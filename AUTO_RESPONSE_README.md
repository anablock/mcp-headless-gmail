# Gmail Auto-Response System

A complete Gmail auto-response system built using the MCP Headless Gmail server. This system provides intelligent email filtering, customized response templates, and detailed analytics.

## System Components

1. **MCP Headless Gmail Server**: Core component that interfaces with Gmail API
2. **Auto-Response Script**: Processes emails and sends intelligent responses
3. **Tracking Server**: Captures email open and link click analytics
4. **Analytics Dashboard**: Visualizes performance metrics
5. **Cron Job Setup**: Automates the system execution

## Features

### Smart Email Filtering
- Classifies emails by content analysis (sales, meetings, general)
- Applies business rules (excluded domains, business hours)
- Prevents responding to previous correspondents

### Multiple Response Templates
- Customized responses based on email type
- Dynamic personalization
- Custom tracking links for each response

#### Template Selection Process

The email template selection process works through a smart classification system defined in the `should_respond_to_email()` function. Here's how templates are selected:

### Smart Template Selection

When `USER_CONFIG.get("smart_template_selection", True)` is enabled, the system:

1. Analyzes the combined text of the email subject and body
2. Checks for keyword matches against predefined filters:

```python
# Checks for sales-related keywords
for keyword in EMAIL_FILTERS["sales"]:
    if keyword.lower() in combined_text:
        return True, "sales"

# Checks for meeting-related keywords
for keyword in EMAIL_FILTERS["meeting"]:
    if keyword.lower() in combined_text:
        return True, "meeting"
```

### Default Template Selection

If no specific template is matched through keywords (or if smart selection is disabled):

```python
# Use the default template if no keywords match or smart selection is disabled
default_template = USER_CONFIG.get("default_template", "general")
return True, default_template
```

The default template is determined by:

1. The `default_template` value in `USER_CONFIG`
2. Falls back to "general" if not specified

### Available Templates

The system includes three standard templates:

1. **General template** - Used for most correspondence
2. **Meeting template** - Used for meeting-related emails
3. **Sales template** - Used for sales inquiries

Templates can be customized through the web interface or by editing the database directly.

### Email Analytics
- Tracks email opens using tracking pixels
- Records link clicks
- Generates performance reports and visualizations
- Compares template effectiveness

## Setup Instructions

### 1. Configure MCP Server in Windsurf

Add the following to your Windsurf MCP configuration:

```json
{
  "mcpServers": {
    "gmail": {
      "command": "npx",
      "args": [
        "-y",
        "@peakmojo/mcp-server-headless-gmail"
      ]
    }
  }
}
```

### 2. Set Up Google API Credentials

1. Create a project in Google Cloud Console
2. Enable the Gmail API
3. Create OAuth credentials (Web application type)
4. Complete the OAuth flow to get refresh token

Store credentials as environment variables:
```bash
export GOOGLE_CLIENT_ID=your_client_id
export GOOGLE_CLIENT_SECRET=your_client_secret
export GOOGLE_REFRESH_TOKEN=your_refresh_token
```

### 3. Install Dependencies

```bash
pip install sqlite3 tabulate matplotlib numpy
```

### 4. Configure the Auto-Response System

Modify the `USER_CONFIG` in `auto_response.py` to match your preferences:

```python
USER_CONFIG = {
    "name": "Your Name",  # Your name for email signatures
    "domains_to_exclude": ["yourdomain.com", "gmail.com"],
    "exclude_previous_correspondents": True,
    "business_hours_only": True,
    "business_hours": {
        "start": 9,  # 9 AM
        "end": 17    # 5 PM
    },
    "max_responses_per_run": 20,
}
```

You can also customize the email templates in the `EMAIL_TEMPLATES` dictionary.

### 5. Install the Cron Job

Make the setup script executable and run it:

```bash
chmod +x setup_cron.sh
./setup_cron.sh
```

This will install a cron job that runs the auto-response script every 10 minutes.

### 6. Start the Tracking Server (Optional)

For analytics tracking, start the tracking server:

```bash
python3 tracking_server.py
```

Note: For production use, you'll need to set up a proper web server with SSL and a domain.

## Usage

### Running Manually

To manually run the auto-response script:
```bash
python3 auto_response.py
```

### Viewing Analytics

To view basic analytics:
```bash
python3 analytics_dashboard.py
```

To generate analytics charts:
```bash
python3 analytics_dashboard.py --charts
```

## System Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│                 │    │                 │    │                 │
│  Cron Job       │───▶│  Auto-Response  │───▶│  MCP Headless   │
│  (Every 10min)  │    │  Script         │    │  Gmail Server   │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │                 │    │                 │
                       │  SQLite         │◀───┤  Tracking       │
                       │  Database       │    │  Server         │
                       │                 │    │                 │
                       └─────────────────┘    └─────────────────┘
                              │                      ▲
                              ▼                      │
                       ┌─────────────────┐          │
                       │                 │          │
                       │  Analytics      │          │
                       │  Dashboard      │          │
                       │                 │          │
                       └─────────────────┘          │
                                                    │
                                                 Email
                                                 Opens
```

## Customization

### Adding New Email Templates

Edit the `EMAIL_TEMPLATES` dictionary in `auto_response.py` to add new templates:

```python
EMAIL_TEMPLATES = {
    "your_new_template": {
        "subject": "Subject line",
        "body": "Plain text body",
        "html_body": "<p>HTML body</p>"
    },
    # ...
}
```

### Modifying Smart Filtering Rules

Edit the `EMAIL_FILTERS` dictionary to adjust filtering keywords:

```python
EMAIL_FILTERS = {
    "your_category": [
        "keyword1", "keyword2", "keyword3"
    ],
    # ...
}
```

## Security Considerations

- Store API credentials securely (environment variables or secret manager)
- Set up proper access controls for the database
- Add SSL to the tracking server for production use
- Regularly rotate OAuth credentials
- Monitor logs for unauthorized access attempts

## Troubleshooting

Check the log files for errors:
- `auto_response.log`: Main application logs
- `auto_response_cron.log`: Cron execution logs
- `tracking_server.log`: Tracking server logs

Common issues:
1. **Authentication errors**: Verify your Google API credentials
2. **Database errors**: Check permissions on the database file
3. **Cron not running**: Verify cron service is active

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT
