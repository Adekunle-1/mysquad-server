"""
Responsibility: FastAPI application entry point and route handlers.
Orchestrates authentication endpoints (OAuth flow, token management) and
Gmail tool execution endpoints. Handles request routing, error conversion
to HTTP responses, and application lifecycle events.

Authentication Endpoints (4):
  - POST /users - Create/get user and manage auth flow
  - GET /oauth/callback - Google OAuth callback handler
  - GET /token - Get fresh access token for user
  - GET /debug/auth-url - Debug endpoint for auth URL

Onboarding Endpoints (1):
  - POST /onboarding_app - Create user onboarding session

Gmail Tool Endpoints (10):
  - POST /tools/send_email - Send email
  - POST /tools/search_emails - Search emails
  - POST /tools/get_email - Get email details
  - POST /tools/mark_as_read - Mark email as read
  - POST /tools/mark_as_unread - Mark email as unread
  - POST /tools/draft_email - Create/update email draft
  - POST /tools/create_label - Create Gmail label
  - POST /tools/list_labels - List Gmail labels
  - POST /tools/add_label - Add label to email
  - POST /tools/remove_label - Remove label from email

Discovery Endpoints (2):
  - GET /tools - Discover available tools
  - GET /health - Health check
"""

import requests
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Authentication imports
from app.db import (
    get_or_create_user,
    save_refresh_token,
    clear_refresh_token,
    init_db,
    close_all_connections
)
from app.crypto import encrypt_token, decrypt_token
from app.google_oauth import (
    get_authorization_url,
    exchange_code_for_tokens,
    refresh_access_token
)

# MCP imports
from app.config import config
from app.constants import MCP_SERVER_NAME, MCP_SERVER_VERSION
from app.logger import setup_logger
from app.schemas import (
    SendEmailRequest, SearchEmailsRequest, GetEmailRequest, 
    MessageActionRequest, DraftEmailRequest, 
    LabelCreateRequest, LabelListRequest, LabelModifyRequest
)
from app.mcp_tools import get_mcp_tools
from app.tools import (
    send_email_handler, search_emails_handler, get_email_handler, 
    mark_as_read_handler, mark_as_unread_handler, draft_email_handler, 
    create_label_handler, list_labels_handler, add_label_handler, 
    remove_label_handler
)

# Onboarding imports
from app.onboarding import create_onboarding_user
from app.schemas import OnboardingRequest, OnboardingResponse

logger = setup_logger(__name__)

app = FastAPI(
    title="Google Integrated Server",
    description="Unified Google OAuth Authentication and Gmail MCP Tools",
    version="1.0.0"
)


# ============================================================================
# DATABASE & LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
def startup_event():
    """Initialize database and validate environment on startup."""
    # List of required environment variables
    required_env_vars = {
        "GOOGLE_CLIENT_ID": "Google OAuth client ID",
        "GOOGLE_CLIENT_SECRET": "Google OAuth client secret",
        "GOOGLE_REDIRECT_URI": "Google OAuth redirect URI",
        "TOKEN_ENCRYPTION_KEY": "Fernet encryption key for token storage",
        "DATABASE_URL": "PostgreSQL connection string"
    }
    
    # Check all required variables are set
    missing = []
    for var, description in required_env_vars.items():
        if not os.getenv(var):
            missing.append(f"{var} ({description})")
    
    if missing:
        error_msg = "Missing required environment variables:\n  - " + "\n  - ".join(missing)
        logger.critical(error_msg)
        raise RuntimeError(error_msg + "\n\nSee .env.example for required variables.")
    
    logger.info("Environment validation passed")
    logger.info("Starting up - initializing database...")
    init_db()
    logger.info("Database initialized successfully")


@app.on_event("shutdown")
def shutdown_event():
    """Close all database connections on shutdown."""
    logger.info("Shutting down - closing database connections...")
    close_all_connections()


# ============================================================================
# AUTH REQUEST MODELS
# ============================================================================

class UserCreate(BaseModel):
    phone_no: str


# ============================================================================
# GENERIC MCP TOOL ENDPOINT WRAPPER
# ============================================================================

