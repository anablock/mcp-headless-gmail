#!/usr/bin/env python3
import sqlite3
import argparse
from datetime import datetime, timedelta
import sys
import tabulate
import matplotlib.pyplot as plt
import numpy as np
import os

# Constants
DB_PATH = "email_responses.db"

def connect_to_db():
    """Connect to the SQLite database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Return rows as dictionaries
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {str(e)}")
        sys.exit(1)

def get_overall_stats(conn):
    """Get overall email response statistics."""
    cursor = conn.cursor()
    
    # Get total emails responded to
    cursor.execute("SELECT COUNT(*) as total FROM responded_emails")
    total_responses = cursor.fetchone()['total']
    
    # Get total emails opened
    cursor.execute("SELECT COUNT(*) as opened FROM email_analytics WHERE opened = 1")
    total_opened = cursor.fetchone()['opened']
    
    # Get total emails with link clicks
    cursor.execute("SELECT COUNT(*) as clicked FROM email_analytics WHERE link_clicked = 1")
    total_clicked = cursor.fetchone()['clicked']
    
    # Calculate open and click rates
    open_rate = (total_opened / total_responses) * 100 if total_responses > 0 else 0
    click_rate = (total_clicked / total_opened) * 100 if total_opened > 0 else 0
    
    stats = {
        "Total Auto-Responses": total_responses,
        "Total Opened": total_opened,
        "Total Link Clicks": total_clicked,
        "Open Rate": f"{open_rate:.1f}%",
        "Click Rate": f"{click_rate:.1f}%"
    }
    
    return stats

def get_template_performance(conn):
    """Get performance metrics by template type."""
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT 
        r.template_used,
        COUNT(*) as sent,
        SUM(CASE WHEN a.opened = 1 THEN 1 ELSE 0 END) as opened,
        SUM(CASE WHEN a.link_clicked = 1 THEN 1 ELSE 0 END) as clicked
    FROM 
        responded_emails r
    LEFT JOIN 
        email_analytics a ON r.tracking_id = a.tracking_id
    GROUP BY 
        r.template_used
    """)
    
    results = []
    for row in cursor.fetchall():
        template = row['template_used']
        sent = row['sent']
        opened = row['opened']
        clicked = row['clicked']
        
        open_rate = (opened / sent) * 100 if sent > 0 else 0
        click_rate = (clicked / opened) * 100 if opened > 0 else 0
        
        results.append({
            "Template": template,
            "Sent": sent,
            "Opened": opened,
            "Clicked": clicked,
            "Open Rate": f"{open_rate:.1f}%",
            "Click Rate": f"{click_rate:.1f}%"
        })
    
    return results

def get_recent_activity(conn, days=7):
    """Get recent email activity."""
    cursor = conn.cursor()
    
    # Calculate date cutoff
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor.execute("""
    SELECT 
        r.from_name,
        r.from_email,
        r.subject,
        r.template_used,
        r.response_time,
        CASE WHEN a.opened = 1 THEN 'Yes' ELSE 'No' END as opened,
        a.open_count,
        CASE WHEN a.link_clicked = 1 THEN 'Yes' ELSE 'No' END as clicked
    FROM 
        responded_emails r
    LEFT JOIN 
        email_analytics a ON r.tracking_id = a.tracking_id
    WHERE 
        r.response_time > ?
    ORDER BY 
        r.response_time DESC
    LIMIT 20
    """, (cutoff_date,))
    
    results = []
    for row in cursor.fetchall():
        # Format the response time
        response_time = datetime.fromisoformat(row['response_time']).strftime('%Y-%m-%d %H:%M')
        
        results.append({
            "Name": row['from_name'],
            "Email": row['from_email'],
            "Subject": row['subject'][:30] + ('...' if len(row['subject']) > 30 else ''),
            "Template": row['template_used'],
            "Sent": response_time,
            "Opened": row['opened'],
            "Open Count": row['open_count'] or 0,
            "Clicked": row['clicked']
        })
    
    return results

