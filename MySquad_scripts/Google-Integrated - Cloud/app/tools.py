"""
Responsibility: Handle execution logic for all Gmail tools.
Each function is an async handler that receives validated input parameters,
executes the corresponding Gmail API operation via GmailClient, and returns
structured results. Error handling is provided via decorators.
"""

from typing import Dict, Any, Optional
from app.gmail_client import GmailClient
from app.logger import setup_logger
from app.decorators import handle_errors, validate_email_content
from app.config import config

logger = setup_logger(__name__)


@handle_errors
@validate_email_content
async def send_email_handler(
    to: str,
    subject: str,
    body: str,
    access_token: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None
) -> Dict[str, Any]:
    async with GmailClient(access_token) as client:
        result = await client.send_email(to, subject, body, cc, bcc)
    return result


@handle_errors
async def search_emails_handler(
    query: str,
    access_token: str,
    max_results: Optional[int] = None
) -> Dict[str, Any]:
    if not query:
        raise ValueError("Query cannot be empty")
    
    # Use config default if not specified
    if max_results is None:
        max_results = config.max_results
    
    if max_results < 1 or max_results > 100:
        raise ValueError(f"max_results must be between 1 and 100, got {max_results}")
    
    async with GmailClient(access_token) as client:
        result = await client.search_emails(query, max_results)
    
    return result


@handle_errors
async def get_email_handler(
    message_id: str,
    access_token: str
) -> Dict[str, Any]:
    if not message_id:
        raise ValueError("message_id cannot be empty")
    
    async with GmailClient(access_token) as client:
        result = await client.get_email(message_id)
    
    return result


@handle_errors
async def mark_as_read_handler(
    message_id: str,
    access_token: str
) -> Dict[str, Any]:
    if not message_id:
        raise ValueError("message_id cannot be empty")
    
    async with GmailClient(access_token) as client:
        result = await client.mark_as_read(message_id)
    
    return result


@handle_errors
async def mark_as_unread_handler(
    message_id: str,
    access_token: str
) -> Dict[str, Any]:
    if not message_id:
        raise ValueError("message_id cannot be empty")
    
    async with GmailClient(access_token) as client:
        result = await client.mark_as_unread(message_id)
    
    return result

@handle_errors
@validate_email_content
async def draft_email_handler(
    to: str,
    subject: str,
    body: str,
    access_token: str,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    draft_id: Optional[str] = None
) -> Dict[str, Any]:
    async with GmailClient(access_token) as client:
        result = await client.draft_email(
            to=to,
            subject=subject,
            body=body,
            cc=cc,
            bcc=bcc,
            draft_id=draft_id
        )
    return result


@handle_errors
async def create_label_handler(
    name: str,
    access_token: str
) -> Dict[str, Any]:
    if not name:
        raise ValueError("Label name cannot be empty")

    async with GmailClient(access_token) as client:
        result = await client.create_label(name)

    return result


@handle_errors
async def list_labels_handler(
    access_token: str
) -> Dict[str, Any]:
    async with GmailClient(access_token) as client:
        result = await client.list_labels()

    return result


@handle_errors
async def add_label_handler(
    message_id: str,
    label_name: str,
    access_token: str
) -> Dict[str, Any]:
    if not message_id or not label_name:
        raise ValueError("message_id and label_name are required")

    async with GmailClient(access_token) as client:
        result = await client.add_label(message_id, label_name)

    return result


@handle_errors
async def remove_label_handler(
    message_id: str,
    label_name: str,
    access_token: str
) -> Dict[str, Any]:
    if not message_id or not label_name:
        raise ValueError("message_id and label_name are required")

    async with GmailClient(access_token) as client:
        result = await client.remove_label(message_id, label_name)

    return result
