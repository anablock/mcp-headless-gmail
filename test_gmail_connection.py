#!/usr/bin/env python3
import os
import json
import logging
import subprocess
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("gmail_test")

def check_environment():
    """Check if all required environment variables are set."""
    required_vars = ['GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_SECRET', 'GOOGLE_REFRESH_TOKEN']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables before running this script.")
        logger.error("Run: source set_credentials.sh")
        return False
    
    return True

def test_refresh_token():
    """Test refreshing the access token using the MCP headless Gmail server."""
    logger.info("Testing token refresh functionality...")
    
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    refresh_token = os.environ.get('GOOGLE_REFRESH_TOKEN')
    
    # Prepare the input JSON for the MCP server
    input_json = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "CallTool",
        "params": {
            "name": "gmail_refresh_token",
            "parameters": {
                "google_refresh_token": refresh_token,
                "google_client_id": client_id,
                "google_client_secret": client_secret
            }
        }
    }
    
    try:
        # Start the MCP server process - npm version
        server_process = subprocess.Popen(
            ["npx", "@peakmojo/mcp-server-headless-gmail"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Send the input JSON to the server
        logger.info("Sending token refresh request to MCP server...")
        server_process.stdin.write(json.dumps(input_json) + "\n")
        server_process.stdin.flush()
        
        # Read the response (with timeout)
        import select
        readable, _, _ = select.select([server_process.stdout], [], [], 10)
        
        if readable:
            response_line = server_process.stdout.readline()
            logger.info("Received response from MCP server")
            
            try:
                response = json.loads(response_line)
                if "result" in response:
                    result = response["result"]
                    if isinstance(result, str):
                        # The result might be a JSON string itself
                        try:
                            result = json.loads(result)
                        except:
                            pass
                    
                    logger.info(f"Token refresh result: {result}")
                    
                    if isinstance(result, dict) and result.get("status") == "success":
                        logger.info("✅ Token refresh successful!")
                        if "access_token" in result:
                            logger.info(f"Access token: {result['access_token'][:10]}...")
                            return True
                    else:
                        logger.error(f"❌ Token refresh failed: {result}")
                else:
                    logger.error(f"❌ Invalid response format: {response}")
            except json.JSONDecodeError:
                logger.error(f"❌ Failed to parse response as JSON: {response_line}")
        else:
            logger.error("❌ Timeout waiting for MCP server response")
        
    except Exception as e:
        logger.error(f"❌ Error during token refresh test: {str(e)}")
    finally:
        # Clean up
        try:
            server_process.terminate()
            server_process.wait(timeout=5)
        except:
            server_process.kill()
    
    return False

def main():
    """Main entry point for the script."""
    logger.info("=== Gmail MCP Server Connection Test ===")
    
    # Check environment variables
    if not check_environment():
        sys.exit(1)
    
    # Test token refresh
    if test_refresh_token():
        logger.info("✅ Connection test completed successfully!")
    else:
        logger.error("❌ Connection test failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
