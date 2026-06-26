"""
Responsibility: FastAPI application entry point and route handlers.
Orchestrates authentication endpoints (OAuth flow, token management) and
Gmail tool execution endpoints. Handles request routing, error conversion
to HTTP responses, and application lifecycle events.

Authentication Endpoints (4):
  - POST /users          - Get user and manage auth flow (with token expiry check)
  - GET  /oauth/callback - Google OAuth callback handler (HTML response + n8n webhook)
  - GET  /token          - Get fresh access token for user (with token expiry check)
  - GET  /debug/auth-url - Debug endpoint for auth URL

Gmail Tool Endpoints (10):
  - POST /tools/send_email
  - POST /tools/search_emails
  - POST /tools/get_email
  - POST /tools/mark_as_read
  - POST /tools/mark_as_unread
  - POST /tools/draft_email
  - POST /tools/create_label
  - POST /tools/list_labels
  - POST /tools/add_label
  - POST /tools/remove_label

Discovery Endpoints (2):
  - GET /tools   - Discover available tools
  - GET /health  - Health check
"""

import requests
import os
from datetime import timezone
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel
import uvicorn

# Authentication imports
from app.db import (
    get_tenant,
    save_tokens,
    update_access_token,
    clear_tokens,
    is_token_expired,
    compute_token_expiry,
    init_db,
    close_all_connections
)
from app.crypto import encrypt_token, decrypt_token
from app.google_oauth import (
    get_authorization_url,
    exchange_code_for_tokens,
    refresh_access_token,
    get_google_userinfo,
    DEFAULT_SCOPES
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

logger = setup_logger(__name__)

# n8n webhook to notify after successful OAuth authorization
N8N_AUTH_FEEDBACK_WEBHOOK = "https://orangegroupsai.online/webhook/google_auth_feedback"

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
    required_env_vars = {
        "GOOGLE_CLIENT_ID": "Google OAuth client ID",
        "GOOGLE_CLIENT_SECRET": "Google OAuth client secret",
        "GOOGLE_REDIRECT_URI": "Google OAuth redirect URI",
        "TOKEN_ENCRYPTION_KEY": "Fernet encryption key for token storage",
        "DATABASE_URL": "PostgreSQL connection string"
    }

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
    tenant_id: str
    messaging_channel: str  # e.g. 'whatsapp', 'telegram', etc.


# ============================================================================
# HELPERS
# ============================================================================

def _load_template(filename: str) -> str:
    """Load an HTML template from the templates directory."""
    template_path = os.path.join(os.path.dirname(__file__), "templates", filename)
    with open(template_path, "r") as f:
        return f.read()


def _get_valid_access_token(user: dict, tenant_id: str) -> str:
    """
    Return a valid (non-expired) plaintext access token for the tenant.

    Flow:
    - If stored access token is still valid → decrypt and return it.
    - If expired → use refresh token to get a new one, encrypt and save it,
      then return the new plaintext token.
    - If refresh fails (revoked) → clear tokens and raise 401.

    Args:
        user:      Row dict from get_tenant().
        tenant_id: UUID string of the tenant.

    Returns:
        Plaintext access token string.

    Raises:
        HTTPException 401 if token is revoked.
        HTTPException 500 on decryption or refresh failure.
    """
    encrypted_access = user.get("access_token")
    encrypted_refresh = user.get("refresh_token")
    token_expiry = user.get("token_expiry")

    # Convert memoryview to bytes (psycopg2 BYTEA returns memoryview)
    if isinstance(encrypted_access, memoryview):
        encrypted_access = bytes(encrypted_access)
    if isinstance(encrypted_refresh, memoryview):
        encrypted_refresh = bytes(encrypted_refresh)

    # If access token still valid — return it directly
    if encrypted_access and not is_token_expired(token_expiry):
        try:
            return decrypt_token(encrypted_access)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to decrypt access token: {str(e)}")

    # Access token expired — use refresh token to get a new one
    if not encrypted_refresh:
        raise HTTPException(
            status_code=404,
            detail="User not connected. Please authorize first."
        )

    try:
        refresh_token = decrypt_token(encrypted_refresh)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to decrypt refresh token: {str(e)}")

    try:
        tokens = refresh_access_token(refresh_token)
        new_access_token = tokens.get("access_token")
        new_expiry = compute_token_expiry()
        encrypted_new_access = encrypt_token(new_access_token)
        update_access_token(tenant_id, encrypted_new_access, new_expiry)
        logger.info(f"Access token refreshed for tenant {tenant_id}")
        return new_access_token

    except requests.HTTPError as e:
        if e.response.status_code in [400, 401]:
            clear_tokens(tenant_id)
            raise HTTPException(
                status_code=401,
                detail="Google access was revoked. User needs to re-authorize."
            )
        raise HTTPException(status_code=500, detail=f"Failed to refresh access token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to refresh access token: {str(e)}")


def _notify_n8n(tenant_id: str, messaging_channel: str, status: str):
    """
    Fire-and-forget POST to the n8n auth feedback webhook.
    Logs warnings on failure but never raises — UI response is not blocked.

    Args:
        tenant_id:         The tenant's UUID.
        messaging_channel: Channel the user came from (e.g. 'whatsapp').
        status:            'success' or 'failed'.
    """
    try:
        payload = {
            "tenant_id": tenant_id,
            "messaging_channel": messaging_channel,
            "status": status
        }
        response = requests.post(N8N_AUTH_FEEDBACK_WEBHOOK, json=payload, timeout=5)
        response.raise_for_status()
        logger.info(f"n8n webhook notified for tenant {tenant_id}: {status}")
    except Exception as e:
        logger.warning(f"Failed to notify n8n webhook for tenant {tenant_id}: {str(e)}")


# ============================================================================
# GENERIC MCP TOOL ENDPOINT WRAPPER
# ============================================================================

async def generic_tool_endpoint(handler, **kwargs):
    """
    Generic handler wrapper for all tool endpoints.
    Converts handler result (with success flag) to proper HTTP response.
    """
    result = await handler(**kwargs)

    if not result.get("success", False):
        logger.warning(f"Tool execution failed: {result.get('error')}")
        error_code = result.get("error_code", "INTERNAL_ERROR")
        status_code = 400 if error_code == "VALIDATION_ERROR" else 500
        raise HTTPException(status_code=status_code, detail=result.get("error"))

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
    1. Get tenant from DB by tenant_id
    2. If no tokens: return auth URL (pass messaging_channel as state suffix)
    3. If tokens exist: check expiry, return valid access token

    Args:
        payload: UserCreate with tenant_id and messaging_channel

    Returns:
        - needs_authorization: auth_url for the user to click
        - success: decrypted access_token ready to use
    """
    try:
        user = get_tenant(payload.tenant_id)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))

    tenant_id = str(user["tenant_id"])

    # No tokens at all — user needs to authorize
    if not user.get("refresh_token"):
        # Encode messaging_channel into state so callback can retrieve it
        state = f"{tenant_id}|{payload.messaging_channel}"
        auth_url = get_authorization_url(state)
        return {
            "status": "needs_authorization",
            "message": "User needs to authorize Google access",
            "auth_url": auth_url
        }

    # Get a valid access token (checks expiry, refreshes if needed)
    access_token = _get_valid_access_token(user, tenant_id)

    return {
        "status": "success",
        "access_token": access_token,
        "token_type": "Bearer"
    }


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
    1. Parse tenant_id and messaging_channel from state
    2. Exchange code for tokens
    3. Fetch Google userinfo (email, sub)
    4. Encrypt and save all tokens + metadata
    5. Fire n8n webhook with tenant_id, messaging_channel, status
    6. Return a rendered HTML page (success or failure)

    State format: "<tenant_id>|<messaging_channel>"
    """
    # Parse state
    messaging_channel = "unknown"
    tenant_id = state
    if "|" in state:
        parts = state.split("|", 1)
        tenant_id = parts[0]
        messaging_channel = parts[1]

    # Handle OAuth error from Google
    if error:
        logger.warning(f"OAuth error for tenant {tenant_id}: {error}")
        _notify_n8n(tenant_id, messaging_channel, "failed")
        html = _load_template("oauth_failure.html").replace("{error_reason}", error)
        return HTMLResponse(content=html, status_code=400)

    if not code:
        _notify_n8n(tenant_id, messaging_channel, "failed")
        html = _load_template("oauth_failure.html").replace("{error_reason}", "No authorization code received.")
        return HTMLResponse(content=html, status_code=400)

    # Exchange code for tokens
    try:
        tokens = exchange_code_for_tokens(code)
    except Exception as e:
        logger.error(f"Token exchange failed for tenant {tenant_id}: {str(e)}")
        _notify_n8n(tenant_id, messaging_channel, "failed")
        html = _load_template("oauth_failure.html").replace("{error_reason}", "Failed to exchange authorization code.")
        return HTMLResponse(content=html, status_code=500)

    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    token_scope = tokens.get("scope", " ".join(DEFAULT_SCOPES))

    if not refresh_token:
        _notify_n8n(tenant_id, messaging_channel, "failed")
        html = _load_template("oauth_failure.html").replace(
            "{error_reason}",
            "No refresh token received. User may have already authorized. Please revoke access in Google and try again."
        )
        return HTMLResponse(content=html, status_code=400)

    # Fetch Google userinfo
    userinfo = get_google_userinfo(access_token)
    platform_user_id = userinfo.get("sub")
    platform_email = userinfo.get("email")

    # Encrypt and save
    try:
        encrypted_access = encrypt_token(access_token)
        encrypted_refresh = encrypt_token(refresh_token)
        token_expiry = compute_token_expiry()

        save_tokens(
            tenant_id=tenant_id,
            encrypted_access=encrypted_access,
            encrypted_refresh=encrypted_refresh,
            token_expiry=token_expiry,
            token_scope=token_scope,
            platform_user_id=platform_user_id,
            platform_email=platform_email
        )
    except Exception as e:
        logger.error(f"Failed to save tokens for tenant {tenant_id}: {str(e)}")
        _notify_n8n(tenant_id, messaging_channel, "failed")
        html = _load_template("oauth_failure.html").replace("{error_reason}", "Failed to save authorization. Please try again.")
        return HTMLResponse(content=html, status_code=500)

    # Notify n8n
    _notify_n8n(tenant_id, messaging_channel, "success")

    # Render success page
    email_line = f'<p class="email">{platform_email}</p>' if platform_email else ""
    html = _load_template("oauth_success.html").replace("{email_line}", email_line)
    return HTMLResponse(content=html, status_code=200)


@app.get("/token")
def get_access_token(tenant_id: str):
    """
    Get a valid access token for a tenant.
    Checks expiry first — returns stored token if still valid,
    otherwise refreshes via Google and saves the new token.

    Args:
        tenant_id: UUID string of the tenant.

    Returns:
        access_token (plaintext), token_type
    """
    try:
        user = get_tenant(tenant_id)
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))

    if not user.get("refresh_token") and not user.get("access_token"):
        raise HTTPException(
            status_code=404,
            detail="User not connected. Please authorize first."
        )

    access_token = _get_valid_access_token(user, tenant_id)

    return {
        "access_token": access_token,
        "token_type": "Bearer"
    }


