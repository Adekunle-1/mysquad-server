"""
Responsibility: Provide decorators for error handling and input validation.
Decorators wrap async handler functions to provide consistent error responses
and validate email content before processing.
"""

import functools
from typing import Callable, Any, Dict
from app.logger import setup_logger
from app.utils import validate_email_list, validate_subject, validate_email_body

logger = setup_logger(__name__)


def handle_errors(func: Callable) -> Callable:
    """
    Decorator to wrap handlers with consistent error handling.
    Catches exceptions and returns standardized error response.
    
    Converts exceptions to structured responses:
    - ValueError/ValidationError -> {success: False, error_code: VALIDATION_ERROR}
    - Other exceptions -> {success: False, error_code: INTERNAL_ERROR}
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> Dict[str, Any]:
        try:
            result = await func(*args, **kwargs)
            return {"success": True, **result}
        except ValueError as e:
            logger.warning(f"{func.__name__} validation error: {str(e)}")
            return {"success": False, "error": str(e), "error_code": "VALIDATION_ERROR"}
        except Exception as e:
            logger.error(f"{func.__name__} error: {str(e)}")
            return {"success": False, "error": str(e), "error_code": "INTERNAL_ERROR"}
    
    return wrapper


def validate_email_content(func: Callable) -> Callable:
    """
    Decorator to validate email fields (to, subject, body).
    Applied to send_email and draft_email handlers.
    
    Validates:
    - Email recipients (to) format
    - Subject line length and emptiness
    - Body content size and emptiness
    """
    @functools.wraps(func)
    async def wrapper(
        to: str,
        subject: str,
        body: str,
        access_token: str,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        
        # Validate email list
        valid, error = validate_email_list(to)
        if not valid:
            raise ValueError(error)
        
        # Validate subject
        valid, error = validate_subject(subject)
        if not valid:
            raise ValueError(error)
        
        # Validate body
        valid, error = validate_email_body(body)
        if not valid:
            raise ValueError(error)
        
        return await func(to, subject, body, access_token, *args, **kwargs)
    
    return wrapper
