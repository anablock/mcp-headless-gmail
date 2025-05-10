#!/usr/bin/env python3
import json
import os
import subprocess
import time
import re
import uuid
import logging
import base64
from datetime import datetime, timedelta
from email.utils import parseaddr
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random

# Import database configuration
from db_config import get_db_connection, init_db

# Import Google API libraries
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

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
# DB_PATH is now handled by db_config.py

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
    "noreply", "no-reply", "do-not-reply", "donotreply",
    "notification", "notify", "alert", "update", "info@", "news@",
    "automated", "auto-confirm", "confirm@", "confirmation",
    "newsletter", "marketing", "promotions", "special", "offers",
    "announcement", "bulletin", "statement", "receipt", "invoice",
    "billing", "payment", "transaction", "order", "shipping",
    "delivery", "tracking", "support@", "help@", "service@",
    "contact@", "feedback@", "customerservice", "sales@",
    "webmaster@", "admin@", "team@", "mailer-daemon",
    "postmaster", "bounce", "returnpath", "return-path",
    "unsubscribe", "subscription", "welcome", "activation",
    "verify", "verification", "security", "account",
    "password", "signin", "login", "auth",
    "report", "summary", "digest", "roundup", "substack", "salesforce",
    "digital.costco.com", "email.mailwtatour.com", "email.mckinsey.com",
    "weekly", "daily", "monthly", "announcement", "broadcast",
    
    # Common marketing emails
    "marketing@", "promotions@", "offers@", "sales@", "events@",
    
    # Specific large senders
    "amazon", "ebay", "paypal", "stripe", "salesforce", "hubspot",
    "zendesk", "mailchimp", "sendgrid", "shopify", "slack", "jira",
    "asana", "trello", "github", "linkedin", "facebook", "twitter",
    "instagram", "google", "microsoft", "apple", "adobe",
    
    # Newsletter and marketing services
    "substack", "beehiiv", "convertkit", "mailerlite", "constantcontact",
    "campaign-archive", "mailchi", "aweber", "getresponse", "activecampaign",
    "drip.com", "feedblitz", "pardot", "exacttarget", "marketo", "eloqua",
    "nextdoor", "medium", "dev.to", "neon.tech", "ghost.io", "buttondown",
    "revue", "tinyletter", "campaignmonitor", "mailgun", "sendpulse", "infusionsoft"
]

# Email domains to exclude (added as an additional filter)
NOTIFICATION_DOMAINS = [
    "email.nextdoor.com",
    "substack.com",
    "beehiiv.com",
    "mail.beehiiv.com",
    "convertkit.com",
    "mailchimp.com",
    "campaign-archive.com",
    "dev.to",
    "neon.tech",
    "medium.com",
    "newsletters.com",
    "e.linkedin.com",
    "t.co",
    "n.theverge.com",
    "insider.com",
    "stockinsider.com",
    "coreserver.jp",
    "amazonses.com",
    "sparkpost.com",
    "salesforce.com",
    "sender.net",
    "sendgrid.net",
    "mailgun.org",
    "mail.ru",
    "mailer.io",
    "govdelivery.com",
    "feedback-vlc.netflix.com.netflix.net",
    "news.stripe.com",
    "marketing.intercom-mail.com"
]

# Smart filtering keywords for template selection
EMAIL_FILTERS = {
    "sales": [
        "proposal", "quote", "pricing", "offering", "solution", "product", "service", 
        "discount", "deal", "opportunity", "roi", "investment", "purchase", "buy",
        "cost", "price", "demo", "trial", "subscription", "package", "plan",
        "contract", "client", "customer", "budget", "revenue", "profit", "business"
    ],
    "meeting": [
        "meeting", "call", "appointment", "schedule", "availability", "calendar", 
        "discuss", "zoom", "teams", "google meet", "webex", "conference", "consultation",
        "chat", "talk", "sync", "connect", "meet", "interview", "session", "time",
        "slot", "available", "when", "tomorrow", "next week", "30 min", "hour", "quick call"
    ],
    "founder": [
        "founder", "ceo", "entrepreneur", "startup", "company", "venture", "backing",
        "investor", "angel", "vc", "venture capital", "funding", "series", "round",
        "pitch", "deck", "presentation", "co-founder", "launch", "started", "starting",
        "building", "growing", "scaling", "vision", "mission", "leadership", "founding"
    ]
}

