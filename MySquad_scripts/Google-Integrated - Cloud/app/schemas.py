"""
Responsibility: Define Pydantic models for API request/response validation.
Provides structured validation for all endpoint inputs. Models are grouped
by operation type: email operations, label operations, and utility schemas.
"""

from pydantic import BaseModel, Field
from typing import Optional

# ============================================================================
# EMAIL OPERATION SCHEMAS
# ============================================================================

class SendEmailRequest(BaseModel):
    """Schema for sending a new email."""
    to: str = Field(..., description="Recipient email(s), comma-separated")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Email body (plain text)")
    access_token: str = Field(..., description="User's Gmail OAuth token")
    cc: Optional[str] = Field(None, description="CC recipients")
    bcc: Optional[str] = Field(None, description="BCC recipients")

class DraftEmailRequest(BaseModel):
    """Schema for creating/updating an email draft."""
    to: str = Field(..., description="Recipient email(s)")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body")
    access_token: str = Field(..., description="User's Gmail OAuth token")
    cc: Optional[str] = None
    bcc: Optional[str] = None
    draft_id: Optional[str] = Field(None, description="Draft ID to update")

# ============================================================================
# EMAIL RETRIEVAL SCHEMAS
# ============================================================================

class SearchEmailsRequest(BaseModel):
    """Schema for searching emails."""
    query: str = Field(..., description="Gmail search query")
    access_token: str = Field(..., description="User's Gmail OAuth token")
    max_results: Optional[int] = Field(10, description="Max number of results")

class GetEmailRequest(BaseModel):
    """Schema for retrieving full email details."""
    message_id: str = Field(..., description="Gmail message ID")
    access_token: str = Field(..., description="User's Gmail OAuth token")

# ============================================================================
# MESSAGE ACTION SCHEMAS
# ============================================================================

class MessageActionRequest(BaseModel):
    """Schema for marking emails as read/unread."""
    message_id: str = Field(..., description="Gmail message ID")
    access_token: str = Field(..., description="User's Gmail OAuth token")

# ============================================================================
# LABEL MANAGEMENT SCHEMAS
# ============================================================================

class LabelCreateRequest(BaseModel):
    """Schema for creating a new label."""
    name: str = Field(..., description="Label name")
    access_token: str = Field(..., description="User's Gmail OAuth token")

class LabelListRequest(BaseModel):
    """Schema for listing labels."""
    access_token: str = Field(..., description="User's Gmail OAuth token")

class LabelModifyRequest(BaseModel):
    """Schema for adding/removing labels on emails."""
    message_id: str = Field(..., description="Gmail message ID")
    label_name: str = Field(..., description="Label name")
    access_token: str = Field(..., description="User's Gmail OAuth token")

# ============================================================================
# UTILITY SCHEMAS (Kept for backward compatibility)
# ============================================================================

class LabelRequest(BaseModel):
    """Deprecated: Use specific label request types above."""
    access_token: str = Field(..., description="User's Gmail OAuth token")
    name: Optional[str] = Field(None, description="Label name (for create)")
    message_id: Optional[str] = Field(None, description="Message ID (for add/remove)")
    label_name: Optional[str] = Field(None, description="Label name (for add/remove)")

class ErrorResponse(BaseModel):
    """Standard error response."""
    success: bool = False
    error: str

class SuccessResponse(BaseModel):
    """Standard success response."""
    success: bool = True


# ============================================================================
# ONBOARDING SCHEMAS
# ============================================================================

class UserInfo(BaseModel):
    """User profile information."""
    firstName: str = Field(..., min_length=1, max_length=100)
    lastName: str = Field(..., min_length=1, max_length=100)
    userName: str = Field(..., min_length=1, max_length=100)
    email: str = Field(..., min_length=1, max_length=255)
    phone_no: str = Field(..., min_length=1, max_length=20)


class BuilderProfile(BaseModel):
    """Builder profile containing primary focus areas."""
    primaryFocus: dict[str, str] = Field(..., min_items=1, max_items=3, description="Interest areas as key-value pairs")


class HustleIntensity(BaseModel):
    """User's hustle intensity and mode (for future use)."""
    value: int = Field(..., ge=0, le=100)
    mode: str = Field(..., min_length=1)


class OnboardingRequest(BaseModel):
    """Complete onboarding request payload."""
    user: UserInfo
    builderProfile: BuilderProfile
    helpNeeds: list = Field(..., min_items=1)
    hustleIntensity: HustleIntensity


class OnboardingResponse(BaseModel):
    """Onboarding response."""
    status: str = Field(..., description="'successful' or 'failed'")
    message: str = Field(default="")
