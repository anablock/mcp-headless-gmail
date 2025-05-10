"""
Configuration module for the Gmail MCP server.
Securely loads configuration from environment variables.
"""

import os
import logging
from typing import Optional, Dict, Any
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('mcp_server_headless_gmail.config')

# Attempt to load environment variables from .env file
load_dotenv()

class Config:
    """Configuration manager for Gmail MCP server."""
    
    @staticmethod
    def get_env(key: str, default: Optional[str] = None) -> Optional[str]:
        """
        Get an environment variable, logging a warning if not found.
        
        Args:
            key: Environment variable name
            default: Default value if not found
            
        Returns:
            Environment variable value or default
        """
        value = os.environ.get(key, default)
        if value is None:
            logger.warning(f"Environment variable {key} not found.")
        return value
    
    @staticmethod
    def get_credentials() -> Dict[str, Any]:
        """
        Get Google OAuth credentials from environment variables.
        
        Returns:
            Dictionary with credential information
        """
        credentials = {
            "client_id": Config.get_env("GOOGLE_CLIENT_ID"),
            "client_secret": Config.get_env("GOOGLE_CLIENT_SECRET"),
            "refresh_token": Config.get_env("GOOGLE_REFRESH_TOKEN"),
            "access_token": Config.get_env("GOOGLE_ACCESS_TOKEN"),
        }
        
        # Log which credentials were found (without revealing actual values)
        found_creds = []
        missing_creds = []
        for name, value in credentials.items():
            if value:
                found_creds.append(name)
            else:
                missing_creds.append(name)
        
        if found_creds:
            logger.info(f"Found credentials: {', '.join(found_creds)}")
        if missing_creds:
            logger.warning(f"Missing credentials: {', '.join(missing_creds)}")
            
        return credentials
    
    @staticmethod
    def get_logging_level() -> int:
        """
        Get the configured logging level.
        
        Returns:
            Logging level as an integer
        """
        log_level = Config.get_env("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, log_level, logging.INFO)
        return level
    
    @staticmethod
    def get_port() -> int:
        """
        Get the server port.
        
        Returns:
            Port number
        """
        return int(Config.get_env("PORT", "3333"))