# Default email templates - used only if database templates are not available
DEFAULT_EMAIL_TEMPLATES = {
    "founder": {
        "subject": "Re: {subject}",
        "body": """Hi {recipient_first_name},

Thanks for reaching out. I wanted to personally respond and introduce you to what we're building at Anablock.

{ai_personalization}

As a special offer for you, I'd like to provide $100 in free credits to try our email personalization tools at chat.anablock.com. Our AI-powered workspace offers various automations for sales and marketing teams that can help with your specific needs.

Simply use code "FOUNDER100" when you sign up at https://chat.anablock.com

Looking forward to seeing how our tools can help your business.

Best regards,
Vuk Dukic
Founder, Anablock""",
        "html_body": """<p>Hi {recipient_first_name},</p>

<p>Thanks for reaching out. I wanted to <strong>personally respond</strong> and introduce you to what we're building at Anablock.</p>

<p>{ai_personalization}</p>

<p><strong>🎁 SPECIAL OFFER:</strong> I'd like to provide <strong>$100 in free credits</strong> to try our email personalization tools at chat.anablock.com. Our AI-powered workspace offers various automations for sales and marketing teams that can help with your specific needs.</p>

<p>Simply use code <strong>"FOUNDER100"</strong> when you sign up at <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=founder&tracking_id={tracking_id}">chat.anablock.com</a></p>

<p>Looking forward to seeing how our tools can help your business.</p>

<p>Best regards,<br>
Vuk Dukic<br>
Founder, Anablock</p>

<p style="color:#888;font-size:11px;">This is an automated reply, but I'll personally follow up on any responses.</p>"""
    },
    "sales": {
        "subject": "Re: {subject}",
        "body": """Hi {recipient_first_name},

Thanks for reaching out about your sales inquiry. I'll review your message carefully and get back to you soon.

In the meantime, I wanted to offer you $50 in free credits to try our AI-powered sales automation tools at chat.anablock.com. Our platform can help you personalize outreach, analyze responses, and improve conversion rates.

Use promo code "SALES50" when you register at https://chat.anablock.com to claim your free credits.

Best,
{user_name}""",
        "html_body": """<p>Hi {recipient_first_name},</p>

<p>Thanks for reaching out about your sales inquiry. I'll review your message carefully and get back to you soon.</p>

<p><strong>🚀 EXCLUSIVE OFFER:</strong> I wanted to offer you <strong>$50 in free credits</strong> to try our AI-powered sales automation tools at chat.anablock.com. Our platform can help you personalize outreach, analyze responses, and improve conversion rates.</p>

<p>Use promo code <strong>"SALES50"</strong> when you register at <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=sales&tracking_id={tracking_id}">chat.anablock.com</a> to claim your free credits.</p>

<p>Best,<br>
{user_name}</p>

<p style="color:#888;font-size:11px;">This is an automated reply to your sales inquiry. I'll personally review your message and respond as soon as possible.</p>

<img src="https://tracking.anablock.com/pixel/{tracking_id}" width="1" height="1" />"""
    },
    "general": {
        "subject": "Re: {subject}",
        "body": """Hi {recipient_first_name},

Thank you for your message. I've received your email and will get back to you as soon as possible.

While you wait, I'd like to offer you $25 in free credits to explore our AI-powered tools at Anablock. Our workspace offers various automations for email personalization, customer support, and marketing that might be useful for you.

Visit https://chat.anablock.com and use code "WELCOME25" to claim your free credits.

Regards,
{user_name}""",
        "html_body": """<p>Hi {recipient_first_name},</p>

<p>Thank you for your message. I've received your email and will get back to you as soon as possible.</p>

<p><strong>💌 SPECIAL OFFER:</strong> While you wait, I'd like to offer you <strong>$25 in free credits</strong> to explore our AI-powered tools at Anablock. Our workspace offers various automations for email personalization, customer support, and marketing that might be useful for you.</p>

<p>Visit <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=general&tracking_id={tracking_id}">chat.anablock.com</a> and use code <strong>"WELCOME25"</strong> to claim your free credits.</p>

<p>Regards,<br>
{user_name}</p>

<p style="color:#888;font-size:11px;">This is an automated response. I'll review your message personally and get back to you soon.</p>

<img src="https://tracking.anablock.com/pixel/{tracking_id}" width="1" height="1" />"""
    },
    "meeting": {
        "subject": "Re: {subject}",
        "body": """Hi {recipient_first_name},

Thanks for your meeting request. I appreciate your interest in connecting!

I'll check my calendar and get back to you shortly with some available times. In the meantime, I'd like to offer you $30 in free credits to try our meeting scheduling AI tool at chat.anablock.com. It can help you automate scheduling and follow-ups, saving valuable time.

Use code "MEET30" when you sign up at https://chat.anablock.com

Looking forward to our conversation,
{user_name}""",
        "html_body": """<p>Hi {recipient_first_name},</p>

<p>Thanks for your meeting request. I appreciate your interest in connecting!</p>

<p>I'll check my calendar and get back to you shortly with some available times. In the meantime, I'd like to offer you <strong>$30 in free credits</strong> to try our meeting scheduling AI tool at chat.anablock.com. It can help you automate scheduling and follow-ups, saving valuable time.</p>

<p>Use code <strong>"MEET30"</strong> when you sign up at <a href="https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=meeting&tracking_id={tracking_id}">chat.anablock.com</a></p>

<p>Looking forward to our conversation,<br>
{user_name}</p>

<p style="color:#888;font-size:11px;">This is an automated reply to your meeting request. I'll follow up personally to schedule our conversation.</p>

<img src="https://tracking.anablock.com/pixel/{tracking_id}" width="1" height="1" />"""
    },
    "founder": {
        "subject": "Re: {subject}",
        "body": "Hi {recipient_first_name},\n\nThanks for reaching out. We have a great product for you at Anablock.\n\n{ai_personalization}\n\nTry our chat.anablock.com solution for your customer support needs. It's helping businesses just like yours improve response times and customer satisfaction.\n\nBest regards,\nVuk Dukic\nFounder, Anablock",
        "html_body": "<p>Hi {recipient_first_name},</p>\n\n<p>Thanks for reaching out. We have a great product for you at Anablock.</p>\n\n<p>{ai_personalization}</p>\n\n<p>Try our <a href=\"https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=founder&tracking_id={tracking_id}\">chat.anablock.com</a> solution for your customer support needs. It's helping businesses just like yours improve response times and customer satisfaction.</p>\n\n<p>Best regards,<br>\nVuk Dukic<br>\nFounder, Anablock</p>"
    }
}

