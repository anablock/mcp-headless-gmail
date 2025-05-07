#!/usr/bin/env python3
import sqlite3
import os
import sys

DB_PATH = "email_responses.db"

def fix_analytics_table():
    """Add missing columns to the email_analytics table."""
    print("Checking and fixing database schema...")
    
    try:
        # Connect to the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Check if the link_clicked column exists
        try:
            cursor.execute("SELECT link_clicked FROM email_analytics LIMIT 1")
            print("✅ link_clicked column already exists.")
        except sqlite3.OperationalError:
            print("Adding link_clicked column to email_analytics table...")
            cursor.execute("ALTER TABLE email_analytics ADD COLUMN link_clicked BOOLEAN DEFAULT 0")
            print("✅ Added link_clicked column")
        
        # Check if the first_link_click column exists
        try:
            cursor.execute("SELECT first_link_click FROM email_analytics LIMIT 1")
            print("✅ first_link_click column already exists.")
        except sqlite3.OperationalError:
            print("Adding first_link_click column to email_analytics table...")
            cursor.execute("ALTER TABLE email_analytics ADD COLUMN first_link_click TIMESTAMP")
            print("✅ Added first_link_click column")
        
        # Check if the link_clicks table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='link_clicks'")
        if not cursor.fetchone():
            print("Creating link_clicks table...")
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS link_clicks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tracking_id TEXT,
                click_time TIMESTAMP,
                FOREIGN KEY(tracking_id) REFERENCES email_analytics(tracking_id)
            )
            ''')
            print("✅ Created link_clicks table")
        else:
            print("✅ link_clicks table already exists")
        
        conn.commit()
        conn.close()
        
        print("\nDatabase schema has been updated successfully!")
        print("You can now run the analytics dashboard without errors.")
        
    except Exception as e:
        print(f"❌ Error fixing database: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    fix_analytics_table()
