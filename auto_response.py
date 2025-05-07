#!/usr/bin/env python3
import json
import os
import sqlite3
import subprocess
import time
import re
import uuid
import logging
from datetime import datetime, timedelta
from email.utils import parseaddr
import random

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("auto_response.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("gmail_auto_response")

# Constants
DB_PATH = "email_responses.db"

# Email templates for different scenarios
EMAIL_TEMPLATES = {
    "sales": {
        "subject": "Re: {subject}",
        "body": """
Thanks for reaching out about your sales proposal. 

I will review your information carefully. In the meantime, if you want to improve your sales outreach, try our free tool at chat.anablock.com.

Best,
{user_name}
        """,
        "html_body": """
<p>Thanks for reaching out about your sales proposal.</p>

<p>I will review your information carefully. In the meantime, if you want to improve your sales outreach, try our free tool at <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=sales&tracking_id={tracking_id}">chat.anablock.com</a>.</p>

<p>Best,<br>
{user_name}</p>

<img src="https://tracking.anablock.com/pixel/{tracking_id}" width="1" height="1" />
        """
    },
    "general": {
        "subject": "Re: {subject}",
        "body": """
Thank you for your message.

I've received your email and will get back to you soon. For immediate assistance, feel free to check out our resources at chat.anablock.com.

Regards,
{user_name}
        """,
        "html_body": """
<p>Thank you for your message.</p>

<p>I've received your email and will get back to you soon. For immediate assistance, feel free to check out our resources at <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=general&tracking_id={tracking_id}">chat.anablock.com</a>.</p>

<p>Regards,<br>
{user_name}</p>

<img src="https://tracking.anablock.com/pixel/{tracking_id}" width="1" height="1" />
        """
    },
    "meeting": {
        "subject": "Re: {subject}",
        "body": """
Thanks for the meeting request.

I'll check my availability and respond shortly. In the meantime, you might find our AI assistant helpful for scheduling: chat.anablock.com.

Cheers,
{user_name}
        """,
        "html_body": """
<p>Thanks for the meeting request.</p>

<p>I'll check my availability and respond shortly. In the meantime, you might find our AI assistant helpful for scheduling: <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=meeting&tracking_id={tracking_id}">chat.anablock.com</a>.</p>

<p>Cheers,<br>
{user_name}</p>

<img src="https://tracking.anablock.com/pixel/{tracking_id}" width="1" height="1" />
        """
    }
}

# Smart filtering keywords
EMAIL_FILTERS = {
    "sales": [
        "proposal", "quote", "pricing", "offering", "solution", "product", "service", 
        "discount", "deal", "opportunity", "roi", "investment", "purchase"
    ],
    "meeting": [
        "meeting", "call", "appointment", "schedule", "availability", "calendar", 
        "discuss", "zoom", "teams", "google meet", "webex", "conference"
    ]
}

# User configuration - should be in a separate config file in production
USER_CONFIG = {
    "name": "Anablock Team",  # Your name for email signatures
    "domains_to_exclude": ["anablock.com", "gmail.com"],  # Don't respond to these domains
    "exclude_previous_correspondents": True,  # Don't auto-respond to people you've emailed before
    "business_hours_only": True,  # Only send during business hours
    "business_hours": {
        "start": 9,  # 9 AM
        "end": 17    # 5 PM
    },
    "max_responses_per_run": 20,  # Limit responses per script run
}

# Google OAuth credentials - store these securely!
# You should use environment variables or a secure secret manager
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.environ.get("GOOGLE_REFRESH_TOKEN")

def init_db():
    """Initialize SQLite database to track responded emails and analytics."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table for tracking responded emails
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS responded_emails (
        message_id TEXT PRIMARY KEY,
        thread_id TEXT,
        from_email TEXT,
        from_name TEXT,
        subject TEXT,
        template_used TEXT,
        response_time TIMESTAMP,
        tracking_id TEXT
    )
    ''')
    
    # Table for tracking email opens
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS email_analytics (
        tracking_id TEXT PRIMARY KEY,
        message_id TEXT,
        from_email TEXT,
        template_used TEXT,
        sent_time TIMESTAMP,
        opened BOOLEAN DEFAULT 0,
        first_opened_time TIMESTAMP,
        open_count INTEGER DEFAULT 0,
        FOREIGN KEY(message_id) REFERENCES responded_emails(message_id)
    )
    ''')
    
    # Table for tracking previous correspondents (people you've emailed)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS previous_correspondents (
        email_address TEXT PRIMARY KEY,
        last_contact_time TIMESTAMP
    )
    ''')
    
    conn.commit()
    return conn

def call_mcp_tool(tool_name, params):
    """Make a call to an MCP tool with proper error handling."""
    try:
        # In a production environment, use the actual MCP client libraries
        # This is a simplified version that simulates the call structure
        cmd = [
            "cascade", "mcp", "call",
            "--server", "gmail",
            "--tool", tool_name,
            "--params", json.dumps(params)
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Error calling MCP tool {tool_name}: {result.stderr}")
            return None
        
        return json.loads(result.stdout)
    except Exception as e:
        logger.error(f"Exception in call_mcp_tool({tool_name}): {str(e)}")
        return None

def refresh_access_token():
    """Refresh the Google access token."""
    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN]):
        logger.error("Missing Google API credentials in environment variables")
        return None
    
    params = {
        "google_refresh_token": GOOGLE_REFRESH_TOKEN,
        "google_client_id": GOOGLE_CLIENT_ID,
        "google_client_secret": GOOGLE_CLIENT_SECRET
    }
    
    logger.info("Refreshing access token")
    result = call_mcp_tool("gmail_refresh_token", params)
    if not result or "access_token" not in result:
        logger.error("Failed to refresh token")
        return None
    
    logger.info("Token refreshed successfully")
    return result["access_token"]

def get_recent_emails(access_token, max_results=20):
    """Get recent emails from Gmail."""
    params = {
        "google_access_token": access_token,
        "max_results": max_results,
        "unread_only": False  # We want to process all recent emails
    }
    
    logger.info(f"Fetching {max_results} recent emails")
    result = call_mcp_tool("gmail_get_recent_emails", params)
    if not result or "emails" not in result:
        logger.error("Failed to get recent emails")
        return []
    
    logger.info(f"Retrieved {len(result['emails'])} emails")
    return result["emails"]

def send_email(access_token, to_email, to_name, subject, body, html_body, thread_id=None):
    """Send an auto-response email."""
    params = {
        "google_access_token": access_token,
        "to": to_email,
        "subject": subject,
        "body": body,
        "html_body": html_body
    }
    
    # If this is a reply to a specific thread, add threading
    if thread_id:
        params["thread_id"] = thread_id
    
    logger.info(f"Sending email to {to_email}")
    result = call_mcp_tool("gmail_send_email", params)
    if not result or "messageId" not in result:
        logger.error(f"Failed to send email to {to_email}")
        return None
    
    logger.info(f"Successfully sent email to {to_email}")
    return result["messageId"]

def extract_email_parts(from_field):
    """Extract name and email address from a 'From' field."""
    name, email = parseaddr(from_field)
    # If name is empty, use the part before @ in email
    if not name and '@' in email:
        name = email.split('@')[0]
    return name.strip(), email.strip()

def should_respond_to_email(email_data, conn, cursor):
    """Determine if we should respond to this email using smart filtering."""
    # Extract data
    from_name, from_email = extract_email_parts(email_data.get("from", ""))
    subject = email_data.get("subject", "")
    body = email_data.get("body", "")
    message_id = email_data.get("id", "")
    
    # Rule 1: Skip if we've already responded
    cursor.execute("SELECT message_id FROM responded_emails WHERE message_id = ?", (message_id,))
    if cursor.fetchone():
        logger.debug(f"Skipping {message_id}: already responded")
        return False, None
    
    # Rule 2: Skip emails from excluded domains
    for domain in USER_CONFIG["domains_to_exclude"]:
        if domain.lower() in from_email.lower():
            logger.debug(f"Skipping {message_id}: from excluded domain {domain}")
            return False, None
    
    # Rule 3: Skip if outside business hours
    if USER_CONFIG["business_hours_only"]:
        current_hour = datetime.now().hour
        if not (USER_CONFIG["business_hours"]["start"] <= current_hour < USER_CONFIG["business_hours"]["end"]):
            logger.debug(f"Skipping {message_id}: outside business hours")
            return False, None
    
    # Rule 4: Skip if we've previously corresponded with this person
    if USER_CONFIG["exclude_previous_correspondents"]:
        cursor.execute("SELECT email_address FROM previous_correspondents WHERE email_address = ?", (from_email,))
        if cursor.fetchone():
            logger.debug(f"Skipping {message_id}: previous correspondent")
            return False, None
    
    # Determine email type based on content
    combined_text = f"{subject} {body}".lower()
    
    # Check for sales-related keywords
    for keyword in EMAIL_FILTERS["sales"]:
        if keyword.lower() in combined_text:
            logger.debug(f"Email {message_id} classified as: sales")
            return True, "sales"
    
    # Check for meeting-related keywords
    for keyword in EMAIL_FILTERS["meeting"]:
        if keyword.lower() in combined_text:
            logger.debug(f"Email {message_id} classified as: meeting")
            return True, "meeting"
    
    # Default to general response
    logger.debug(f"Email {message_id} classified as: general")
    return True, "general"

def format_template(template_type, subject, tracking_id, user_name):
    """Format the email template with dynamic content."""
    template = EMAIL_TEMPLATES[template_type]
    return {
        "subject": template["subject"].format(subject=subject),
        "body": template["body"].format(user_name=user_name, tracking_id=tracking_id),
        "html_body": template["html_body"].format(user_name=user_name, tracking_id=tracking_id)
    }

def record_analytics_data(conn, cursor, message_id, from_email, template_used, tracking_id):
    """Record analytics data for the sent email."""
    try:
        current_time = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO email_analytics (tracking_id, message_id, from_email, template_used, sent_time) VALUES (?, ?, ?, ?, ?)",
            (tracking_id, message_id, from_email, template_used, current_time)
        )
        conn.commit()
        logger.debug(f"Recorded analytics data for message {message_id}")
    except sqlite3.Error as e:
        logger.error(f"Database error recording analytics: {str(e)}")

def main():
    """Main function to check emails and send auto-responses."""
    logger.info(f"Starting auto-response check at {datetime.now()}")
    
    # Initialize database
    conn = init_db()
    cursor = conn.cursor()
    
    # Refresh access token
    access_token = refresh_access_token()
    if not access_token:
        logger.error("Could not obtain access token. Exiting.")
        return
    
    # Get recent emails
    emails = get_recent_emails(access_token, max_results=30)
    
    # Track new responses
    response_count = 0
    
    # Process each email
    for email in emails:
        # Stop if we've reached the maximum responses per run
        if response_count >= USER_CONFIG["max_responses_per_run"]:
            logger.info(f"Reached maximum responses per run ({USER_CONFIG['max_responses_per_run']})")
            break
        
        # Check if we should respond to this email
        should_respond, template_type = should_respond_to_email(email, conn, cursor)
        
        if should_respond:
            # Extract email details
            message_id = email.get("id")
            thread_id = email.get("threadId")
            from_name, from_email = extract_email_parts(email.get("from", ""))
            subject = email.get("subject", "")
            
            # Generate tracking ID for this email
            tracking_id = str(uuid.uuid4())
            
            # Format the appropriate template
            formatted_template = format_template(
                template_type, 
                subject, 
                tracking_id,
                USER_CONFIG["name"]
            )
            
            # Send the auto-response
            sent_message_id = send_email(
                access_token,
                from_email,
                from_name,
                formatted_template["subject"],
                formatted_template["body"],
                formatted_template["html_body"],
                thread_id
            )
            
            if sent_message_id:
                # Record that we've responded to this email
                try:
                    current_time = datetime.now().isoformat()
                    cursor.execute(
                        "INSERT INTO responded_emails VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            message_id,
                            thread_id,
                            from_email,
                            from_name,
                            subject,
                            template_type,
                            current_time,
                            tracking_id
                        )
                    )
                    conn.commit()
                    
                    # Record analytics data
                    record_analytics_data(conn, cursor, message_id, from_email, template_type, tracking_id)
                    
                    response_count += 1
                    logger.info(f"Auto-responded to {from_email} using {template_type} template")
                except sqlite3.Error as e:
                    logger.error(f"Database error: {str(e)}")
    
    logger.info(f"Auto-response check complete. Sent {response_count} auto-responses.")
    conn.close()

if __name__ == "__main__":
    main()
