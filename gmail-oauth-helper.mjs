// Gmail OAuth Helper
// This script helps generate a refresh token for Gmail API access

import fs from 'fs';
import { google } from 'googleapis';
import http from 'http';
import url from 'url';
import open from 'open';

// Path to your client secret file
const CLIENT_SECRET_PATH = '/Users/vukdukic/Downloads/client_secret_570700348382-bnlv5ccg9pqh1g5isadgk36q7m3b295q.apps.googleusercontent.com.json';

// Load client secrets
const clientSecretRaw = fs.readFileSync(CLIENT_SECRET_PATH);
const credentials = JSON.parse(clientSecretRaw);
const { client_secret, client_id, redirect_uris } = credentials.installed || credentials.web;

// Create OAuth2 client
const oauth2Client = new google.auth.OAuth2(
  client_id,
  client_secret,
  redirect_uris[0] || 'http://localhost:3000/oauth2callback'
);

// Generate the authentication URL
const SCOPES = [
  'https://www.googleapis.com/auth/gmail.readonly',
  'https://www.googleapis.com/auth/gmail.send',
  'https://www.googleapis.com/auth/gmail.modify'
];

const authUrl = oauth2Client.generateAuthUrl({
  access_type: 'offline',
  scope: SCOPES,
  prompt: 'consent' // Forces the refresh token to be returned
});

console.log('Authorize this app by visiting this URL:', authUrl);

// Open the URL in a browser
open(authUrl);

// Create a web server to handle the callback
const server = http.createServer(async (req, res) => {
  try {
    // Extract code from callback URL
    const queryParams = url.parse(req.url, true).query;
    const code = queryParams.code;
    
    if (!code) {
      res.writeHead(400, { 'Content-Type': 'text/html' });
      res.end('Error: No authorization code received');
      return;
    }
    
    // Exchange code for tokens
    const { tokens } = await oauth2Client.getToken(code);
    
    // Display tokens
    console.log('\nToken Information:');
    console.log('Access Token:', tokens.access_token?.substring(0, 10) + '...');
    console.log('Refresh Token:', tokens.refresh_token);
    console.log('Token Type:', tokens.token_type);
    console.log('Expiry Date:', new Date(tokens.expiry_date).toLocaleString());
    
    // Save tokens to file
    fs.writeFileSync('gmail-tokens.json', JSON.stringify(tokens, null, 2));
    console.log('\nTokens saved to gmail-tokens.json');
    
    // Display the information needed for the Gmail integration
    console.log('\nFor your Gmail integration, you\'ll need:');
    console.log('Client ID:', client_id);
    console.log('Client Secret:', client_secret);
    console.log('Refresh Token:', tokens.refresh_token);
    
    // Send success response to browser
    res.writeHead(200, { 'Content-Type': 'text/html' });
    res.end(`
      <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <h1 style="color: #4285F4;">Authentication Successful</h1>
          <p>You've successfully authenticated with Gmail API!</p>
          <p>You can close this window and return to the terminal to see your tokens.</p>
          <p><strong>Your refresh token is:</strong></p>
          <code style="background: #f1f1f1; padding: 10px; display: block; word-break: break-all;">
            ${tokens.refresh_token}
          </code>
          <p>Use this token along with your client ID and client secret in your Gmail integration.</p>
        </body>
      </html>
    `);
    
    // Close the server after a short delay
    setTimeout(() => {
      server.close();
      console.log('Server closed');
      process.exit(0);
    }, 2000);
    
  } catch (error) {
    console.error('Error exchanging code for tokens:', error);
    
    res.writeHead(500, { 'Content-Type': 'text/html' });
    res.end(`
      <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
          <h1 style="color: #EA4335;">Authentication Error</h1>
          <p>Something went wrong during the authentication process:</p>
          <pre style="background: #f1f1f1; padding: 10px;">${error.message}</pre>
          <p>Please close this window and try again.</p>
        </body>
      </html>
    `);
  }
});

// Start the server
server.listen(3000, () => {
  console.log('Temporary server listening on http://localhost:3000');
  console.log('Waiting for authentication...');
});
