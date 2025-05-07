#!/usr/bin/env python3
import os
import json
import sqlite3
import uuid
import logging
import re
import argparse
from datetime import datetime, timedelta
from email.utils import parseaddr
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import base64

# Import Google API libraries
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("direct_auto_response.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("gmail_auto_response")

# Constants
DB_PATH = "email_responses.db"
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']

# Email templates for different scenarios
EMAIL_TEMPLATES = {
    "sales": {
        "subject": "Re: {subject}",
        "body": """
Thanks for reaching out about your sales proposal. 

I will review your information carefully. Visit our app for superior email and lead generation, https://chat.anablock.com. It will help you improve your sales process and boost conversion rates.

Best,
Vuk Dukic
Founder, Principal Software Engineer
https://www.anablock.com
353 Sacramento Street, 4
San Francisco, CA 94108, USA
vuk@anablock.com
        """,
        "html_body": """
<p>Thanks for reaching out about your sales proposal.</p>

<p>I will review your information carefully. Visit our app for superior email and lead generation, <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=sales&tracking_id={tracking_id}">https://chat.anablock.com</a>. It will help you improve your sales process and boost conversion rates.</p>

<p>Best,<br>
Vuk Dukic<br>
Founder, Principal Software Engineer<br>
<a href="https://www.anablock.com">https://www.anablock.com</a><br>
353 Sacramento Street, 4<br>
San Francisco, CA 94108, USA<br>
<a href="mailto:vuk@anablock.com">vuk@anablock.com</a></p>

<img src="https://tracking.anablock.com/pixel/{tracking_id}" width="1" height="1" />
        """
    },
    "general": {
        "subject": "Re: {subject}",
        "body": """
Thank you for your message.

I've received your email and will get back to you soon. For immediate assistance, feel free to check out our resources at chat.anablock.com.

Regards,
Vuk Dukic
Founder, Principal Software Engineer
https://www.anablock.com
353 Sacramento Street, 4
San Francisco, CA 94108, USA
vuk@anablock.com
        """,
        "html_body": """
<p>Thank you for your message.</p>

<p>I've received your email and will get back to you soon. For immediate assistance, feel free to check out our resources at <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=general&tracking_id={tracking_id}">chat.anablock.com</a>.</p>

<p>Regards,<br>
Vuk Dukic<br>
Founder, Principal Software Engineer<br>
<a href="https://www.anablock.com">https://www.anablock.com</a><br>
353 Sacramento Street, 4<br>
San Francisco, CA 94108, USA<br>
<a href="mailto:vuk@anablock.com">vuk@anablock.com</a></p>

<img src="https://tracking.anablock.com/pixel/{tracking_id}" width="1" height="1" />
        """
    },
    "meeting": {
        "subject": "Re: {subject}",
        "body": """
Thanks for the meeting request.

I'll check my availability and respond shortly. In the meantime, you might find our AI assistant helpful for scheduling: chat.anablock.com.

Cheers,
Vuk Dukic
Founder, Principal Software Engineer
https://www.anablock.com
353 Sacramento Street, 4
San Francisco, CA 94108, USA
vuk@anablock.com
        """,
        "html_body": """
<p>Thanks for the meeting request.</p>

<p>I'll check my availability and respond shortly. In the meantime, you might find our AI assistant helpful for scheduling: <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=meeting&tracking_id={tracking_id}">chat.anablock.com</a>.</p>

<p>Cheers,<br>
Vuk Dukic<br>
Founder, Principal Software Engineer<br>
<a href="https://www.anablock.com">https://www.anablock.com</a><br>
353 Sacramento Street, 4<br>
San Francisco, CA 94108, USA<br>
<a href="mailto:vuk@anablock.com">vuk@anablock.com</a></p>

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

# User configuration 
USER_CONFIG = {
    "name": "Vuk Dukic",  # Your name for email signatures
    "domains_to_exclude": ["anablock.com", "gmail.com"],  # Don't respond to these domains
    "exclude_previous_correspondents": True,  # Don't auto-respond to people you've emailed before
    "business_hours_only": True,  # Only send during business hours
    "business_hours": {
        "start": 9,  # 9 AM
        "end": 17    # 5 PM
    },
    "max_responses_per_run": 20,  # Limit responses per script run
}

# No-reply and notification email patterns to exclude
NOTIFICATION_PATTERNS = [
    "no-reply",
    "noreply",
    "do-not-reply",
    "donotreply",
    "automated",
    "notification",
    "alert",
    "system",
    "mailer-daemon",
    "postmaster",
    "newsletter",
    "news@",
    "updates@",
    "info@",
    "support@",
    "help@",
    "service@",
    "admin@"
]

def get_gmail_service():
    """Get authenticated Gmail API service."""
    creds = None
    
    # Look for existing credentials in environment variables
    if all([os.environ.get('GOOGLE_CLIENT_ID'), 
            os.environ.get('GOOGLE_CLIENT_SECRET'),
            os.environ.get('GOOGLE_REFRESH_TOKEN')]):
        
        creds = Credentials(
            token=None,  # We'll refresh to get a new token
            refresh_token=os.environ.get('GOOGLE_REFRESH_TOKEN'),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get('GOOGLE_CLIENT_ID'),
            client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
            scopes=SCOPES
        )
        
    # If credentials exist but expired, refresh them
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        logger.info("Refreshed access token")
    elif not creds:
        logger.error("No valid credentials found. Set environment variables or run OAuth flow")
        return None
        
    try:
        # Build the Gmail API service
        service = build('gmail', 'v1', credentials=creds)
        logger.info("Gmail service created successfully")
        return service
    except Exception as e:
        logger.error(f"Error creating Gmail service: {str(e)}")
        return None

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
    
    # Table for tracking link clicks
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS link_clicks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tracking_id TEXT,
        click_time TIMESTAMP,
        FOREIGN KEY(tracking_id) REFERENCES email_analytics(tracking_id)
    )
    ''')
    
    conn.commit()
    return conn

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
    subject = email_data.get("snippet", "")  # Use snippet as a fallback for subject
    if "subject" in email_data:
        subject = email_data["subject"]
    body = email_data.get("snippet", "")  # Use snippet as the body for classification
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
            
    # Rule 5: Skip notification emails and no-reply addresses
    from_email_lower = from_email.lower()
    for pattern in NOTIFICATION_PATTERNS:
        if pattern.lower() in from_email_lower:
            logger.debug(f"Skipping {message_id}: notification/no-reply address ({pattern})")
            return False, None
    
    # Additional check for common notification subject patterns
    subject_lower = subject.lower()
    notification_subject_patterns = [
        "notification", "alert", "update", "confirm", "verify", "authentication",
        "security", "account", "subscription", "newsletter", "receipt", "invoice",
        "statement", "automatic reply", "auto-reply", "confirmation"
    ]
    
    for pattern in notification_subject_patterns:
        if pattern in subject_lower:
            logger.debug(f"Skipping {message_id}: notification subject ({pattern})")
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

def send_email_response(service, to_email, subject, body_text, html_body, thread_id=None):
    """Send an email response using Gmail API."""
    try:
        # Create message container
        message = MIMEMultipart('alternative')
        message['To'] = to_email
        message['Subject'] = subject
        
        # Attach plain text and HTML parts
        message.attach(MIMEText(body_text, 'plain'))
        message.attach(MIMEText(html_body, 'html'))
        
        # Encode the message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Create the message body
        email_body = {'raw': raw_message}
        
        # Add thread ID if replying to a specific thread
        if thread_id:
            email_body['threadId'] = thread_id
        
        # Send the message
        message = service.users().messages().send(userId='me', body=email_body).execute()
        logger.info(f"Email sent, message ID: {message['id']}")
        return message['id']
    
    except HttpError as error:
        logger.error(f'An error occurred sending email: {error}')
        return None

def get_recent_emails(service, max_results=20):
    """Get recent emails from Gmail."""
    try:
        # Call the Gmail API
        results = service.users().messages().list(
            userId='me', 
            maxResults=max_results,
            labelIds=['INBOX']
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            logger.info("No messages found.")
            return []
            
        emails = []
        for message in messages:
            msg = service.users().messages().get(
                userId='me', id=message['id']).execute()
                
            # Extract headers
            headers = {}
            for header in msg['payload']['headers']:
                name = header['name'].lower()
                if name in ['from', 'to', 'subject', 'date']:
                    headers[name] = header['value']
                    
            # Combine message data
            email_data = {
                'id': msg['id'],
                'threadId': msg['threadId'],
                'snippet': msg['snippet'],
                'from': headers.get('from', ''),
                'to': headers.get('to', ''),
                'subject': headers.get('subject', ''),
                'date': headers.get('date', '')
            }
            
            emails.append(email_data)
            
        return emails
        
    except HttpError as error:
        logger.error(f'An error occurred retrieving emails: {error}')
        return []

def main():
    """Main function to check emails and send auto-responses."""
    parser = argparse.ArgumentParser(description="Gmail Auto-Response System")
    parser.add_argument('--test', action='store_true', help='Run in test mode (no emails sent)')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()
    
    # Set logging level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Starting auto-response check at {datetime.now()}")
    logger.info(f"Running in {'TEST' if args.test else 'PRODUCTION'} mode")
    
    # Initialize database
    conn = init_db()
    cursor = conn.cursor()
    
    # Get Gmail service
    service = get_gmail_service()
    if not service:
        logger.error("Failed to create Gmail service. Exiting.")
        return
    
    # Get recent emails
    emails = get_recent_emails(service, max_results=30)
    if not emails:
        logger.info("No recent emails found. Exiting.")
        return
        
    logger.info(f"Retrieved {len(emails)} recent emails")
    
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
            
            logger.info(f"Preparing to respond to: {from_email} using {template_type} template")
            
            if not args.test:
                # Send the auto-response
                sent_message_id = send_email_response(
                    service,
                    from_email,
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
            else:
                # In test mode, just log what would have happened
                logger.info(f"TEST MODE: Would have sent {template_type} template to {from_email}")
                response_count += 1
    
    logger.info(f"Auto-response check complete. {'Would have sent' if args.test else 'Sent'} {response_count} auto-responses.")
    conn.close()

if __name__ == "__main__":
    main()
