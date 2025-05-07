#!/bin/bash
# Setup cron job for Gmail auto-response system

# Get the absolute path to the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AUTO_RESPONSE_SCRIPT="$PROJECT_DIR/auto_response.py"
LOG_FILE="$PROJECT_DIR/auto_response_cron.log"

# Make the Python scripts executable
chmod +x "$PROJECT_DIR/auto_response.py"
chmod +x "$PROJECT_DIR/tracking_server.py"
chmod +x "$PROJECT_DIR/analytics_dashboard.py"

# Create a temporary file for the new crontab
TEMP_CRON=$(mktemp)

# Export the current crontab
crontab -l > "$TEMP_CRON" 2>/dev/null || echo "# New crontab file" > "$TEMP_CRON"

# Check if our job is already in the crontab
if grep -q "auto_response.py" "$TEMP_CRON"; then
    echo "Cron job already exists. Skipping installation."
else
    # Add our cron job - run every 10 minutes
    echo "# Gmail Auto-Response script - runs every 10 minutes" >> "$TEMP_CRON"
    echo "*/10 * * * * cd $PROJECT_DIR && python3 $AUTO_RESPONSE_SCRIPT >> $LOG_FILE 2>&1" >> "$TEMP_CRON"
    
    # Install the new crontab
    crontab "$TEMP_CRON"
    echo "Cron job installed successfully. Will run every 10 minutes."
fi

# Clean up the temporary file
rm "$TEMP_CRON"

# Display instructions for the tracking server
echo ""
echo "============================================================"
echo "Email Auto-Response System Setup Complete"
echo "============================================================"
echo ""
echo "The auto-response script will run every 10 minutes."
echo ""
echo "To manually run the auto-response script:"
echo "  python3 $AUTO_RESPONSE_SCRIPT"
echo ""
echo "To start the tracking server (for analytics):"
echo "  python3 $PROJECT_DIR/tracking_server.py"
echo ""
echo "To view analytics:"
echo "  python3 $PROJECT_DIR/analytics_dashboard.py"
echo "  python3 $PROJECT_DIR/analytics_dashboard.py --charts  # Generate charts"
echo ""
echo "Make sure to set the following environment variables:"
echo "  export GOOGLE_CLIENT_ID=your_client_id"
echo "  export GOOGLE_CLIENT_SECRET=your_client_secret"
echo "  export GOOGLE_REFRESH_TOKEN=your_refresh_token"
echo ""
echo "============================================================"
