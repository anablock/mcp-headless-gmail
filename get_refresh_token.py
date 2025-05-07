#!/usr/bin/env python3
import os
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# Load client secrets from a file or use environment variables
def get_oauth_credentials():
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("Error: GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables must be set")
        print("Example: export GOOGLE_CLIENT_ID=your-client-id")
        print("         export GOOGLE_CLIENT_SECRET=your-client-secret")
        exit(1)
    
    return {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "redirect_uris": ["http://localhost"]
        }
    }

def main():
    # Define the scopes you need
    SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
    
    # Get the credentials
    credentials_json = get_oauth_credentials()
    
    # Write credentials to a temporary file
    with open('temp_credentials.json', 'w') as f:
        json.dump(credentials_json, f)
    
    try:
        # Run the OAuth flow
        flow = InstalledAppFlow.from_client_secrets_file(
            'temp_credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        
        # Print the refresh token
        print("\n====================== YOUR REFRESH TOKEN ======================")
        print(creds.refresh_token)
        print("=================================================================")
        print("\nStore this token securely and set it as an environment variable:")
        print(f"export GOOGLE_REFRESH_TOKEN={creds.refresh_token}")
        print("\nAccess token (expires in 1 hour):")
        print(creds.token)
        
    finally:
        # Clean up temporary file
        if os.path.exists('temp_credentials.json'):
            os.remove('temp_credentials.json')

if __name__ == '__main__':
    main()
