#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler
import sqlite3
import logging
import os
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tracking_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("email_tracking_server")

# Constants
DB_PATH = "email_responses.db"
PORT = 8000

class TrackingHandler(BaseHTTPRequestHandler):
    """Handler for tracking pixel and link clicks."""
    
    def do_GET(self):
        """Handle GET requests for tracking pixels and link redirects."""
        try:
            # Parse the URL
            parsed_path = urlparse(self.path)
            
            # Check if this is a tracking pixel request
            if parsed_path.path.startswith('/pixel/'):
                # Extract tracking ID from URL
                tracking_id = parsed_path.path.replace('/pixel/', '')
                logger.info(f"Tracking pixel loaded for ID: {tracking_id}")
                
                # Record the open in the database
                self._record_email_open(tracking_id)
                
                # Return a 1x1 transparent GIF
                self.send_response(200)
                self.send_header('Content-Type', 'image/gif')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.end_headers()
                
                # This is a 1x1 transparent GIF
                gif_data = bytes.fromhex('47494638396101000100800000000000ffffff21f90401000000002c00000000010001000002024401003b')
                self.wfile.write(gif_data)
                return
            
            # Check if this is a redirect request (for link tracking)
            elif parsed_path.path.startswith('/redirect/'):
                query_params = parse_qs(parsed_path.query)
                tracking_id = parsed_path.path.replace('/redirect/', '')
                destination_url = query_params.get('url', ['https://chat.anablock.com'])[0]
                
                logger.info(f"Link click for ID: {tracking_id}, redirecting to {destination_url}")
                
                # Record the link click
                self._record_link_click(tracking_id)
                
                # Redirect to the destination URL
                self.send_response(302)
                self.send_header('Location', destination_url)
                self.end_headers()
                return
            
            # Default - return 404
            self.send_response(404)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')
            
        except Exception as e:
            logger.error(f"Error handling request: {str(e)}")
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Internal Server Error')
    
    def _record_email_open(self, tracking_id):
        """Record that an email has been opened."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Check if this is the first time the email was opened
            cursor.execute(
                "SELECT opened FROM email_analytics WHERE tracking_id = ?",
                (tracking_id,)
            )
            result = cursor.fetchone()
            
            if result is None:
                logger.warning(f"Tracking ID not found in database: {tracking_id}")
                conn.close()
                return
                
            is_opened = result[0]
            current_time = datetime.now().isoformat()
            
            if not is_opened:
                # First open
                cursor.execute(
                    "UPDATE email_analytics SET opened = 1, first_opened_time = ?, open_count = 1 WHERE tracking_id = ?",
                    (current_time, tracking_id)
                )
            else:
                # Increment open count
                cursor.execute(
                    "UPDATE email_analytics SET open_count = open_count + 1 WHERE tracking_id = ?",
                    (tracking_id,)
                )
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            logger.error(f"Database error recording email open: {str(e)}")
    
    def _record_link_click(self, tracking_id):
        """Record that a link in the email was clicked."""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Add a link click record
            current_time = datetime.now().isoformat()
            cursor.execute(
                """
                INSERT INTO link_clicks (tracking_id, click_time) 
                VALUES (?, ?)
                """,
                (tracking_id, current_time)
            )
            
            # Update the email_analytics record
            cursor.execute(
                "UPDATE email_analytics SET link_clicked = 1, first_link_click = COALESCE(first_link_click, ?) WHERE tracking_id = ?",
                (current_time, tracking_id)
            )
            
            conn.commit()
            conn.close()
            
        except sqlite3.Error as e:
            logger.error(f"Database error recording link click: {str(e)}")

def ensure_tables_exist():
    """Ensure the analytics tables exist in the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Table for tracking link clicks
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS link_clicks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT,
            click_time TIMESTAMP,
            FOREIGN KEY(tracking_id) REFERENCES email_analytics(tracking_id)
        )
        ''')
        
        # Add additional columns to email_analytics if they don't exist
        try:
            cursor.execute("SELECT link_clicked FROM email_analytics LIMIT 1")
        except sqlite3.OperationalError:
            cursor.execute("ALTER TABLE email_analytics ADD COLUMN link_clicked BOOLEAN DEFAULT 0")
            cursor.execute("ALTER TABLE email_analytics ADD COLUMN first_link_click TIMESTAMP")
        
        conn.commit()
        conn.close()
        logger.info("Database tables verified")
        
    except sqlite3.Error as e:
        logger.error(f"Database initialization error: {str(e)}")
        raise

def run_server():
    """Run the tracking server."""
    try:
        # Make sure the necessary tables exist
        ensure_tables_exist()
        
        # Start the server
        server_address = ('', PORT)
        httpd = HTTPServer(server_address, TrackingHandler)
        logger.info(f"Starting tracking server on port {PORT}")
        httpd.serve_forever()
    except KeyboardInterrupt:
        logger.info("Stopping server due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {str(e)}")

if __name__ == "__main__":
    run_server()
