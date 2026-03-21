# Google Integrated Server

A production-ready FastAPI server providing secure Google OAuth authentication and Gmail HTTP API tools. Designed for integration with automation platforms (n8n, Make, Zapier) and cloud deployments.

## 🎯 Overview

This server handles two primary functions:

1. **Google OAuth Authentication** - Multi-user authorization for Gmail, Google Calendar, Sheets, and Docs with encrypted token storage
2. **Gmail HTTP API Tools** - 10 endpoints for email operations (send, search, read, draft, label management)

Perfect for:
- Building integrations with n8n or other automation platforms
- Deploying multi-tenant Google service integrations
- Securely managing user OAuth tokens on any cloud platform (AWS, Azure, GCP, etc.)

## 📋 Requirements

- **Python 3.11+**
- **PostgreSQL 13+** (for token storage)
- **Docker & Docker Compose** (for containerized deployment)
- **Google OAuth Credentials** (Client ID, Secret, Redirect URI)

## 🏗️ Project Structure

```
google-integrated-server/
├── app/
│   ├── auth/
│   │   ├── crypto.py          # Token encryption/decryption
│   │   ├── db.py              # Database & user management
│   │   └── google_oauth.py     # OAuth2 flows
│   ├── gmail/
│   │   ├── gmail_client.py     # Gmail API client
│   │   ├── tools.py            # Tool handlers
│   │   └── mcp_tools.py        # Tool definitions
│   ├── utils.py                # Shared validation & encoding
│   ├── schemas.py              # Pydantic request/response models
│   ├── decorators.py           # Error handling & validation
│   ├── validators.py           # Input validation (proxies to utils)
│   ├── constants.py            # Magic numbers & URLs
│   ├── config.py               # Configuration loader
│   ├── logger.py               # Logging setup
│   └── main.py                 # FastAPI application & routes
├── config.yml                  # Server, Gmail, logging config
├── requirements.txt            # Python dependencies
└── Dockerfile                  # Container image
```

## ⚙️ Setup

### Local Development

```bash
# 1. Clone and setup
git clone <repo>
cd google-integrated-server
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Create .env file
cp .env.example .env
# Edit .env with:
# - GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URI
# - DATABASE_URL (postgresql://user:pass@localhost/db)
# - TOKEN_ENCRYPTION_KEY (generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# 3. Start PostgreSQL (if using Docker)
docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15

# 4. Start server
python app/main.py
```

### Docker Deployment

```bash
# Copy template and configure
cp .env.example .env
# Edit .env with your Google OAuth credentials and database URL

# Start entire stack (FastAPI + PostgreSQL + n8n)
docker-compose up -d
```

Server runs at `http://localhost:5671`

## 📚 API Summary

### Authentication (4 endpoints)
- **POST /users** - Get auth URL or access token for user
- **GET /oauth/callback** - OAuth callback handler
- **GET /token** - Get fresh access token
- **GET /debug/auth-url** - Debug endpoint

### Gmail Tools (10 endpoints)
- **POST /tools/send_email** - Send email
- **POST /tools/search_emails** - Search emails  
- **POST /tools/get_email** - Get email details
- **POST /tools/draft_email** - Create/update draft
- **POST /tools/mark_as_read** - Mark as read
- **POST /tools/mark_as_unread** - Mark as unread
- **POST /tools/create_label** - Create label
- **POST /tools/list_labels** - List labels
- **POST /tools/add_label** - Add label to email
- **POST /tools/remove_label** - Remove label from email

### Discovery (2 endpoints)
- **GET /tools** - Discover available tools
- **GET /health** - Health check

## 📝 Configuration

Edit `config.yml` to customize:

```yaml
server:
  port: 5671
  host: "0.0.0.0"

gmail:
  retry_attempts: 3
  retry_delay: 1.0
  max_results: 50

logging:
  level: "INFO"
```

## 📦 Docker Compose Stack

The included `docker-compose.yml` bundles:
- **PostgreSQL** - User & token storage
- **FastAPI Server** - Google integration service
- **n8n** - Workflow automation platform

All services communicate via internal Docker network.

## 🚀 Deployment

See [DEPLOYMENT_DOCUMENTATION.md](DEPLOYMENT_DOCUMENTATION.md) for cloud-agnostic deployment guidelines (AWS, Azure, GCP).

## 📋 TODO / Roadmap

- [ ] **Zoom OAuth authentication** - Add Zoom integration with OAuth flow
- [ ] **Google Calendar HTTP endpoints** - Calendar CRUD operations
- [ ] Google Sheets endpoints
- [ ] Google Docs endpoints
- [ ] Webhook retry mechanism
- [ ] Advanced audit logging

