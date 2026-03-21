"""
Responsibility: Store all magic numbers, URLs, and constant values.
Centralized location for configuration constants referenced throughout
the application to avoid hardcoded values.
"""

# ============================================================================
# GMAIL API CONFIGURATION
# ============================================================================

GMAIL_API_BASE_URL = "https://www.googleapis.com/gmail/v1"
GMAIL_API_TIMEOUT = 30.0  # seconds

# ============================================================================
# EMAIL LIMITS (RFC 2822 compliant)
# ============================================================================

MAX_EMAIL_BODY_SIZE = 1_000_000  # 1MB
MAX_SUBJECT_LENGTH = 998  # RFC 2822 limit
MAX_SEARCH_RESULTS = 100

# ============================================================================
# HTTP STATUS CODES
# ============================================================================

HTTP_BAD_REQUEST = 400
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
HTTP_SERVER_ERROR = 500
HTTP_SERVICE_UNAVAILABLE = 503

# Retryable HTTP status codes (temporary server issues)
RETRYABLE_STATUS_CODES = [HTTP_SERVER_ERROR, HTTP_SERVICE_UNAVAILABLE]

# Non-retryable HTTP status codes (client errors, auth failures)
NON_RETRYABLE_STATUS_CODES = [HTTP_BAD_REQUEST, HTTP_UNAUTHORIZED, HTTP_FORBIDDEN, HTTP_NOT_FOUND]

# ============================================================================
# MCP SERVER CONFIGURATION
# ============================================================================

MCP_SERVER_NAME = "Google Integrated Server"
MCP_SERVER_VERSION = "1.0.0"

# SSE heartbeat interval
SSE_HEARTBEAT_INTERVAL = 30  # seconds