async def generic_tool_endpoint(handler, **kwargs):
    """
    Generic handler wrapper for all tool endpoints.
    Converts handler result (with success flag) to proper HTTP response.
    """
    result = await handler(**kwargs)
    
    # If handler returned error via decorator, pass it through
    if not result.get("success", False):
        logger.warning(f"Tool execution failed: {result.get('error')}")
        # Client error (validation) vs server error
        error_code = result.get("error_code", "INTERNAL_ERROR")
        status_code = 400 if error_code == "VALIDATION_ERROR" else 500
        raise HTTPException(status_code=status_code, detail=result.get("error"))
    
    # Success case - remove success flag from response
    response = {k: v for k, v in result.items() if k != "success"}
    return JSONResponse(content=response)


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/users")
def create_or_get_user(payload: UserCreate):
    """
    Main authentication endpoint - Called by n8n or client systems.
    
    Flow:
    1. Get or create user in DB by phone number
    2. If no refresh token exists: return auth URL for user to authorize
    3. If refresh token exists: decrypt it and return access token
    
    Args:
        payload: UserCreate with phone_no
    
    Returns:
        - needs_authorization: User must authorize (returns auth_url)
        - success: User authenticated (returns access_token)
    """
    user = get_or_create_user(payload.phone_no)
    
    # Check if user has refresh token
    encrypted_token = user.get("google_refresh_token")
    
    # No refresh token: User needs to authorize
    if not encrypted_token:
        auth_url = get_authorization_url(payload.phone_no)
        return {
            "status": "needs_authorization",
            "message": "User needs to authorize Google access",
            "auth_url": auth_url
        }
    
    # Convert memoryview/buffer to bytes if needed
    if isinstance(encrypted_token, memoryview):
        encrypted_token = encrypted_token.tobytes()
    elif isinstance(encrypted_token, bytearray):
        encrypted_token = bytes(encrypted_token)

    # Has refresh token: Decrypt and get access token
    try:
        refresh_token = decrypt_token(encrypted_token)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to decrypt refresh token: {str(e)}"
        )
    
    try:
        tokens = refresh_access_token(refresh_token)
        return {
            "status": "success",
            "access_token": tokens.get("access_token"),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type", "Bearer")
        }
    except requests.HTTPError as e:
        # Token was revoked by user
        if e.response.status_code in [400, 401]:
            # Delete invalid token and return new auth URL
            clear_refresh_token(payload.phone_no)
            
            auth_url = get_authorization_url(payload.phone_no)
            return {
                "status": "needs_authorization",
                "message": "Token was revoked. Please re-authorize.",
                "auth_url": auth_url
            }
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh access token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to refresh access token: {str(e)}"
        )


