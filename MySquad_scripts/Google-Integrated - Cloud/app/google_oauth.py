"""
Responsibility: Handle Google OAuth2 authentication flows.
Manages authorization URL generation, token exchange, and token refresh.
Supports scopes for Gmail, Google Calendar, Sheets, and Docs.
Integrates with Google's OAuth2 endpoints for multi-service authorization.
"""

import os
import requests
from urllib.parse import urlencode

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

# Validate environment variables on import
if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI]):
    raise RuntimeError(
        "Missing required Google OAuth credentials. "
        "Ensure GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI are set."
    )

TOKEN_URL = "https://oauth2.googleapis.com/token"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"

# Google API Scopes - Full read, write, delete access
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",  # Full Gmail access (read, write, delete)
]

GOOGLE_CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar",  # Full Calendar access (read, write, delete events)
]

GOOGLE_SHEETS_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",  # Full Sheets access (read, write, delete)
]

GOOGLE_DOCS_SCOPES = [
    "https://www.googleapis.com/auth/documents",  # Full Docs access (read, write)
]

# Combined scopes for all services
ALL_SCOPES = GMAIL_SCOPES + GOOGLE_CALENDAR_SCOPES + GOOGLE_SHEETS_SCOPES + GOOGLE_DOCS_SCOPES

# Default scopes for authorization
DEFAULT_SCOPES = ALL_SCOPES


def get_authorization_url(phone_no: str, scopes: list = None) -> str:
    """Generate Google OAuth authorization URL with configurable scopes.
    
    Args:
        phone_no: The user's phone number to pass as state parameter
        scopes: List of scope strings. Defaults to ALL_SCOPES (Gmail, Calendar, Sheets, Docs)
    
    Returns:
        Google OAuth authorization URL
    """
    if scopes is None:
        scopes = DEFAULT_SCOPES  # Default to all services
    
    # Convert list to space-separated string if needed
    if isinstance(scopes, list):
        scope_string = " ".join(scopes)
    else:
        scope_string = scopes
    
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": scope_string,
        "access_type": "offline",
        "prompt": "consent",
        "state": phone_no
    }
    
    auth_url = f"{AUTH_URL}?{urlencode(params)}"
    return auth_url


def exchange_code_for_tokens(code: str) -> dict:
    """Exchange authorization code for tokens."""
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    response = requests.post(TOKEN_URL, data=data)
    response.raise_for_status()
    return response.json()


def refresh_access_token(refresh_token: str) -> dict:
    """Use refresh token to get a new access token."""
    data = {
        "refresh_token": refresh_token,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "grant_type": "refresh_token",
    }
    
    response = requests.post(TOKEN_URL, data=data)
    response.raise_for_status()
    return response.json()
