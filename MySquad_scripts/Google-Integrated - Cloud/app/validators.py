"""
Responsibility: Input validation for user requests.
This module is kept for backward compatibility. All validation logic
has been consolidated in the utils module.
See app.utils for the actual validation implementations.
"""

# For backward compatibility, re-export from utils
from app.utils import (
    validate_email,
    validate_email_list,
    validate_email_body,
    validate_subject,
    parse_email_list,
    validate_non_empty_string,
    validate_required_fields
)

__all__ = [
    'validate_email',
    'validate_email_list',
    'validate_email_body',
    'validate_subject',
    'parse_email_list',
    'validate_non_empty_string',
    'validate_required_fields'
]