## 🔒 Security

- Refresh tokens encrypted with Fernet (symmetric encryption)
- Environment variable validation on startup
- Input validation on all endpoints
- Error handling prevents information leakage
- Connection pooling for database security

## 💾 Database Schema

Single table `myguy_users`:
- `chat_id` - User identifier (primary key)
- `google_refresh_token` - Encrypted Google refresh token
- `zoom_refresh_token` - Encrypted Zoom refresh token (future)
- `created_at`, `updated_at` - Timestamps

## 🛠️ Technology Stack

- **FastAPI** - Modern async Python web framework
- **httpx** - Async HTTP client
- **psycopg2** - PostgreSQL adapter
- **Pydantic** - Data validation
- **Cryptography** - Token encryption
- **Docker** - Container orchestration

## 📄 License

[Your License]

## 🤝 Contributing

[Your Contributing Guidelines]
- Body: `{label_name, access_token}`

**POST /tools/list_labels**
- List all user labels
- Body: `{access_token}`

**POST /tools/add_label**
- Add label to email
- Body: `{message_id, label_id, access_token}`

**POST /tools/remove_label**
- Remove label from email
- Body: `{message_id, label_id, access_token}`

### Discovery & Health (2 endpoints)

**GET /tools**
- List available Gmail MCP tools and metadata
- Returns: Array of tool definitions with descriptions

**GET /health**
- Health check endpoint
- Returns: `{status, tools, version}`

---

## 🔄 Authentication Flow

```
1. POST /users (user_id)
   ├─ First time? → auth_url
   └─ Has token? → access_token

2. User authorizes at Google → /oauth/callback
   ├─ Exchange code for tokens
   ├─ Encrypt & store refresh token
   └─ Return access_token

3. Use access_token with Gmail endpoints
   ├─ Auto-refresh if expired
   └─ Re-authorize if revoked
```

---

## 🔐 Security

| Feature | Implementation |
|---------|-----------------|
| **Encryption** | Fernet symmetric for refresh tokens |
| **Storage** | PostgreSQL BYTEA, never plaintext |
| **Connections** | Pooling, health checks, broken detection |
| **Validation** | Email format, body size, subject length |
| **Database** | Prepared statements |
| **Docker** | Non-root user (UID 1000) |
| **Config** | Environment variables, never hardcoded |

---

## ⚙️ Configuration

### `.env` (Required)
```env
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxx
GOOGLE_REDIRECT_URI=http://localhost:5677/oauth/callback
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/google_auth
TOKEN_ENCRYPTION_KEY=<fernet-key>
```

### `config.yml` (Optional)
```yaml
server:
  host: 0.0.0.0
  port: 5677

gmail:
  retry_attempts: 3
  retry_delay: 1.0
  max_results: 50

logging:
  level: INFO
```

---

## 🧪 Quick Tests

```bash
# Health check
curl http://localhost:5677/health

# List tools
curl http://localhost:5677/tools

# Get auth URL
curl -X POST http://localhost:5677/users \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123"}'

# Send email
curl -X POST http://localhost:5677/tools/send_email \
  -H "Content-Type: application/json" \
  -d '{
    "to": "user@example.com",
    "subject": "Hello",
    "body": "Test",
    "access_token": "<token>"
  }'
```

---

## 🐳 Docker Deployment (Recommended)

### Step 1: Create Docker Network
```bash
docker network create mcpnet
```

### Step 2: Start PostgreSQL (or use docker-compose)
```bash
docker run -d \
  --name postgres \
  --network mcpnet \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=google_integrated \
  -p 5432:5432 \
  postgres:15
```

### Step 3: Configure Environment
```bash
cp .env.example .env
# Edit .env with your credentials:
# - GOOGLE_CLIENT_ID (from Google Cloud Console)
# - GOOGLE_CLIENT_SECRET (from Google Cloud Console)
# - GOOGLE_REDIRECT_URI (e.g., http://your-domain:5671/oauth/callback)
# - TOKEN_ENCRYPTION_KEY (generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
# - DATABASE_URL=postgresql://postgres:postgres@postgres/google_integrated (if using docker)
```

### Step 4: Build and Run
```bash
docker-compose up --build
```

### Step 5: Verify Health
```bash
curl http://localhost:5671/health
```

Expected response:
```json
{
  "status": "healthy",
  "tools": 10,
  "version": "1.0.0"
}
```

---

## 🐳 Docker

```bash
docker-compose build
docker-compose up
docker-compose logs -f app
docker-compose down
```

