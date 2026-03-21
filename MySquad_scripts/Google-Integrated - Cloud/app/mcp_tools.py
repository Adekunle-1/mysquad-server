"""
Responsibility: Define and expose available MCP tools for external systems (n8n).
Returns structured tool definitions with input schemas that external systems
can discover via the /tools endpoint. Tools are grouped by function:
send/draft operations, search/retrieval operations, label operations.
"""

from typing import List, Dict, Any

def get_mcp_tools() -> List[Dict[str, Any]]:
    """
    Get list of available MCP tools with input schemas.
    
    Returns:
        List of tool definitions with name, description, and inputSchema
    """
    return [
        {
            "name": "send_email",
            "description": "Send a new email via Gmail. Supports multiple recipients, CC, and BCC.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "to": {"type": "string", "description": "Recipient email(s), comma-separated"},
                    "subject": {"type": "string", "description": "Email subject line"},
                    "body": {"type": "string", "description": "Email body (plain text)"},
                    "access_token": {"type": "string", "description": "User's Gmail OAuth token"},
                    "cc": {"type": "string", "description": "CC recipients (optional)"},
                    "bcc": {"type": "string", "description": "BCC recipients (optional)"}
                },
                "required": ["to", "subject", "body", "access_token"]
            }
        },
        {
            "name": "search_emails",
            "description": "Search emails using Gmail search syntax (e.g., 'from:john is:unread')",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Gmail search query"},
                    "access_token": {"type": "string", "description": "User's Gmail OAuth token"},
                    "max_results": {"type": "integer", "description": "Max results (default: 10)"}
                },
                "required": ["query", "access_token"]
            }
        },
        {
            "name": "get_email",
            "description": "Get full details of a specific email including thread context",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Gmail message ID"},
                    "access_token": {"type": "string", "description": "User's Gmail OAuth token"}
                },
                "required": ["message_id", "access_token"]
            }
        },
        {
            "name": "mark_as_read",
            "description": "Mark a message as read (removes UNREAD label)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Gmail message ID"},
                    "access_token": {"type": "string", "description": "User's Gmail OAuth token"}
                },
                "required": ["message_id", "access_token"]
            }
        },
        {
            "name": "mark_as_unread",
            "description": "Mark a message as unread (adds UNREAD label)",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "message_id": {"type": "string", "description": "Gmail message ID"},
                    "access_token": {"type": "string", "description": "User's Gmail OAuth token"}
                },
                "required": ["message_id", "access_token"]
            }
        },
        {
    "name": "draft_email",
    "description": "Create a new email draft or update an existing one.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "to": {"type": "string", "description": "Recipient email(s), comma-separated"},
            "subject": {"type": "string", "description": "Draft subject"},
            "body": {"type": "string", "description": "Draft body (plain text)"},
            "access_token": {"type": "string", "description": "User's Gmail OAuth token"},
            "cc": {"type": "string", "description": "CC recipients (optional)"},
            "bcc": {"type": "string", "description": "BCC recipients (optional)"},
            "draft_id": {"type": "string", "description": "Existing draft ID to update (optional)"}
        },
        "required": ["to", "subject", "body", "access_token"]
            }
        },
        {
    "name": "create_label",
    "description": "Create a new Gmail label.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Label name"},
            "access_token": {"type": "string", "description": "User's Gmail OAuth token"}
        },
        "required": ["name", "access_token"]
            }
        },
        {
    "name": "list_labels",
    "description": "List all user-created Gmail labels.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "access_token": {"type": "string", "description": "User's Gmail OAuth token"}
        },
        "required": ["access_token"]
            }
        },
        {
    "name": "add_label",
    "description": "Add a label to a Gmail message.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "Gmail message ID"},
            "label_name": {"type": "string", "description": "Label name"},
            "access_token": {"type": "string", "description": "User's Gmail OAuth token"}
        },
        "required": ["message_id", "label_name", "access_token"]
             }
        },
        {
    "name": "remove_label",
    "description": "Remove a label from a Gmail message.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "message_id": {"type": "string", "description": "Gmail message ID"},
            "label_name": {"type": "string", "description": "Label name"},
            "access_token": {"type": "string", "description": "User's Gmail OAuth token"}
        },
        "required": ["message_id", "label_name", "access_token"]
            }
        }
    ]