def generate_charts(conn, output_dir='analytics_charts'):
    """Generate charts visualizing email performance."""
    # Ensure the output directory exists
    os.makedirs(output_dir, exist_ok=True)
    
    cursor = conn.cursor()
    
    # Chart 1: Template Performance Comparison
    cursor.execute("""
    SELECT 
        r.template_used,
        COUNT(*) as sent,
        SUM(CASE WHEN a.opened = 1 THEN 1 ELSE 0 END) as opened,
        SUM(CASE WHEN a.link_clicked = 1 THEN 1 ELSE 0 END) as clicked
    FROM 
        responded_emails r
    LEFT JOIN 
        email_analytics a ON r.tracking_id = a.tracking_id
    GROUP BY 
        r.template_used
    """)
    
    templates = []
    sent_counts = []
    opened_counts = []
    clicked_counts = []
    
    for row in cursor.fetchall():
        templates.append(row['template_used'])
        sent_counts.append(row['sent'])
        opened_counts.append(row['opened'])
        clicked_counts.append(row['clicked'])
    
    # Create bar chart
    if templates:
        plt.figure(figsize=(10, 6))
        x = np.arange(len(templates))
        width = 0.25
        
        plt.bar(x - width, sent_counts, width, label='Sent')
        plt.bar(x, opened_counts, width, label='Opened')
        plt.bar(x + width, clicked_counts, width, label='Clicked')
        
        plt.xlabel('Template Type')
        plt.ylabel('Count')
        plt.title('Email Performance by Template')
        plt.xticks(x, templates)
        plt.legend()
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/template_performance.png")
        print(f"Chart saved to {output_dir}/template_performance.png")
    
    # Chart 2: Daily Activity
    cursor.execute("""
    SELECT 
        DATE(response_time) as date,
        COUNT(*) as count
    FROM 
        responded_emails
    GROUP BY 
        DATE(response_time)
    ORDER BY 
        date ASC
    LIMIT 30
    """)
    
    dates = []
    counts = []
    
    for row in cursor.fetchall():
        dates.append(row['date'])
        counts.append(row['count'])
    
    if dates:
        plt.figure(figsize=(12, 6))
        plt.plot(dates, counts, marker='o', linestyle='-')
        plt.xlabel('Date')
        plt.ylabel('Number of Auto-Responses')
        plt.title('Daily Auto-Response Activity')
        plt.xticks(rotation=45)
        plt.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/daily_activity.png")
        print(f"Chart saved to {output_dir}/daily_activity.png")
    
    # Chart 3: Open Rate Over Time
    cursor.execute("""
    SELECT 
        DATE(r.response_time) as date,
        COUNT(*) as sent,
        SUM(CASE WHEN a.opened = 1 THEN 1 ELSE 0 END) as opened
    FROM 
        responded_emails r
    LEFT JOIN 
        email_analytics a ON r.tracking_id = a.tracking_id
    GROUP BY 
        DATE(r.response_time)
    ORDER BY 
        date ASC
    LIMIT 30
    """)
    
    dates = []
    open_rates = []
    
    for row in cursor.fetchall():
        if row['sent'] > 0:
            dates.append(row['date'])
            open_rates.append((row['opened'] / row['sent']) * 100)
    
    if dates:
        plt.figure(figsize=(12, 6))
        plt.plot(dates, open_rates, marker='o', linestyle='-', color='green')
        plt.xlabel('Date')
        plt.ylabel('Open Rate (%)')
        plt.title('Email Open Rate Over Time')
        plt.xticks(rotation=45)
        plt.grid(True, linestyle='--', alpha=0.7)
        
        plt.tight_layout()
        plt.savefig(f"{output_dir}/open_rate_trend.png")
        print(f"Chart saved to {output_dir}/open_rate_trend.png")

def main():
    parser = argparse.ArgumentParser(description='Email Auto-Response Analytics Dashboard')
    parser.add_argument('--charts', action='store_true', help='Generate analytics charts')
    parser.add_argument('--recent', type=int, default=7, help='Days of recent activity to show (default: 7)')
    args = parser.parse_args()
    
    conn = connect_to_db()
    
    # Display overall stats
    print("\n===== EMAIL AUTO-RESPONSE ANALYTICS =====\n")
    
    overall_stats = get_overall_stats(conn)
    print("OVERALL METRICS:")
    for key, value in overall_stats.items():
        print(f"{key}: {value}")
    
    # Display template performance
    template_stats = get_template_performance(conn)
    print("\nTEMPLATE PERFORMANCE:")
    if template_stats:
        headers = template_stats[0].keys()
        rows = [list(stat.values()) for stat in template_stats]
        print(tabulate.tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        print("No template data available")
    
    # Display recent activity
    recent_activity = get_recent_activity(conn, days=args.recent)
    print(f"\nRECENT ACTIVITY (LAST {args.recent} DAYS):")
    if recent_activity:
        headers = recent_activity[0].keys()
        rows = [list(activity.values()) for activity in recent_activity]
        print(tabulate.tabulate(rows, headers=headers, tablefmt="grid"))
    else:
        print(f"No activity in the last {args.recent} days")
    
    # Generate charts if requested
    if args.charts:
        print("\nGenerating analytics charts...")
        generate_charts(conn)
    
    conn.close()

if __name__ == "__main__":
    main()
