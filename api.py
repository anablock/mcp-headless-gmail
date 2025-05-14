#!/usr/bin/env python3
from fastapi import FastAPI, BackgroundTasks, HTTPException, Body, Depends
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import uvicorn
import json
import os
import time
import logging
from datetime import datetime

# Import the auto_response module
import auto_response

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("api.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("gmail_auto_response_api")

# Create FastAPI app
app = FastAPI(title="Gmail Auto Response API")

# Configure CORS for Next.js integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models for API requests/responses
class AutoResponseConfigModel(BaseModel):
    max_responses: int = Field(default=20, description="Maximum number of auto-responses to send")
    business_hours_only: bool = Field(default=True, description="Only send during business hours")

class EmailTemplateModel(BaseModel):
    template_type: str = Field(..., description="Type of template (sales, meeting, general)")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Plain text email body")
    html_body: str = Field(..., description="HTML email body")

class ResponseResult(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None

# API Routes
@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint to check if the API is running"""
    return {"status": "Gmail Auto Response API is running"}

@app.post("/test-credentials")
async def test_credentials(request_data: Dict[str, Any]):
    """Test endpoint to validate OAuth credentials without accessing Gmail"""
    logger.debug(f"Received test-credentials request")
    try:
        # Extract auth credentials
        auth = request_data.get("auth", {})
        logger.debug(f"Auth data received: client_id exists: {bool(auth.get('client_id'))}, "
                  f"client_secret exists: {bool(auth.get('client_secret'))}, "
                  f"refresh_token exists: {bool(auth.get('refresh_token'))}")
        
        # Return detailed information about the credentials
        return {
            "status": "success",
            "credentials_received": {
                "client_id": bool(auth.get("client_id")),
                "client_secret": bool(auth.get("client_secret")),
                "refresh_token": bool(auth.get("refresh_token")),
                "client_id_length": len(auth.get("client_id", "")) if auth.get("client_id") else 0,
                "client_secret_length": len(auth.get("client_secret", "")) if auth.get("client_secret") else 0,
                "refresh_token_length": len(auth.get("refresh_token", "")) if auth.get("refresh_token") else 0
            }
        }
    except Exception as e:
        logger.error(f"Error in test-credentials: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

# API Debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# MCP Protocol Compatibility Endpoints
@app.post("/messages/list")
async def messages_list(request_data: Dict[str, Any]):
    """MCP protocol endpoint for listing messages"""
    logger.debug(f"Received messages/list request: {request_data}")
    try:
        # Extract auth credentials
        auth = request_data.get("auth", {})
        logger.debug(f"Auth data: client_id exists: {bool(auth.get('client_id'))}, refresh_token exists: {bool(auth.get('refresh_token'))}")
        
        # Validate required credentials
        if not auth.get("client_id") or not auth.get("client_secret") or not auth.get("refresh_token"):
            logger.error(f"Missing required credentials. client_id: {bool(auth.get('client_id'))}, "
                      f"client_secret: {bool(auth.get('client_secret'))}, "
                      f"refresh_token: {bool(auth.get('refresh_token'))}")
            return JSONResponse({"error": "Missing required credentials"}, status_code=401)
        
        # Set environment variables for auto_response
        os.environ["GOOGLE_CLIENT_ID"] = auth.get("client_id")
        os.environ["GOOGLE_CLIENT_SECRET"] = auth.get("client_secret")
        os.environ["GOOGLE_REFRESH_TOKEN"] = auth.get("refresh_token")
        
        # Get access token
        logger.debug("Getting access token...")
        access_token = auto_response.refresh_access_token()
        if not access_token:
            logger.error("Failed to refresh access token")
            return JSONResponse({"error": "Failed to refresh access token"}, status_code=401)
        
        # Get recent emails
        max_results = request_data.get("max_results", 20)
        logger.debug(f"Getting {max_results} recent emails...")
        result = auto_response.get_recent_emails(access_token, max_results)
        
        # Handle the response structure from get_recent_emails
        if "error" in result:
            logger.error(f"Error getting emails: {result['error']}")
            return JSONResponse({"error": result["error"]}, status_code=500)
            
        # Extract emails from the result
        emails = result.get("emails", [])
        
        logger.debug(f"Returning {len(emails)} emails")
        return {"messages": emails}
    except Exception as e:
        logger.error(f"Error in messages/list: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/messages/get")
async def messages_get(request_data: Dict[str, Any]):
    """MCP protocol endpoint for getting a specific message"""
    logger.debug(f"Received messages/get request: {request_data}")
    try:
        # Extract auth credentials from request
        auth = request_data.get("auth", {})
        message_id = request_data.get("id")
        
        logger.debug(f"Message ID: {message_id}")
        if not message_id:
            logger.error("Missing message ID")
            return JSONResponse({"error": "Missing message ID"}, status_code=400)
        
        # Validate required credentials
        if not auth.get("client_id") or not auth.get("client_secret") or not auth.get("refresh_token"):
            logger.error(f"Missing required credentials. client_id: {bool(auth.get('client_id'))}, "
                      f"client_secret: {bool(auth.get('client_secret'))}, "
                      f"refresh_token: {bool(auth.get('refresh_token'))}")
            return JSONResponse({"error": "Missing required credentials"}, status_code=401)
            
        # Set environment variables for auto_response
        os.environ["GOOGLE_CLIENT_ID"] = auth.get("client_id")
        os.environ["GOOGLE_CLIENT_SECRET"] = auth.get("client_secret")
        os.environ["GOOGLE_REFRESH_TOKEN"] = auth.get("refresh_token")
        
        # Get access token
        logger.debug("Getting access token...")
        access_token = auto_response.refresh_access_token()
        if not access_token:
            logger.error("Failed to refresh access token")
            return JSONResponse({"error": "Failed to refresh access token"}, status_code=401)
        
        # Get the message using our direct implementation
        logger.debug(f"Getting message with ID: {message_id}")
        message_data = auto_response.get_email_message_direct(access_token, message_id)
        
        if not message_data:
            logger.error(f"Failed to retrieve message with ID: {message_id}")
            return JSONResponse({"error": "Failed to retrieve message"}, status_code=404)
        
        logger.debug("Successfully retrieved message data")
        return {"message": message_data}
    except Exception as e:
        logger.error(f"Error in messages/get: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/messages/send")
async def messages_send(request_data: Dict[str, Any]):
    """MCP protocol endpoint for sending a message"""
    logger.debug(f"Received messages/send request: {request_data}")
    try:
        # Extract auth credentials from request
        auth = request_data.get("auth", {})
        to_email = request_data.get("to")
        subject = request_data.get("subject")
        body = request_data.get("body")
        html_body = request_data.get("html_body", body)
        thread_id = request_data.get("thread_id")
        
        logger.debug(f"Email params: to={to_email}, subject={subject}, thread_id={thread_id}")
        if not to_email or not subject or not body:
            logger.error("Missing required email parameters")
            return JSONResponse({"error": "Missing required parameters"}, status_code=400)
        
        # Validate required credentials
        if not auth.get("client_id") or not auth.get("client_secret") or not auth.get("refresh_token"):
            logger.error(f"Missing required credentials. client_id: {bool(auth.get('client_id'))}, "
                      f"client_secret: {bool(auth.get('client_secret'))}, "
                      f"refresh_token: {bool(auth.get('refresh_token'))}")
            return JSONResponse({"error": "Missing required credentials"}, status_code=401)
            
        # Parse to_email for name and email
        to_name = ""
        if "<" in to_email and ">" in to_email:
            parts = to_email.split("<")
            to_name = parts[0].strip()
            to_email = parts[1].replace(">", "").strip()
            logger.debug(f"Parsed email: name={to_name}, email={to_email}")
        
        # Set environment variables for auto_response
        os.environ["GOOGLE_CLIENT_ID"] = auth.get("client_id")
        os.environ["GOOGLE_CLIENT_SECRET"] = auth.get("client_secret")
        os.environ["GOOGLE_REFRESH_TOKEN"] = auth.get("refresh_token")
        
        # Get access token
        logger.debug("Getting access token...")
        access_token = auto_response.refresh_access_token()
        if not access_token:
            logger.error("Failed to refresh access token")
            return JSONResponse({"error": "Failed to refresh access token"}, status_code=401)
        
        # Send email
        logger.debug("Sending email...")
        result = auto_response.send_email(
            access_token=access_token,
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body=body,
            html_body=html_body,
            thread_id=thread_id
        )
        
        if not result:
            logger.error("Failed to send email")
            return JSONResponse({"error": "Failed to send email"}, status_code=500)
        
        logger.debug(f"Email sent successfully: {result}")
        return {"result": "success", "message_id": result.get("id", "unknown")}
    except Exception as e:
        logger.error(f"Error in messages/send: {str(e)}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/run-auto-response", response_model=ResponseResult)
async def run_auto_response(
    background_tasks: BackgroundTasks,
    request_data: Dict[str, Any] = Body(...)
):
    """
    Trigger the auto-response process to check emails and send responses.
    This runs asynchronously in the background.
    
    Expects a request with both configuration parameters and auth credentials:
    {
        "max_responses": 20,
        "business_hours_only": true,
        "auth": {
            "client_id": "...",
            "client_secret": "...",
            "refresh_token": "..."
        }
    }
    """
    try:
        logger.info(f"Received run-auto-response request with data: {request_data.keys()}")
        
        # Extract auth credentials just like other endpoints
        auth = request_data.get("auth", {})
        logger.info(f"Auth data received: client_id exists: {bool(auth.get('client_id'))}, "
                  f"client_secret exists: {bool(auth.get('client_secret'))}, "
                  f"refresh_token exists: {bool(auth.get('refresh_token'))}")
        
        # Log truncated credentials for debugging (only first few chars)
        client_id = auth.get("client_id", "")
        client_secret = auth.get("client_secret", "")
        refresh_token = auth.get("refresh_token", "")
        
        logger.debug(f"Client ID prefix: {client_id[:5]}... (length: {len(client_id)})")
        logger.debug(f"Client secret prefix: {client_secret[:5]}... (length: {len(client_secret)})")
        logger.debug(f"Refresh token prefix: {refresh_token[:5]}... (length: {len(refresh_token)})")
        
        # Validate required credentials
        if not client_id or not client_secret or not refresh_token:
            logger.error(f"Missing required credentials. client_id: {bool(client_id)}, "
                      f"client_secret: {bool(client_secret)}, "
                      f"refresh_token: {bool(refresh_token)}")
            return JSONResponse({
                "success": False,
                "error": "Missing required credentials", 
                "details": {
                    "client_id_present": bool(client_id),
                    "client_secret_present": bool(client_secret),
                    "refresh_token_present": bool(refresh_token)
                }
            }, status_code=401)
        
        # Set environment variables for auto_response
        os.environ["GOOGLE_CLIENT_ID"] = client_id
        os.environ["GOOGLE_CLIENT_SECRET"] = client_secret
        os.environ["GOOGLE_REFRESH_TOKEN"] = refresh_token
        
        # Initialize config with defaults if not provided
        max_responses = request_data.get("max_responses", 20)
        business_hours_only = request_data.get("business_hours_only", True)
        
        logger.info(f"Configured auto-response with max_responses={max_responses}, "
                 f"business_hours_only={business_hours_only}")
        
        # Update USER_CONFIG based on provided configuration
        auto_response.USER_CONFIG["max_responses_per_run"] = max_responses
        auto_response.USER_CONFIG["business_hours_only"] = business_hours_only
        
        # Get access token to validate credentials before scheduling the task
        logger.info("Attempting to refresh access token to validate credentials")
        try:
            access_token = auto_response.refresh_access_token()
            if not access_token:
                logger.error("Failed to refresh access token - empty token returned")
                return JSONResponse({
                    "success": False,
                    "error": "Failed to refresh access token", 
                    "message": "Authentication failed. Please verify your Google credentials."
                }, status_code=401)
        except Exception as token_error:
            logger.error(f"Access token refresh error: {str(token_error)}")
            return JSONResponse({
                "success": False,
                "error": "token_refresh_error", 
                "message": f"Failed to refresh Google access token: {str(token_error)}"
            }, status_code=401)
            
        # Run the main function in the background
        logger.info("Starting auto-response process in background task")
        background_tasks.add_task(auto_response.main)
        
        return {
            "success": True,
            "message": "Auto-response process started in the background",
            "details": {
                "max_responses": max_responses,
                "business_hours_only": business_hours_only
            }
        }
    except Exception as e:
        logger.error(f"Error starting auto-response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start auto-response process: {str(e)}")

@app.post("/send-custom-response", response_model=ResponseResult)
async def send_custom_response(
    to_email: str = Body(...),
    to_name: str = Body(...),
    subject: str = Body(...),
    body: str = Body(...),
    html_body: str = Body(...),
    thread_id: Optional[str] = Body(None)
):
    """
    Send a custom auto-response email without going through the filtering process
    """
    try:
        # Refresh token first
        access_token = auto_response.refresh_access_token()
        if not access_token:
            raise ValueError("Failed to refresh access token")
        
        # Send the email
        result = auto_response.send_email(
            access_token=access_token,
            to_email=to_email,
            to_name=to_name,
            subject=subject,
            body=body,
            html_body=html_body,
            thread_id=thread_id
        )
        
        if not result:
            raise ValueError("Failed to send email")
        
        return {
            "success": True,
            "message": f"Custom response sent to {to_email}",
            "details": {
                "to": f"{to_name} <{to_email}>",
                "subject": subject,
                "message_id": result.get("id", "unknown")
            }
        }
    except Exception as e:
        logger.error(f"Error sending custom response: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send custom response: {str(e)}")

@app.post("/add-template", response_model=ResponseResult)
async def add_template(
    template: EmailTemplateModel = Body(...)
):
    """
    Add or update an email template
    """
    try:
        # Save template to the database using the new function
        auto_response.save_template_to_db(
            template.template_type,
            template.subject,
            template.body,
            template.html_body
        )
        
        return {
            "success": True,
            "message": f"Template '{template.template_type}' added/updated successfully",
            "details": {
                "template_type": template.template_type
            }
        }
    except Exception as e:
        logger.error(f"Error adding template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add template: {str(e)}")

@app.get("/get-template/{template_type}", response_model=Optional[EmailTemplateModel])
async def get_template(template_type: str):
    """
    Get a specific email template
    """
    try:
        if template_type not in auto_response.EMAIL_TEMPLATES:
            raise HTTPException(status_code=404, detail=f"Template '{template_type}' not found")
        
        template = auto_response.EMAIL_TEMPLATES[template_type]
        return EmailTemplateModel(
            template_type=template_type,
            subject=template.get("subject", ""),
            body=template.get("body", ""),
            html_body=template.get("html_body", "")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve template: {str(e)}")

@app.get("/get-all-templates", response_model=list[EmailTemplateModel])
async def get_all_templates():
    """
    Get all email templates
    """
    try:
        # Get all templates from the database
        templates = auto_response.get_all_templates_from_db()
        
        # Convert to response model format
        result = []
        for template in templates:
            result.append(EmailTemplateModel(
                template_type=template["template_type"],
                subject=template["subject"],
                body=template["body"],
                html_body=template["html_body"]
            ))
        
        return result
    except Exception as e:
        logger.error(f"Error retrieving all templates: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve templates: {str(e)}")

@app.get("/config")
async def get_config():
    """
    Get user configuration including default template setting
    """
    try:
        # Return only the configuration values that should be exposed to the frontend
        safe_config = {
            "default_template": auto_response.get_default_template(),
            "smart_template_selection": auto_response.USER_CONFIG.get("smart_template_selection", True),
            "domains_to_exclude": auto_response.USER_CONFIG.get("domains_to_exclude", [])
        }
        return safe_config
    except Exception as e:
        logger.error(f"Error getting configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")

@app.post("/set-default-template", response_model=Dict[str, Any])
async def set_default_template(template_type: str = Body(...)):
    """
    Set the default template for auto-responses
    """
    try:
        result = auto_response.set_default_template(template_type)
        return {
            "success": True,
            "message": f"Default template set to '{template_type}'",
            "template": template_type
        }
    except Exception as e:
        logger.error(f"Error setting default template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to set default template: {str(e)}")

@app.delete("/delete-template/{template_type}", response_model=ResponseResult)
async def delete_template(template_type: str):
    """
    Delete an email template
    """
    try:
        conn = sqlite3.connect(auto_response.DB_PATH)
        cursor = conn.cursor()
        
        # Check if template exists
        cursor.execute("SELECT COUNT(*) FROM email_templates WHERE template_type = ?", (template_type,))
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            raise HTTPException(status_code=404, detail=f"Template '{template_type}' not found")
        
        # Delete template from database
        cursor.execute("DELETE FROM email_templates WHERE template_type = ?", (template_type,))
        conn.commit()
        
        # Remove from in-memory templates if it exists
        if template_type in auto_response.EMAIL_TEMPLATES:
            del auto_response.EMAIL_TEMPLATES[template_type]
        
        conn.close()
        
        return {
            "success": True,
            "message": f"Template '{template_type}' deleted successfully"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")


@app.get("/get-analytics", response_model=Dict[str, Any])
async def get_analytics():
    """
    Get analytics data about sent auto-responses
    """
    try:
        conn = auto_response.init_db()
        cursor = conn.cursor()
        
        # Get count of responded emails
        cursor.execute("SELECT COUNT(*) FROM responded_emails")
        total_responses = cursor.fetchone()[0]
        
        # Get count by template type
        cursor.execute("SELECT template_used, COUNT(*) FROM responded_emails GROUP BY template_used")
        template_counts = {row[0]: row[1] for row in cursor.fetchall()}
        
        # Get open rates
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN opened = 1 THEN 1 ELSE 0 END) as opened_count,
                COUNT(*) as total_count
            FROM email_analytics
        """)
        analytics = cursor.fetchone()
        open_count = analytics[0] or 0
        total_tracked = analytics[1] or 0
        open_rate = (open_count / total_tracked) * 100 if total_tracked > 0 else 0
        
        conn.close()
        
        return {
            "success": True,
            "total_responses": total_responses,
            "template_counts": template_counts,
            "open_rate": round(open_rate, 2),
            "tracked_emails": total_tracked,
            "opened_emails": open_count
        }
    except Exception as e:
        logger.error(f"Error retrieving analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve analytics: {str(e)}")

# Main entrypoint for running the API server
if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("api:app", host="0.0.0.0", port=port, reload=False)
