"""
Responsibility: Provide shared utility functions for validation, encoding, and error handling.
This module consolidates common logic used across multiple handlers and services.
"""

import re
import base64
from typing import Tuple, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from app.constants import MAX_EMAIL_BODY_SIZE, MAX_SUBJECT_LENGTH
from app.logger import setup_logger

logger = setup_logger(__name__)


# ============================================================================
# EMAIL VALIDATION
# ============================================================================

def validate_email(email: str) -> bool:
    """Validate email format using RFC-compliant regex."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_email_list(emails: str) -> Tuple[bool, str]:
    """
    Validate comma-separated email list.
    
    Args:
        emails: Comma-separated email addresses
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not emails:
        return False, "Email list cannot be empty"
    
    email_list = [e.strip() for e in emails.split(',')]
    
    for email in email_list:
        if not validate_email(email):
            return False, f"Invalid email address: {email}"
    
    return True, ""


def parse_email_list(emails: str) -> List[str]:
    """Parse comma-separated emails and return clean list."""
    if not emails:
        return []
    return [email.strip() for email in emails.split(',') if email.strip()]


def validate_subject(subject: str) -> Tuple[bool, str]:
    """
    Validate email subject line.
    
    Args:
        subject: Email subject
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not subject:
        return False, "Email subject cannot be empty"
    
    if len(subject) > MAX_SUBJECT_LENGTH:
        return False, f"Subject exceeds maximum length of {MAX_SUBJECT_LENGTH} characters"
    
    return True, ""


def validate_email_body(body: str) -> Tuple[bool, str]:
    """
    Validate email body content.
    
    Args:
        body: Email body text
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not body:
        return False, "Email body cannot be empty"
    
    if len(body.encode('utf-8')) > MAX_EMAIL_BODY_SIZE:
        return False, f"Email body exceeds maximum size of {MAX_EMAIL_BODY_SIZE} bytes"
    
    return True, ""


# ============================================================================
# EMAIL MESSAGE ENCODING/DECODING
# ============================================================================

def encode_email_message(to: str, subject: str, body: str, 
                        cc: str = None, bcc: str = None) -> str:
    """
    Create and encode MIME message for Gmail API.
    
    Args:
        to: Recipient email(s)
        subject: Email subject
        body: Email body text
        cc: Optional CC recipients
        bcc: Optional BCC recipients
        
    Returns:
        Base64url-encoded MIME message
        
    Raises:
        ValueError: If message encoding fails
    """
    try:
        message = MIMEMultipart()
        message['To'] = to
        message['Subject'] = Header(subject, 'utf-8')
        
        if cc:
            message['Cc'] = cc
        if bcc:
            message['Bcc'] = bcc
        
        message.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # Encode the message
        raw_message = message.as_string()
        message_bytes = raw_message.encode('utf-8')
        base64_message = base64.urlsafe_b64encode(message_bytes)
        return base64_message.decode('utf-8').rstrip('=')
    except Exception as e:
        raise ValueError(f"Failed to encode message: {str(e)}")


def decode_email_message(encoded: str) -> str:
    """
    Decode base64url-encoded email message.
    
    Args:
        encoded: Base64url-encoded message
        
    Returns:
        Decoded message text
    """
    try:
        # Add padding
        encoded += '=' * (-len(encoded) % 4)
        decoded_bytes = base64.urlsafe_b64decode(encoded)
        return decoded_bytes.decode('utf-8', errors='ignore')
    except Exception as e:
        logger.error(f"Message decode error: {str(e)}")
        return "[Could not decode message]"


# ============================================================================
# INPUT VALIDATION HELPERS
# ============================================================================

def validate_non_empty_string(value: str, field_name: str) -> Tuple[bool, str]:
    """
    Validate that a string field is not empty.
    
    Args:
        value: String to validate
        field_name: Name of field for error messages
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not value or not value.strip():
        return False, f"{field_name} cannot be empty"
    return True, ""


def validate_required_fields(fields: dict) -> Tuple[bool, str]:
    """
    Validate that all required fields are present and non-empty.
    
    Args:
        fields: Dictionary of {field_name: field_value}
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    for field_name, field_value in fields.items():
        if not field_value:
            return False, f"{field_name} is required"
    return True, ""