Services:
- **app**: FastAPI on port 5671
- **postgres**: PostgreSQL 15 on port 5432 (optional, can use external DB)

---

## 🔄 Complete OAuth Flow Walkthrough

### Scenario: Connect first Gmail account

**Step 1: Client calls POST /users**
```bash
curl -X POST http://localhost:5671/users \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123"}'
```

**Response:**
```json
{
  "status": "needs_authorization",
  "message": "User needs to authorize Google access",
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...&redirect_uri=...&state=user123"
}
```

**Step 2: User clicks auth_url**
- Redirected to Google login/consent screen
- User authorizes application to access Gmail
- Google redirects to: `http://localhost:5671/oauth/callback?code=AUTH_CODE&state=user123`

**Step 3: Server handles callback**
- Exchanges `AUTH_CODE` for `access_token` + `refresh_token`
- Encrypts `refresh_token` with `TOKEN_ENCRYPTION_KEY`
- Stores encrypted token in PostgreSQL under `user123`
- Returns `access_token` to user

**Step 4: Next time - User calls POST /users again**
```bash
curl -X POST http://localhost:5671/users \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user123"}'
```

**Response:**
```json
{
  "status": "success",
  "access_token": "ya29.a...",
  "expires_in": 3599,
  "token_type": "Bearer"
}
```

- Server retrieves encrypted token from DB
- Automatically refreshes access token from Google
- Returns fresh access token immediately
- User doesn't need to re-authorize (until token revoked)

---

## 🤝 Integration Guide

### n8n Workflow

**Step 1: Create HTTP Request (Get Access Token)**
```
Method: POST
URL: http://your-server:5671/users
Headers: Content-Type: application/json
Body: {"user_id": "{{ $json.user_id }}"}
```

**Step 2: Save response token**
```
access_token = response.access_token
```

**Step 3: Send Email via Gmail**
```
Method: POST
URL: http://your-server:5671/tools/send_email
Headers: Content-Type: application/json
Body: {
  "to": "recipient@example.com",
  "subject": "Hello from n8n",
  "body": "This email was sent from n8n using Google Integrated",
  "access_token": "{{ access_token }}"
}
```

### Python Example

```python
import requests
import json

BASE_URL = "http://localhost:5671"
USER_ID = "my_app_user"

# Step 1: Get access token
auth_response = requests.post(
    f"{BASE_URL}/users",
    json={"user_id": USER_ID}
)

if auth_response.json()["status"] == "needs_authorization":
    auth_url = auth_response.json()["auth_url"]
    print(f"Please authorize at: {auth_url}")
    # User authorizes, then run again...
else:
    access_token = auth_response.json()["access_token"]
    
    # Step 2: Send email
    email_response = requests.post(
        f"{BASE_URL}/tools/send_email",
        json={
            "to": "user@example.com",
            "subject": "Hello from Python",
            "body": "Test message",
            "access_token": access_token
        }
    )
    print(email_response.json())
    
    # Step 3: Search emails
    search_response = requests.post(
        f"{BASE_URL}/tools/search_emails",
        json={
            "query": "from:user@example.com",
            "access_token": access_token,
            "max_results": 10
        }
    )
    print(f"Found {len(search_response.json()['results'])} emails")
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

const baseURL = 'http://localhost:5671';
const userId = 'my_app_user';

async function integrateGmail() {
  // Step 1: Get access token
  const authResponse = await axios.post(`${baseURL}/users`, {
    user_id: userId
  });
  
  if (authResponse.data.status === 'needs_authorization') {
    console.log('Authorize at:', authResponse.data.auth_url);
    return;
  }
  
  const accessToken = authResponse.data.access_token;
  
  // Step 2: Send email
  const sendResponse = await axios.post(
    `${baseURL}/tools/send_email`,
    {
      to: 'user@example.com',
      subject: 'Hello from Node.js',
      body: 'Test message',
      access_token: accessToken
    }
  );
  
  console.log('Email sent:', sendResponse.data);
}

integrateGmail();
```

### Make (Zapier Alternative)

**Webhook Setup:**
1. Add "HTTP Request" module
2. Method: POST
3. URL: `http://your-server:5671/tools/send_email`
4. Headers: `Content-Type: application/json`
5. Body:
   ```json
   {
     "to": "{{email}}",
     "subject": "{{subject}}",
     "body": "{{message}}",
     "access_token": "{{access_token}}"
   }
   ```

---

## 🛠️ Troubleshooting Guide

### Issue: "Missing required environment variables"

**Cause:** `.env` file not configured or missing fields

