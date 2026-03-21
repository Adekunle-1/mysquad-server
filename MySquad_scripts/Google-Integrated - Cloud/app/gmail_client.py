"""
Responsibility: Communicate with Gmail API.
Handles all async HTTP interactions with Gmail API including sending, searching,
reading, drafting emails, and managing labels. Uses connection pooling and
exponential backoff retry logic for reliability.
"""

import httpx
import asyncio
from typing import Optional, Dict, Any
from app.config import config
from app.constants import (GMAIL_API_BASE_URL, GMAIL_API_TIMEOUT, RETRYABLE_STATUS_CODES, NON_RETRYABLE_STATUS_CODES)
from app.logger import setup_logger
from app.utils import encode_email_message, decode_email_message

logger = setup_logger(__name__)

class GmailClient:  
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            },
            timeout=GMAIL_API_TIMEOUT
        )
    
    async def close(self):
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        
        url = f"{GMAIL_API_BASE_URL}{endpoint}"
        attempt = 0
        
        while attempt < config.retry_attempts:
            try:
                # Make request
                if method == "GET":
                    response = await self.client.get(url, params=params)
                elif method == "POST":
                    response = await self.client.post(url, json=data)
                elif method == "PUT":
                    response = await self.client.put(url, json=data)
                elif method == "DELETE":
                    response = await self.client.delete(url)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.json()
            
            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                
                # Non-retryable errors
                if status_code in NON_RETRYABLE_STATUS_CODES:
                    logger.error(f"Client error {status_code}: {e.response.text}")
                    raise Exception(f"Gmail API error: {e.response.text}")
                
                # Retryable errors
                if status_code in RETRYABLE_STATUS_CODES and attempt < config.retry_attempts - 1:
                    attempt += 1
                    delay = config.retry_delay * (2 ** (attempt - 1))
                    logger.warning(f"Server error {status_code}, retrying in {delay}s")
                    await asyncio.sleep(delay)
                    continue
                
                # Max retries reached
                logger.error(f"Request failed after {config.retry_attempts} attempts")
                raise Exception(f"Gmail API error: {e.response.text}")
            
            except Exception as e:
                logger.error(f"Request error: {str(e)}")
                raise Exception(f"Request failed: {str(e)}")
    
    def _encode_message(self, to: str, subject: str, body: str, 
                       cc: Optional[str] = None, bcc: Optional[str] = None) -> str:
        """Create and encode MIME message (delegates to utils module)"""
        return encode_email_message(to, subject, body, cc, bcc)
    
    def _decode_message(self, encoded: str) -> str:
        """Decode base64url message (delegates to utils module)"""
        return decode_email_message(encoded)
    
    async def send_email(self, to: str, subject: str, body: str,
                        cc: Optional[str] = None, bcc: Optional[str] = None) -> Dict[str, Any]:
        encoded = self._encode_message(to, subject, body, cc, bcc)
        response = await self._make_request("POST", "/users/me/messages/send", {"raw": encoded})
        return {
            "message_id": response["id"],
            "thread_id": response["threadId"],
            "to": to,
            "subject": subject
        }
    
    async def search_emails(self, query: str, max_results: int = 10) -> Dict[str, Any]:
        search_response = await self._make_request(
            "GET", "/users/me/messages", params={"q": query, "maxResults": max_results}
        )
        
        if "messages" not in search_response:
            return {"messages": [], "total": 0}
        
        messages = []
        for msg in search_response["messages"]:
            try:
                msg_details = await self._make_request(
                    "GET", f"/users/me/messages/{msg['id']}", params={"format": "metadata"}
                )
                
                headers = {h["name"]: h["value"] for h in msg_details["payload"]["headers"]}
                
                messages.append({
                    "id": msg_details["id"],
                    "thread_id": msg_details["threadId"],
                    "from": headers.get("From", "Unknown"),
                    "to": headers.get("To", "Unknown"),
                    "subject": headers.get("Subject", "(No subject)"),
                    "snippet": msg_details.get("snippet", ""),
                    "date": headers.get("Date", "Unknown"),
                    "labels": msg_details.get("labelIds", [])
                })
            except Exception as e:
                logger.error(f"Error fetching message {msg['id']}: {str(e)}")
                continue
        
        return {"messages": messages, "total": len(messages)}
    
    async def get_email(self, message_id: str) -> Dict[str, Any]: 
        # Get the specific message
        msg = await self._make_request("GET", f"/users/me/messages/{message_id}", 
                                    params={"format": "full"})
        
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        
        # Extract body
        body = self._extract_body(msg["payload"])
        
        # Get thread messages
        thread_messages = []
        try:
            thread_response = await self._make_request(
                "GET", f"/users/me/threads/{msg['threadId']}"
            )
            
            for thread_msg in thread_response.get("messages", []):
                if thread_msg["id"] == message_id:
                    continue  # Skip the current message
                
                thread_headers = {h["name"]: h["value"] 
                                for h in thread_msg["payload"]["headers"]}
                
                thread_messages.append({
                    "id": thread_msg["id"],
                    "from": thread_headers.get("From", "Unknown"),
                    "subject": thread_headers.get("Subject", "(No subject)"),
                    "snippet": thread_msg.get("snippet", ""),
                    "date": thread_headers.get("Date", "Unknown")
                })
        except Exception as e:
            logger.warning(f"Could not fetch thread context: {str(e)}")
        
        return {
            "message": {
                "id": msg["id"],
                "thread_id": msg["threadId"],
                "from": headers.get("From", "Unknown"),
                "to": headers.get("To", "Unknown"),
                "cc": headers.get("Cc"),
                "subject": headers.get("Subject", "(No subject)"),
                "body": body or msg.get("snippet", ""),
                "date": headers.get("Date", "Unknown"),
                "labels": msg.get("labelIds", []),
                "headers": headers
            },
            "thread": thread_messages
        }

    def _extract_body(self, payload: Dict) -> str:
        """Extract body text from email payload"""
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain" and "data" in part["body"]:
                    return self._decode_message(part["body"]["data"])
                # Also check for nested parts
                if "parts" in part:
                    for subpart in part["parts"]:
                        if subpart["mimeType"] == "text/plain" and "data" in subpart["body"]:
                            return self._decode_message(subpart["body"]["data"])
        elif "body" in payload and "data" in payload["body"]:
            return self._decode_message(payload["body"]["data"])
        
        return ""

    async def mark_as_read(self, message_id: str) -> Dict[str, Any]:
        """Mark message as read"""
        await self._make_request("POST", f"/users/me/messages/{message_id}/modify", 
                                    {"removeLabelIds": ["UNREAD"]})
        return {"message_id": message_id, "status": "read"}
    
    async def mark_as_unread(self, message_id: str) -> Dict[str, Any]:
        """Mark message as unread"""
        await self._make_request("POST", f"/users/me/messages/{message_id}/modify",
                                {"addLabelIds": ["UNREAD"]})
        return {"message_id": message_id, "status": "unread"}
    
    async def _get_label_id(self, label_name: str, create_if_missing: bool = False) -> str:
        """Get label ID by name. Optionally create if it doesn't exist."""
        response = await self._make_request("GET", "/users/me/labels")
        
        for label in response.get("labels", []):
            if label["name"].lower() == label_name.lower():
                return label["id"]
        
        # Label doesn't exist
        if not create_if_missing:
            raise ValueError(f"Label '{label_name}' not found. Create it first using create_label.")
        
        logger.info(f"Label '{label_name}' not found, creating it...")
        
        payload = {
            "name": label_name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show"
        }
        
        try:
            response = await self._make_request("POST", "/users/me/labels", payload)
            return response["id"]
        except Exception as e:
            raise Exception(f"Could not create label '{label_name}': {str(e)}")
    
    async def draft_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[str] = None,
        bcc: Optional[str] = None,
        draft_id: Optional[str] = None
    ) -> Dict[str, Any]:
        encoded = self._encode_message(to, subject, body, cc, bcc)

        payload = {
            "message": {
                "raw": encoded
            }
        }

        if draft_id:
            response = await self._make_request(
                "PUT",
                f"/users/me/drafts/{draft_id}",
                payload
            )
            created = False
        else:
            response = await self._make_request(
                "POST",
                "/users/me/drafts",
                payload
            )
            created = True

        return {
            "draft_id": response["id"],
            "message_id": response["message"]["id"],
            "created": created
        }

    async def create_label(self, name: str) -> Dict[str, Any]:
        payload = {
            "name": name,
            "labelListVisibility": "labelShow",
            "messageListVisibility": "show"
        }

        response = await self._make_request(
            "POST",
            "/users/me/labels",
            payload
        )

        return {
            "label_id": response["id"],
            "name": response["name"]
        }
    
    async def list_labels(self) -> Dict[str, Any]:
        response = await self._make_request("GET", "/users/me/labels")

        labels = [
            {
                "id": label["id"],
                "name": label["name"],
                "type": label.get("type", "user")
            }
            for label in response.get("labels", [])
            if label.get("type") == "user"
        ]

        return {
            "labels": labels,
            "total": len(labels)
        }
    
    async def add_label(self, message_id: str, label_name: str) -> Dict[str, Any]:
        label_id = await self._get_label_id(label_name, create_if_missing=False)

        response = await self._make_request(
            "POST",
            f"/users/me/messages/{message_id}/modify",
            {"addLabelIds": [label_id]}
        )

        return {
            "message_id": message_id,
            "label_added": label_name,
            "current_labels": response.get("labelIds", [])
        }

    async def remove_label(self, message_id: str, label_name: str) -> Dict[str, Any]:
        label_id = await self._get_label_id(label_name, create_if_missing=False)

        response = await self._make_request(
            "POST",
            f"/users/me/messages/{message_id}/modify",
            {"removeLabelIds": [label_id]}
        )

        return {
            "message_id": message_id,
            "label_removed": label_name,
            "current_labels": response.get("labelIds", [])
        }
