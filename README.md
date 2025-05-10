# MCP Headless Gmail Server

[![npm version](https://img.shields.io/npm/v/@peakmojo/mcp-server-headless-gmail.svg)](https://www.npmjs.com/package/@peakmojo/mcp-server-headless-gmail) [![Docker Pulls](https://img.shields.io/docker/pulls/buryhuang/mcp-headless-gmail)](https://hub.docker.com/r/buryhuang/mcp-headless-gmail) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A MCP (Model Context Protocol) server that provides get, send Gmails without local credential or token setup.

![Headless Gmail Server MCP server](https://glama.ai/mcp/servers/@baryhuang/mcp-headless-gmail/badge)

## Why MCP Headless Gmail Server?

### Critical Advantages

- **Headless & Remote Operation**: Unlike other MCP Gmail solutions that require running outside of docker and local file access, this server can run completely headless in remote environments with no browser no local file access.
- **Decoupled Architecture**: Any client can complete the OAuth flow independently, then pass credentials as context to this MCP server, creating a complete separation between credential storage and server implementation.

### Nice but not critical

- **Focused Functionality**: In many use cases, especially for marketing applications, only Gmail access is needed without additional Google services like Calendar, making this focused implementation ideal.
- **Docker-Ready**: Designed with containerization in mind for a well-isolated, environment-independent, one-click setup.
- **Reliable Dependencies**: Built on the well-maintained google-api-python-client library.

## Features

- Get most recent emails from Gmail with the first 1k characters of the body
- Get full email body content in 1k chunks using offset parameter
- Send emails through Gmail
- Refresh access tokens separately
- Automatic refresh token handling

## Prerequisites

- Python 3.10 or higher
- Google API credentials (client ID, client secret, access token, and refresh token)

## Credential Management

### Obtaining Google OAuth Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a project (or select an existing one)
3. Enable the Gmail API for your project
4. Create OAuth 2.0 credentials (OAuth client ID)
   - Application type: Web application
   - Authorized redirect URIs: Add a URI where you'll handle the OAuth callback
5. Note your Client ID and Client Secret

### Template-Based Configuration

This project provides several template files to help you manage credentials securely:

1. **Environment Variables (.env)**: Copy `.env.template` to `.env` and add your credentials

   ```bash
   cp .env.template .env
   # Then edit .env with your credentials
   ```

2. **Shell Script**: Use `set_credentials.sh.template` to create a script for setting credentials

   ```bash
   cp set_credentials.sh.template set_credentials.sh
   chmod +x set_credentials.sh
   # Edit set_credentials.sh with your credentials
   source ./set_credentials.sh
   ```

3. **Python Script**: Use `get_token_from_json.py.template` for retrieving tokens from credential files

   ```bash
   cp get_token_from_json.py.template get_token_from_json.py
   # Edit get_token_from_json.py with your credentials
   ```

### Security Best Practices

- **Never commit credentials to version control**
- All credential files (`.env`, `set_credentials.sh`, etc.) are in `.gitignore`
- Use environment variables whenever possible instead of hardcoding credentials
- For production, consider using a secrets manager service

## Installation

```bash
# Clone the repository
git clone https://github.com/baryhuang/mcp-headless-gmail.git
cd mcp-headless-gmail

# Install dependencies
pip install -e .

# Set up your credentials using one of the template methods above
```

## Docker

### Building the Docker Image

```bash
# Build the Docker image
docker build -t mcp-headless-gmail .
```

## Usage with Claude Desktop

You can configure Claude Desktop to use the Docker image by adding the following to your Claude configuration:

docker:

```json
{
  "mcpServers": {
    "gmail": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "buryhuang/mcp-headless-gmail:latest"
      ]
    }
  }
}
```

npm version:

```json
{
  "mcpServers": {
    "gmail": {
      "command": "npx",
      "args": [
        "@peakmojo/mcp-server-headless-gmail"
      ]
    }
  }
}
```

## Cross-Platform Publishing

To publish the Docker image for multiple platforms, you can use the `docker buildx` command. Follow these steps:

1. **Create a new builder instance** (if you haven't already):

   ```bash
   docker buildx create --use
   ```

2. **Build and push the image for multiple platforms**:

   ```bash
   docker buildx build --platform linux/amd64,linux/arm64,linux/arm/v7 -t buryhuang/mcp-headless-gmail:latest --push .
   ```

3. **Verify the image is available for the specified platforms**:

   ```bash
   docker buildx imagetools inspect buryhuang/mcp-headless-gmail:latest
   ```

## Usage

The server provides Gmail functionality through MCP tools. Authentication handling is simplified with a dedicated token refresh tool.

### Starting the Server

```bash
mcp-server-headless-gmail
```

### Using the Tools

When using an MCP client like Claude, you have two main ways to handle authentication:

#### Refreshing Tokens (First Step or When Tokens Expire)

If you have both access and refresh tokens:

```json
{
  "google_access_token": "your_access_token",
  "google_refresh_token": "your_refresh_token",
  "google_client_id": "your_client_id",
  "google_client_secret": "your_client_secret"
}
```

If your access token has expired, you can refresh with just the refresh token:

```json
{
  "google_refresh_token": "your_refresh_token",
  "google_client_id": "your_client_id",
  "google_client_secret": "your_client_secret"
}
```

This will return a new access token and its expiration time, which you can use for subsequent calls.

#### Getting Recent Emails

Retrieves recent emails with the first 1k characters of each email body:

```json
{
  "google_access_token": "your_access_token",
  "max_results": 5,
  "unread_only": false
}
```

Response includes:

- Email metadata (id, threadId, from, to, subject, date, etc.)
- First 1000 characters of the email body
- `body_size_bytes`: Total size of the email body in bytes
- `contains_full_body`: Boolean indicating if the entire body is included (true) or truncated (false)

#### Getting Full Email Body Content

For emails with bodies larger than 1k characters, you can retrieve the full content in chunks:

```json
{
  "google_access_token": "your_access_token",
  "message_id": "message_id_from_get_recent_emails",
  "offset": 0
}
```

You can also get email content by thread ID:

```json
{
  "google_access_token": "your_access_token",
  "thread_id": "thread_id_from_get_recent_emails",
  "offset": 1000
}
```

The response includes:

- A 1k chunk of the email body starting from the specified offset
- `body_size_bytes`: Total size of the email body
- `chunk_size`: Size of the returned chunk
- `contains_full_body`: Boolean indicating if the chunk contains the remainder of the body

To retrieve the entire email body of a long message, make sequential calls increasing the offset by 1000 each time until `contains_full_body` is true.

#### Sending an Email

```json
{
  "google_access_token": "your_access_token",
  "to": "recipient@example.com",
  "subject": "Hello from MCP Gmail",
  "body": "This is the email body in plain text",
  "html_body": "<p>This is the <strong>HTML</strong> version of the email.</p>"
}
```

The response includes the newly created message ID and thread ID.

## Troubleshooting

### Common Issues

#### Token Refresh Errors

If you encounter errors refreshing tokens:

1. Verify your `client_id` and `client_secret` are correct
2. Ensure your OAuth consent screen is properly configured
3. Check that your refresh token has not been revoked

#### Permission Issues

If you receive permission errors when accessing Gmail:

1. Make sure your OAuth consent screen includes the required Gmail scopes:
   - `https://www.googleapis.com/auth/gmail.readonly` (for reading emails)
   - `https://www.googleapis.com/auth/gmail.compose` (for sending emails)

#### Authentication Flow Issues

If you're having trouble with the initial OAuth flow:

1. Use the provided `get_refresh_token.py.template` script as a starting point
2. Ensure your redirect URI matches what you configured in Google Cloud Console

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable the Gmail API
4. Configure OAuth consent screen
5. Create OAuth client ID credentials (select "Desktop app" as the application type)
6. Save the client ID and client secret
7. Use OAuth 2.0 to obtain access and refresh tokens with the following scopes:
   - `https://www.googleapis.com/auth/gmail.readonly` (for reading emails)
   - `https://www.googleapis.com/auth/gmail.send` (for sending emails)

## Token Refreshing

This server implements automatic token refreshing. When your access token expires, the Google API client will use the refresh token, client ID, and client secret to obtain a new access token without requiring user intervention.

## Security Note

This server requires direct access to your Google API credentials. Always keep your tokens and credentials secure and never share them with untrusted parties.