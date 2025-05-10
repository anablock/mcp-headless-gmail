import os
import sqlite3
import logging

logger = logging.getLogger("gmail_auto_response")

# Database configuration
def get_db_connection():
    """
    Get database connection based on environment
    In production (Heroku), use PostgreSQL
    In development, use SQLite
    """
    is_production = os.environ.get('HEROKU', False)
    
    if is_production:
        # For Heroku with PostgreSQL
        try:
            import psycopg2
            database_url = os.environ.get('DATABASE_URL')
            
            # Heroku's DATABASE_URL starts with postgres://, but psycopg2 needs postgresql://
            if database_url and database_url.startswith('postgres://'):
                database_url = database_url.replace('postgres://', 'postgresql://', 1)
                
            conn = psycopg2.connect(database_url)
            logger.info("Connected to PostgreSQL database")
            return conn
        except ImportError:
            logger.warning("psycopg2 not installed, falling back to SQLite")
            return sqlite3.connect(os.environ.get('DB_PATH', 'email_responses.db'))
        except Exception as e:
            logger.error(f"Error connecting to PostgreSQL: {str(e)}")
            logger.warning("Falling back to SQLite")
            return sqlite3.connect(os.environ.get('DB_PATH', 'email_responses.db'))
    else:
        # For local development with SQLite
        return sqlite3.connect(os.environ.get('DB_PATH', 'email_responses.db'))

def init_db():
    """
    Initialize the database with required tables
    Works with both SQLite and PostgreSQL
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create tables if they don't exist
    # Using syntax compatible with both SQLite and PostgreSQL
    
    # Table for email templates
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS email_templates (
        id SERIAL PRIMARY KEY,
        template_type TEXT NOT NULL,
        subject TEXT NOT NULL,
        body TEXT NOT NULL,
        html_body TEXT NOT NULL
    )
    ''')
    
    # Table for tracking responded emails
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS responded_emails (
        id SERIAL PRIMARY KEY,
        message_id TEXT UNIQUE NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        template_used TEXT,
        recipient_email TEXT
    )
    ''')
    
    # Table for tracking previous correspondents
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS previous_correspondents (
        id SERIAL PRIMARY KEY,
        email_address TEXT UNIQUE NOT NULL,
        first_contact_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_contact_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Table for analytics
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS response_analytics (
        id SERIAL PRIMARY KEY,
        response_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        template_type TEXT,
        tracking_id TEXT UNIQUE,
        opened BOOLEAN DEFAULT FALSE,
        clicked BOOLEAN DEFAULT FALSE,
        replied BOOLEAN DEFAULT FALSE
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")