# EMAIL_TEMPLATES will be populated from the database during init_db
EMAIL_TEMPLATES = {    "founder": {
        "subject": "Re: {subject}",
        "body": "Hi {recipient_first_name},\n\nThanks for reaching out. We have a great product for you at Anablock.\n\n{ai_personalization}\n\nTry our chat.anablock.com solution for your customer support needs. It's helping businesses just like yours improve response times and customer satisfaction.\n\nBest regards,\nVuk Dukic\nFounder, Anablock",
        "html_body": "<p>Hi {recipient_first_name},</p>\n\n<p>Thanks for reaching out. We have a great product for you at Anablock.</p>\n\n<p>{ai_personalization}</p>\n\n<p>Try our <a href=\"https://chat.anablock.com?utm_source=email&utm_medium=auto_reply&utm_campaign=founder&tracking_id={tracking_id}\">chat.anablock.com</a> solution for your customer support needs. It's helping businesses just like yours improve response times and customer satisfaction.</p>\n\n<p>Best regards,<br>\nVuk Dukic<br>\nFounder, Anablock</p>"
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
    ],
    "founder": [
        "founder", "ceo", "chief executive", "leadership", "executive team", "startup",
        "entrepreneur", "vision", "mission", "company culture"
    ]
}

def refresh_access_token():
    """Refresh the OAuth access token using the refresh token."""
    try:
        # Get credentials from environment variables
        client_id = os.environ.get('GOOGLE_CLIENT_ID')
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
        refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
        
        if not all([client_id, client_secret, refresh_token]):
            logger.error("Missing required environment variables for token refresh")
            return None
            
        # Command to refresh token using OAuth2 protocol
        cmd = [
            "curl", "-s", "https://oauth2.googleapis.com/token",
            "-d", f"client_id={client_id}",
            "-d", f"client_secret={client_secret}",
            "-d", "grant_type=refresh_token",
            "-d", f"refresh_token={refresh_token}"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        response = json.loads(result.stdout)
        
        if "error" in response:
            logger.error(f"Failed to refresh token: {response['error_description'] if 'error_description' in response else response['error']}")
            return None
            
        # Return the new access token
        return response["access_token"]
    except Exception as e:
        logger.error(f"Error refreshing access token: {str(e)}")
        return None

def get_default_template(conn=None, cursor=None):
    """Get the default email template from the database."""
    close_connection = False
    try:
        if conn is None or cursor is None:
            conn = get_db_connection()
            cursor = conn.cursor()
            close_connection = True
        
        # Query for the default template
        cursor.execute("SELECT template_type FROM email_templates WHERE is_default = 1 LIMIT 1")
        result = cursor.fetchone()
        
        # Return default template type or fallback to "general"
        return result[0] if result else "general"
    except Exception as e:
        logger.error(f"Error getting default template: {str(e)}")
        return "general"
    finally:
        if close_connection and conn is not None:
            conn.close()

def get_all_templates_from_db(conn=None, cursor=None):
    """Get all email templates from the database."""
    close_connection = False
    try:
        if conn is None or cursor is None:
            conn = get_db_connection()
            cursor = conn.cursor()
            close_connection = True
        
        # Check if the email_templates table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_templates'")
        if cursor.fetchone() is None:
            # Table doesn't exist, use default templates
            templates = []
            for template_type, template in DEFAULT_EMAIL_TEMPLATES.items():
                templates.append({
                    "template_type": template_type,
                    "subject": template["subject"],
                    "body": template["body"],
                    "html_body": template["html_body"],
                    "is_default": template_type == "general"  # Set general as default
                })
            return templates
            
        # Check if is_default column exists in the table
        cursor.execute("PRAGMA table_info(email_templates)")
        columns = [column[1] for column in cursor.fetchall()]
        has_default_column = "is_default" in columns
        
        if has_default_column:
            cursor.execute("SELECT template_type, subject, body, html_body, is_default FROM email_templates")
        else:
            cursor.execute("SELECT template_type, subject, body, html_body FROM email_templates")
            
        templates = []
        
        for row in cursor.fetchall():
            template = {
                "template_type": row[0],
                "subject": row[1],
                "body": row[2],
                "html_body": row[3]
            }
            
            if has_default_column:
                template["is_default"] = bool(row[4])
            else:
                template["is_default"] = (row[0] == "general")  # Set general as default
                
            templates.append(template)
            
        # If no templates in DB, return the default ones
        if not templates:
            for template_type, template in DEFAULT_EMAIL_TEMPLATES.items():
                templates.append({
                    "template_type": template_type,
                    "subject": template["subject"],
                    "body": template["body"],
                    "html_body": template["html_body"],
                    "is_default": template_type == "general"  # Set general as default
                })
        
        return templates
    except sqlite3.Error as e:
        logger.error(f"Database error retrieving templates: {str(e)}")
        # On error, fall back to default templates
        templates = []
        for template_type, template in DEFAULT_EMAIL_TEMPLATES.items():
            templates.append({
                "template_type": template_type,
                "subject": template["subject"],
                "body": template["body"],
                "html_body": template["html_body"],
                "is_default": template_type == "general"
            })
        return templates
    finally:
        if close_connection and conn is not None:
            conn.close()

def init_db():
    """Initialize database to track responded emails and analytics.
    Delegates to the db_config module which handles both SQLite and PostgreSQL.
    """
    # Call the init_db function from db_config which handles all table creation
    # This function supports both SQLite and PostgreSQL
    from db_config import init_db as init_database
    init_database()
    
    # We get a database connection to insert default configuration
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Insert default configuration if it doesn't exist
    for key, value in USER_CONFIG.items():
        cursor.execute(
            "INSERT OR IGNORE INTO user_config (key, value) VALUES (?, ?)",
            (key, json.dumps(value))
        )
    
    # Load templates from the database
    load_templates_from_db(cursor)
    
    conn.commit()
    return conn

def load_templates_from_db(cursor):
    """Load email templates from the database."""
    global EMAIL_TEMPLATES
    
    # Query all templates from the database
    cursor.execute("SELECT template_type, subject, body, html_body FROM email_templates")
    templates = cursor.fetchall()
    
    # If no templates in the database, use the default templates and populate the database
    if not templates:
        EMAIL_TEMPLATES = DEFAULT_EMAIL_TEMPLATES.copy()
        
        # Add default templates to the database
        for template_type, template in DEFAULT_EMAIL_TEMPLATES.items():
            cursor.execute(
                "INSERT INTO email_templates (template_type, subject, body, html_body) VALUES (?, ?, ?, ?)",
                (template_type, template["subject"], template["body"], template["html_body"])
            )
    else:
        # Populate EMAIL_TEMPLATES from database
        EMAIL_TEMPLATES = {}
        for template_type, subject, body, html_body in templates:
            EMAIL_TEMPLATES[template_type] = {
                "subject": subject,
                "body": body,
                "html_body": html_body
            }

def save_template_to_db(template_type, subject, body, html_body, conn=None, cursor=None):
    """Save or update an email template in the database."""
    close_connection = False
    try:
        if conn is None or cursor is None:
            conn = get_db_connection()
            cursor = conn.cursor()
            close_connection = True
        
        # Check if template already exists
        cursor.execute("SELECT COUNT(*) FROM email_templates WHERE template_type = ?", (template_type,))
        template_exists = cursor.fetchone()[0] > 0
        
        if template_exists:
            # Update existing template
            cursor.execute(
                "UPDATE email_templates SET subject = ?, body = ?, html_body = ? WHERE template_type = ?",
                (subject, body, html_body, template_type)
            )
            logger.info(f"Updated template: {template_type}")
        else:
            # Insert new template
            cursor.execute(
                "INSERT INTO email_templates (template_type, subject, body, html_body) VALUES (?, ?, ?, ?)",
                (template_type, subject, body, html_body)
            )
            logger.info(f"Added new template: {template_type}")
        
        # Update in-memory template cache
        global EMAIL_TEMPLATES
        EMAIL_TEMPLATES[template_type] = {
            "subject": subject,
            "body": body,
            "html_body": html_body
        }
        
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error saving template to database: {str(e)}")
        if conn is not None:
            conn.rollback()
        return False
    finally:
        if close_connection and conn is not None:
            conn.close()

def research_sender(sender_name, sender_email):
    """Use AI to research information about the sender for personalization."""
    try:
        # This is where you'd integrate with an AI service
        # For now, we'll simulate research with some basic personalization
        import random
        
        # Extract domain from sender email
        domain = sender_email.split('@')[-1] if '@' in sender_email else ''
        
        # Create a list of potential personalized messages based on the domain
        personalized_messages = [
            f"I noticed you're from {domain}, which is known for innovative solutions in the industry.",
            f"Your company seems to be growing rapidly based on recent news.",
            f"I see you might be interested in improving customer interactions and support systems.",
            f"It looks like your team could benefit from our AI-powered customer support tools.",
            f"Based on your industry, I think you'd find our analytics features particularly valuable."
        ]
        
        # In a real implementation, you would use actual research about the sender
        return random.choice(personalized_messages)
    except Exception as e:
        logger.error(f"Error researching sender: {str(e)}")
        return "I'm looking forward to exploring how we might work together."

def personalize_template(template, sender_name, sender_email, subject, message_id):
    """Format the email template with dynamic content."""
    # Basic personalization with recipient name
    recipient_first_name = get_first_name(sender_name) if sender_name else "there"
    
    # Add AI-powered personalization if enabled
    ai_insights = ""
    if USER_CONFIG.get("ai_personalization", False) and USER_CONFIG.get("research_sender", False):
        ai_insights = research_sender(sender_name, sender_email)
    
    # Replace placeholders
    message_body = template["body"].format(
        recipient_first_name=recipient_first_name,
        recipient_name=sender_name or "there",
        user_name=USER_CONFIG["name"],
        user_title=USER_CONFIG.get("title", ""),
        subject=subject,
        tracking_id=message_id[:8],
        ai_personalization=ai_insights
    )
    
    html_body = template["html_body"].format(
        recipient_first_name=recipient_first_name,
        recipient_name=sender_name or "there",
        user_name=USER_CONFIG["name"],
        user_title=USER_CONFIG.get("title", ""),
        subject=subject,
        tracking_id=message_id[:8],
        ai_personalization=ai_insights
    )
    
    return {
        "subject": template["subject"].format(subject=subject),
        "body": message_body,
        "html_body": html_body
    }

def extract_email_parts(from_field):
    """Extract name and email address from a 'From' field."""
    name, email = parseaddr(from_field)
    # If name is empty, use the part before @ in email
    if not name and '@' in email:
        name = email.split('@')[0]
    return name.strip(), email.strip()

def get_first_name(full_name):
    """Extract first name from a full name string."""
    if not full_name:
        return "there"
        
    # Split the name and take the first part
    parts = full_name.split()
    if not parts:
        return "there"
        
    # Return the first part, capitalized if possible
    first_name = parts[0].strip()
    return first_name.capitalize() if first_name else "there"

def format_template(template_type, subject, tracking_id, user_name, recipient_name=""):
    """Format the email template with dynamic content."""
    # Use the DEFAULT_EMAIL_TEMPLATES as a fallback
    template = DEFAULT_EMAIL_TEMPLATES.get(template_type, DEFAULT_EMAIL_TEMPLATES["general"])
    
    # Extract first name from recipient_name or use 'there' as default
    recipient_first_name = get_first_name(recipient_name) if recipient_name else "there"
    
    # Prepare formatting parameters
    format_params = {
        "subject": subject,
        "user_name": user_name,
        "tracking_id": tracking_id,
        "recipient_name": recipient_name or "there",
        "recipient_first_name": recipient_first_name,
        "user_title": USER_CONFIG.get("title", ""),
        "ai_personalization": ""
    }
    
    try:
        return {
            "subject": template["subject"].format(**format_params),
            "body": template["body"].format(**format_params),
            "html_body": template["html_body"].format(**format_params)
        }
    except KeyError as e:
        logger.error(f"Template formatting error with {template_type} template: {str(e)}")
        # Use general template as a fallback with minimal parameters
        fallback = DEFAULT_EMAIL_TEMPLATES["general"]
        try:
            return {
                "subject": fallback["subject"].format(subject=subject),
                "body": fallback["body"].format(**format_params),
                "html_body": fallback["html_body"].format(**format_params)
            }
        except Exception as e2:
            logger.error(f"Even fallback template failed: {str(e2)}")
            # Return a very simple template as last resort
            return {
                "subject": f"Re: {subject}",
                "body": f"Thank you for your message. I will respond soon.\n\nRegards,\n{user_name}",
                "html_body": f"<p>Thank you for your message. I will respond soon.</p><p>Regards,<br>{user_name}</p>"
            }

def send_email(access_token, to_email, to_name="", subject="", body="", html_body=None, thread_id=None):
    """Send an email response using Gmail API."""
    try:
        # Create credentials from the access token
        credentials = Credentials(
            token=access_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get('GOOGLE_CLIENT_ID'),
            client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
            refresh_token=os.environ.get('GOOGLE_REFRESH_TOKEN'),
            scopes=['https://www.googleapis.com/auth/gmail.modify']
        )
        
        # Build Gmail service
        service = build('gmail', 'v1', credentials=credentials, cache_discovery=False)
        
        # Create message container
        message = MIMEMultipart('alternative')
        
        # Format recipient with name if provided
        recipient = to_email
        if to_name:
            recipient = f'"{to_name}" <{to_email}>'
            
        message['To'] = recipient
        message['Subject'] = subject
        
        # Attach plain text body
        message.attach(MIMEText(body, 'plain'))
        
        # Attach HTML body if provided
        if html_body:
            message.attach(MIMEText(html_body, 'html'))
        
        # Encode the message
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        # Create the message body
        email_body = {'raw': raw_message}
        
        # Add thread ID if replying to a specific thread
        if thread_id:
            email_body['threadId'] = thread_id
        
        # Send the message
        result = service.users().messages().send(userId='me', body=email_body).execute()
        logger.info(f"Email sent, message ID: {result.get('id')}")
        return result
        
    except HttpError as error:
        logger.error(f'An error occurred sending email: {error}')
        return None
    except Exception as e:
        logger.error(f'Unexpected error sending email: {str(e)}')
        return None

def should_respond_to_email(email_data, conn, cursor):
    """Determine if we should respond to this email using smart filtering."""
    # Extract data
    from_name, from_email = extract_email_parts(email_data.get("from", ""))
    subject = email_data.get("subject", "")
    body = email_data.get("snippet", "")  # Use snippet if available for better analysis
    message_id = email_data.get("id", "")
    
    # Log for debugging
    logger.debug(f"Analyzing email from: {from_email}, subject: {subject[:30]}...")
    
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
        start_hour = USER_CONFIG["business_hours"]["start"]
        end_hour = USER_CONFIG["business_hours"]["end"]
        if not (start_hour <= current_hour < end_hour):
            logger.debug(f"Skipping {message_id}: outside business hours ({current_hour} not in {start_hour}-{end_hour})")
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
            logger.info(f"Skipping {message_id}: matches notification pattern '{pattern}' in sender address")
            return False, None
            
    # Rule 5b: Skip emails from notification domains
    if '@' in from_email_lower:
        domain = from_email_lower.split('@')[1]
        for notification_domain in NOTIFICATION_DOMAINS:
            if notification_domain.lower() in domain:
                logger.info(f"Skipping {message_id}: from notification domain '{notification_domain}'")
                return False, None
    
    # Rule 6: Check for notification keywords in subject
    subject_lower = subject.lower()
    notification_subject_indicators = [
        "notification", "alert", "update", "confirm", "verify", "authentication",
        "password", "security", "account", "subscription", "newsletter", "receipt", 
        "invoice", "statement", "automatic reply", "auto-reply", "confirmation",
        "order", "shipping", "delivery", "tracking", "payment"
    ]
    
    for keyword in notification_subject_indicators:
        if keyword in subject_lower:
            logger.info(f"Skipping {message_id}: subject contains notification keyword '{keyword}'")
            return False, None
    
    # If smart template selection is enabled, use keyword matching
    if USER_CONFIG.get("smart_template_selection", True):
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
    
    # Use the default template if no keywords match or smart selection is disabled
    default_template = USER_CONFIG.get("default_template", "general")
    logger.debug(f"Email {message_id} using default template: {default_template}")
    return True, default_template

def get_recent_emails(access_token=None, max_results=20):
    """Get recent emails from Gmail."""
    try:
        # If access token is not provided, try to refresh it
        if not access_token:
            access_token = refresh_access_token()
            if not access_token:
                logger.error("Failed to refresh access token")
                return {"error": "Failed to refresh access token", "emails": []}
        
        # Create credentials from the access token
        credentials = Credentials(
            token=access_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=os.environ.get('GOOGLE_CLIENT_ID'),
            client_secret=os.environ.get('GOOGLE_CLIENT_SECRET'),
            refresh_token=os.environ.get('GOOGLE_REFRESH_TOKEN'),
            scopes=['https://www.googleapis.com/auth/gmail.modify']
        )
        
        # Build the Gmail service
        service = build('gmail', 'v1', credentials=credentials, cache_discovery=False)
        
        # Call the Gmail API
        results = service.users().messages().list(
            userId='me', 
            maxResults=max_results,
            labelIds=['INBOX']
        ).execute()
        
        messages = results.get('messages', [])
        
        if not messages:
            logger.info("No messages found.")
            return {"success": True, "emails": []}
            
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
            
        return {"success": True, "emails": emails}
        
    except HttpError as error:
        error_message = f'An error occurred retrieving emails: {error}'
        logger.error(error_message)
        return {"error": error_message, "emails": []}
    except Exception as e:
        error_message = f'Unexpected error retrieving emails: {str(e)}'
        logger.error(error_message)
        return {"error": error_message, "emails": []}

def record_analytics(conn, cursor, message_id, from_email, template_used):
    """Record analytics data for the sent email."""
    try:
        tracking_id = str(uuid.uuid4())
        current_time = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO email_analytics (tracking_id, message_id, from_email, template_used, sent_time) VALUES (?, ?, ?, ?, ?)",
            (tracking_id, message_id, from_email, template_used, current_time)
        )
        conn.commit()
        logger.debug(f"Recorded analytics data for message {message_id}")
        return tracking_id
    except sqlite3.Error as e:
        logger.error(f"Database error recording analytics: {str(e)}")
        return str(uuid.uuid4())  # Fallback tracking ID_id


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
    result = get_recent_emails(access_token, max_results=30)
    
    # Check for errors in the response
    if "error" in result:
        logger.error(f"Error retrieving emails: {result.get('error')}")
        return
    
    # Get the emails from the result
    emails = result.get("emails", [])
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
                USER_CONFIG["name"],
                from_name  # Pass the recipient's name
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
                    record_analytics(conn, cursor, message_id, from_email, template_type)
                    
                    response_count += 1
                    logger.info(f"Auto-responded to {from_email} using {template_type} template")
                except sqlite3.Error as e:
                    logger.error(f"Database error: {str(e)}")
    
    logger.info(f"Auto-response check complete. Sent {response_count} responses.")
    conn.close()

if __name__ == "__main__":
    main()
