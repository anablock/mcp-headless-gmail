#!/usr/bin/env python3
import os
import sys
import logging
from direct_gmail_auto_response import get_gmail_service, init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gmail_test_single")

def send_test_response():
    """Send a single test response to a specific email."""
    # Import all needed functions from the main script
    from direct_gmail_auto_response import (
        get_gmail_service, init_db, send_email_response, 
        format_template, record_analytics_data
    )
    
    # Email to respond to (change this to your test email address)
    test_email = input("Enter your test email address to receive the response: ")
    
    if not test_email or '@' not in test_email:
        logger.error("Invalid email address. Please provide a valid email.")
        return
    
    # Initialize services
    service = get_gmail_service()
    if not service:
        logger.error("Failed to create Gmail service. Check your credentials.")
        return
    
    conn = init_db()
    cursor = conn.cursor()
    
    # Create a test tracking ID
    import uuid
    tracking_id = str(uuid.uuid4())
    
    # Select which template to test
    template_options = ["sales", "meeting", "general"]
    print("\nAvailable templates:")
    for i, template in enumerate(template_options):
        print(f"{i+1}. {template}")
    
    template_choice = input("\nSelect template number (1-3): ")
    try:
        template_index = int(template_choice) - 1
        if template_index < 0 or template_index >= len(template_options):
            raise ValueError("Invalid selection")
        template_type = template_options[template_index]
    except:
        logger.error("Invalid selection. Using 'general' template as default.")
        template_type = "general"
    
    # Format the template
    from direct_gmail_auto_response import format_template, USER_CONFIG
    formatted_template = format_template(
        template_type,
        "Test Auto-Response Subject",
        tracking_id,
        USER_CONFIG["name"]
    )
    
    # Confirm before sending
    print("\n===================== EMAIL PREVIEW =====================")
    print(f"To: {test_email}")
    print(f"Subject: {formatted_template['subject']}")
    print(f"Template: {template_type}")
    print(f"Body: {formatted_template['body'][:100]}...")
    print("=========================================================")
    
    confirm = input("\nSend this test email? (y/n): ").lower()
    if confirm != 'y':
        print("Test cancelled.")
        return
    
    # Send the test email
    sent_message_id = send_email_response(
        service,
        test_email,
        formatted_template["subject"],
        formatted_template["body"],
        formatted_template["html_body"]
    )
    
    if sent_message_id:
        # Record in database for analytics tracking
        logger.info(f"Test email sent successfully! Message ID: {sent_message_id}")
        logger.info(f"Tracking ID: {tracking_id}")
        
        try:
            import datetime
            current_time = datetime.datetime.now().isoformat()
            
            # Record as a test message
            cursor.execute(
                "INSERT INTO responded_emails VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    sent_message_id,
                    "",  # No thread ID for test
                    test_email,
                    "Test User",
                    "Test Auto-Response Subject",
                    template_type,
                    current_time,
                    tracking_id
                )
            )
            
            # Record analytics data
            record_analytics_data(conn, cursor, sent_message_id, test_email, template_type, tracking_id)
            
            conn.commit()
            logger.info("Response recorded in database for analytics tracking")
            print("\nTest completed successfully!")
            print("Please check your email inbox for the test message.")
            print("After opening the email, you can check analytics with:")
            print("python3 analytics_dashboard.py")
            
        except Exception as e:
            logger.error(f"Error recording data: {str(e)}")
    else:
        logger.error("Failed to send test email")
    
    conn.close()

if __name__ == "__main__":
    send_test_response()