**Solution:**
```bash
cp .env.example .env
# Edit .env and fill all fields:
# - Get GOOGLE_CLIENT_ID/SECRET from https://console.cloud.google.com/apis/credentials
# - Set GOOGLE_REDIRECT_URI to match your domain
# - Generate TOKEN_ENCRYPTION_KEY: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Issue: "PostgreSQL connection error"

**Cause:** Database not running or DATABASE_URL incorrect

**Solution:**
```bash
# Start PostgreSQL
docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15

# Update DATABASE_URL in .env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/google_integrated

# Restart server
```

### Issue: OAuth callback fails / "No authorization code received"

**Cause:** GOOGLE_REDIRECT_URI mismatch or invalid credentials

**Solution:**
1. Check `GOOGLE_REDIRECT_URI` in `.env` matches Google Cloud Console
2. Verify `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are correct
3. Test: `curl http://localhost:5671/debug/auth-url`

### Issue: "Token was revoked" error

**Cause:** User revoked access in Google Account settings

**Solution:**
- User must re-authorize: `POST /users` with same user_id
- System will return `auth_url` again
- User clicks link and authorizes again

### Issue: Health check fails / Port 5671 unreachable

**Cause:** Port mismatch or server not started

**Solution:**
- Verify all ports aligned: docker-compose (5671), config.yml (5671)
- Check server started: `curl http://localhost:5671/health`
- Check logs: `docker-compose logs app`

### Issue: Email send fails / "Invalid recipient"

**Cause:** Invalid email format or permission issue

**Solution:**
- Verify email format is valid
- Check user authorized with correct Gmail account
- Verify `TOKEN_ENCRYPTION_KEY` hasn't changed

### Issue: Search returns no results / "Query syntax error"

**Cause:** Invalid Gmail search syntax

**Solution:**
- Use valid Gmail query syntax: `from:user@example.com`, `subject:important`, `has:attachment`
- See [Gmail Search Operators](https://support.google.com/mail/answer/7190)
- Test: `POST /tools/search_emails` with `query: "label:INBOX"`

---

## ✨ What's Fixed (v1.0.1)

**Critical Issues Resolved:**
- ✅ Port alignment (all components use port 5671)
- ✅ Python 3 compatibility (removed `buffer` type references)
- ✅ Token revocation handling (proper NULL checks in DB)
- ✅ Database initialization (fail-fast on startup)
- ✅ Connection pool detection (identifies broken connections)
- ✅ Environment validation (comprehensive startup checks)
- ✅ OAuth scopes (removed Calendar, focus on Gmail only)
- ✅ Config defaults (search respects max_results setting)
- ✅ Dependencies (pinned versions for stability)
- ✅ Docker healthcheck (working properly)

**Status:** ✅ Production-ready v1.0.1

---

## 🤝 Integration Examples

### n8n
```json
{
  "method": "POST",
  "url": "http://localhost:5677/users",
  "body": {"user_id": "user123"}
}
```

### Python
```python
import requests

# Get token
r = requests.post('http://localhost:5677/users', 
                  json={'user_id': 'user123'})
token = r.json()['access_token']

# Send email
requests.post('http://localhost:5677/tools/send_email',
              json={
                'to': 'user@example.com',
                'subject': 'Hello',
                'body': 'Message',
                'access_token': token
              })
```

---

## 🛠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| Missing env variables | Fill `.env` with your credentials |
| PostgreSQL error | Run: `docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:15` |
| Token revoked | User must re-authorize via POST /users |
| OAuth callback fails | Check GOOGLE_REDIRECT_URI matches Google Cloud Console |

For comprehensive troubleshooting, see **Complete Troubleshooting Guide** above.

---

## 📊 Performance

- **Connections:** 1-20 pooled
- **Email body:** Max 1MB
- **Subject:** Max 998 chars
- **Search results:** Configurable (default 50)
- **Retries:** 3 attempts, exponential backoff

---

## 📋 Technology Stack

- **Framework:** FastAPI 0.109
- **Server:** Uvicorn 0.27
- **Database:** PostgreSQL 15
- **Encryption:** Cryptography (Fernet)
- **HTTP:** HTTPX 0.26 (async)
- **Validation:** Pydantic 2.5
- **Python:** 3.11+

---

## 📖 References

- [Google Gmail API](https://developers.google.com/gmail/api)
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [FastAPI](https://fastapi.tiangolo.com)
- [PostgreSQL](https://www.postgresql.org)

---

**Version:** 1.0.1 | **Status:** ✅ Production Ready | **Updated:** Jan 28, 2026