@app.get("/debug/auth-url")
def debug_auth_url():
    """Debug endpoint to see the generated auth URL."""
    from app.google_oauth import GOOGLE_CLIENT_ID, GOOGLE_REDIRECT_URI

    url = get_authorization_url("test_tenant_id|whatsapp")

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
    return await generic_tool_endpoint(
        send_email_handler,
        to=request.to, subject=request.subject, body=request.body,
        access_token=request.access_token, cc=request.cc, bcc=request.bcc
    )


@app.post("/tools/search_emails")
async def search_emails_endpoint(request: SearchEmailsRequest):
    return await generic_tool_endpoint(
        search_emails_handler,
        query=request.query, access_token=request.access_token, max_results=request.max_results
    )


@app.post("/tools/get_email")
async def get_email_endpoint(request: GetEmailRequest):
    return await generic_tool_endpoint(
        get_email_handler, message_id=request.message_id, access_token=request.access_token
    )


@app.post("/tools/mark_as_read")
async def mark_as_read_endpoint(request: MessageActionRequest):
    return await generic_tool_endpoint(
        mark_as_read_handler, message_id=request.message_id, access_token=request.access_token
    )


@app.post("/tools/mark_as_unread")
async def mark_as_unread_endpoint(request: MessageActionRequest):
    return await generic_tool_endpoint(
        mark_as_unread_handler, message_id=request.message_id, access_token=request.access_token
    )


@app.post("/tools/draft_email")
async def draft_email_endpoint(request: DraftEmailRequest):
    return await generic_tool_endpoint(
        draft_email_handler,
        to=request.to, subject=request.subject, body=request.body,
        access_token=request.access_token, cc=request.cc, bcc=request.bcc, draft_id=request.draft_id
    )


@app.post("/tools/create_label")
async def create_label_endpoint(request: LabelCreateRequest):
    return await generic_tool_endpoint(
        create_label_handler, name=request.name, access_token=request.access_token
    )


@app.post("/tools/list_labels")
async def list_labels_endpoint(request: LabelListRequest):
    return await generic_tool_endpoint(list_labels_handler, access_token=request.access_token)


@app.post("/tools/add_label")
async def add_label_endpoint(request: LabelModifyRequest):
    return await generic_tool_endpoint(
        add_label_handler, message_id=request.message_id,
        label_name=request.label_name, access_token=request.access_token
    )


@app.post("/tools/remove_label")
async def remove_label_endpoint(request: LabelModifyRequest):
    return await generic_tool_endpoint(
        remove_label_handler, message_id=request.message_id,
        label_name=request.label_name, access_token=request.access_token
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