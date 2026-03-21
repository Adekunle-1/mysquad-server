import httpx

from app.config import settings

# Timeout: 120 seconds to allow n8n AI processing time
N8N_TIMEOUT = 120.0


async def forward_to_n8n(payload: dict) -> dict:
    """
    POST payload to n8n webhook and return the response.
    Raises httpx.HTTPStatusError on non-2xx responses.
    """
    async with httpx.AsyncClient(timeout=N8N_TIMEOUT) as client:
        response = await client.post(
            settings.n8n_webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.json()