@app.get("/oauth/callback")
def google_oauth_callback(
    code: str = Query(None),
    error: str = Query(None),
    state: str = Query(...)
):
    """
    Google OAuth callback endpoint.
    Called by Google after user authorizes the application.
    
    Flow:
    1. Exchange code for tokens (includes refresh token)
    2. Encrypt and save refresh token in DB using phone number
    3. Return access token to user
    
    Args:
        code: Authorization code from Google
        error: Error from Google if authorization failed
        state: Phone number passed during authorization request
    
    Returns:
        success status with access_token and expiration info
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth authorization failed: {error}"
        )
    
    if not code:
        raise HTTPException(
            status_code=400,
            detail="No authorization code received"
        )
    
    phone_no = state  # state contains the phone_no we passed
    
    # Exchange code for tokens
    try:
        tokens = exchange_code_for_tokens(code)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to exchange authorization code: {str(e)}"
        )
    
    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    
    if not refresh_token:
        raise HTTPException(
            status_code=400,
            detail="No refresh token received from Google. User may have already authorized."
        )
    
    # Encrypt and save refresh token
    try:
        encrypted_token = encrypt_token(refresh_token)
        save_refresh_token(phone_no, encrypted_token)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save refresh token: {str(e)}"
        )
    
    return {
        "status": "success",
        "message": "Google account connected successfully",
        "phone_no": phone_no,
        "access_token": access_token,
        "expires_in": tokens.get("expires_in"),
        "token_type": tokens.get("token_type", "Bearer")
    }


@app.get("/token")
def get_access_token(phone_no: str):
    """
    Get fresh access token for a user.
    Alternative endpoint if you need just the access token without full /users flow.
    
    Args:
        phone_no: User identifier
    
    Returns:
        access_token and expiration info
    """
    user = get_or_create_user(phone_no)
    encrypted_token = user.get("google_refresh_token")
    
    if not encrypted_token:
        raise HTTPException(
            status_code=404,
            detail="User not connected. Please authorize first."
        )
    
    try:
        refresh_token = decrypt_token(encrypted_token)
        tokens = refresh_access_token(refresh_token)
        
        return {
            "access_token": tokens.get("access_token"),
            "expires_in": tokens.get("expires_in"),
            "token_type": tokens.get("token_type", "Bearer")
        }
    except requests.HTTPError as e:
        # Token was revoked by user
        if e.response.status_code in [400, 401]:
            clear_refresh_token(phone_no)
            
            raise HTTPException(
                status_code=401,
                detail="Token was revoked. User needs to re-authorize."
            )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get access token: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get access token: {str(e)}"
        )


@app.get("/debug/auth-url")
def debug_auth_url():
    """Debug endpoint to see the generated auth URL"""
    from app.google_oauth import get_authorization_url, GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI
    
    url = get_authorization_url("test_user_123")
    
    return {
        "auth_url": url,
        "client_id": GOOGLE_CLIENT_ID[:20] + "..." if GOOGLE_CLIENT_ID else "MISSING",
        "redirect_uri": GOOGLE_REDIRECT_URI
    }


# ============================================================================
# MCP TOOL DISCOVERY ENDPOINTS
# ============================================================================

@app.get("/tools")
async def list_tools():
    """Discover available Gmail MCP tools"""
    return JSONResponse(content={
        "tools": get_mcp_tools(),
        "server": {
            "name": MCP_SERVER_NAME,
            "version": MCP_SERVER_VERSION
        }
    })


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "tools": len(get_mcp_tools()),
        "version": MCP_SERVER_VERSION
    }


# ============================================================================
# MCP TOOL EXECUTION ENDPOINTS
# ============================================================================

@app.post("/tools/send_email")
async def send_email_endpoint(request: SendEmailRequest):
    """Send an email via Gmail"""
    return await generic_tool_endpoint(
        send_email_handler,
        to=request.to,
        subject=request.subject,
        body=request.body,
        access_token=request.access_token,
        cc=request.cc,
        bcc=request.bcc
    )


@app.post("/tools/search_emails")
async def search_emails_endpoint(request: SearchEmailsRequest):
    """Search emails using Gmail search syntax"""
    return await generic_tool_endpoint(
        search_emails_handler,
        query=request.query,
        access_token=request.access_token,
        max_results=request.max_results
    )


@app.post("/tools/get_email")
async def get_email_endpoint(request: GetEmailRequest):
    """Get full details of a specific email"""
    return await generic_tool_endpoint(
        get_email_handler,
        message_id=request.message_id,
        access_token=request.access_token
    )


@app.post("/tools/mark_as_read")
async def mark_as_read_endpoint(request: MessageActionRequest):
    """Mark an email as read"""
    return await generic_tool_endpoint(
        mark_as_read_handler,
        message_id=request.message_id,
        access_token=request.access_token
    )


@app.post("/tools/mark_as_unread")
async def mark_as_unread_endpoint(request: MessageActionRequest):
    """Mark an email as unread"""
    return await generic_tool_endpoint(
        mark_as_unread_handler,
        message_id=request.message_id,
        access_token=request.access_token
    )


@app.post("/tools/draft_email")
async def draft_email_endpoint(request: DraftEmailRequest):
    """Create or update an email draft"""
    return await generic_tool_endpoint(
        draft_email_handler,
        to=request.to,
        subject=request.subject,
        body=request.body,
        access_token=request.access_token,
        cc=request.cc,
        bcc=request.bcc,
        draft_id=request.draft_id
    )


@app.post("/tools/create_label")
async def create_label_endpoint(request: LabelCreateRequest):
    """Create a new Gmail label"""
    return await generic_tool_endpoint(
        create_label_handler,
        name=request.name,
        access_token=request.access_token
    )


@app.post("/tools/list_labels")
async def list_labels_endpoint(request: LabelListRequest):
    """List all user-created Gmail labels"""
    return await generic_tool_endpoint(
        list_labels_handler,
        access_token=request.access_token
    )


@app.post("/tools/add_label")
async def add_label_endpoint(request: LabelModifyRequest):
    """Add a label to an email"""
    return await generic_tool_endpoint(
        add_label_handler,
        message_id=request.message_id,
        label_name=request.label_name,
        access_token=request.access_token
    )


@app.post("/tools/remove_label")
async def remove_label_endpoint(request: LabelModifyRequest):
    """Remove a label from an email"""
    return await generic_tool_endpoint(
        remove_label_handler,
        message_id=request.message_id,
        label_name=request.label_name,
        access_token=request.access_token
    )


# ============================================================================
# ONBOARDING ENDPOINTS
# ============================================================================

@app.post("/onboarding_app", response_model=OnboardingResponse)
async def onboard_user(payload: OnboardingRequest) -> OnboardingResponse:
    """
    Handle user onboarding session creation.
    
    Creates user profile with personal info, interests, and help needs.
    Returns "successful" on success, "failed" on error with detailed message.
    """
    try:
        success, message = create_onboarding_user(payload)
        
        return OnboardingResponse(
            status="successful" if success else "failed",
            message=message
        )
    except Exception as e:
        logger.error(f"Onboarding endpoint error: {str(e)}")
        return OnboardingResponse(
            status="failed",
            message=f"Unexpected error: {str(e)}"
        )


# ============================================================================
# SERVER STARTUP
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=config.server_host,
        port=config.server_port,
        log_level=config.log_level.lower()
    )
