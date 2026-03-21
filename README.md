# MySquad Server — FastAPI Backend

The backend services powering the **MySquad** AI assistant platform. Two FastAPI microservices containerised with Docker and deployed behind Traefik reverse proxy.

---

## Services

### 🔗 Google Integrated Server (`/MySquad_scripts/Google-Integrated - Cloud/`)
An MCP (Model Context Protocol) server exposing Google Workspace tools to the n8n AI agent.

**Capabilities:**
- Gmail — send, search, read, draft, label management
- Google Calendar — read/write events
- Google Sheets — read/write data
- Google Docs — read/write documents
- OAuth2 token management with encrypted storage in PostgreSQL

**Port:** `5671`

### 📦 MyGuy Media Server (`/MySquad_scripts/my-guy-media-server - Cloud/`)
Handles media uploads from WhatsApp — receives images and audio, stores them in MinIO, and forwards to the n8n webhook.

**Capabilities:**
- Image upload (JPEG, PNG, WebP, GIF — max 10MB)
- Audio upload (OGG, MP3, WAV, WebM — max 25MB)
- Text message forwarding
- MinIO object storage integration
- Automatic cleanup after n8n processing

**Port:** `5672`

---

## Architecture

```
WhatsApp Business API
        ↓
  Traefik (SSL termination)
        ↓
  ┌─────┴──────────────┐
  │                    │
Google Server     Media Server
(port 5671)       (port 5672)
  │                    │
  └─────┬──────────────┘
        │
   PostgreSQL          MinIO
   (users, tokens)     (media files)
        │
      n8n
   (AI workflows)
```

---

## Prerequisites

| Requirement | Purpose |
|---|---|
| Docker + Docker Compose | Container orchestration |
| Domain name with DNS | Traefik SSL via Let's Encrypt |
| Google Cloud OAuth2 app | Google API access |
| PostgreSQL | User data and token storage |
| MinIO | Media file storage |
| n8n instance | Workflow engine receiving webhooks |

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/Adekunle-1/mysquad-server.git
cd mysquad-server
```

### 2. Configure environment variables

Copy the example files and fill in your values:
```bash
# Root level (controls Traefik, Postgres, n8n, MinIO)
cp .env.example .env

# Google Integrated Server
cp "MySquad_scripts/Google-Integrated - Cloud/.env.example" \
   "MySquad_scripts/Google-Integrated - Cloud/.env"

# Media Server
cp "MySquad_scripts/my-guy-media-server - Cloud/.env.example" \
   "MySquad_scripts/my-guy-media-server - Cloud/.env"
```

Then edit each `.env` file with your actual values.

### 3. Generate encryption key
The Google server encrypts OAuth tokens at rest. Generate a key:
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
Set this as `TOKEN_ENCRYPTION_KEY` in the Google server's `.env`.

### 4. Set up Google OAuth
1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project and enable Gmail, Calendar, Sheets, and Docs APIs
3. Create OAuth2 credentials (Web Application type)
4. Add your redirect URI: `https://google.yourdomain.com/auth/callback`
5. Copy Client ID and Secret to the `.env` file

### 5. Deploy
```bash
docker compose up -d
```

### 6. Initialise the database
On first run, the Google server automatically creates the required tables. To reset:
```bash
docker exec google-integrated-server python3 -c "from app.db import init_db; init_db()"
```

---

## API Endpoints

### Google Integrated Server

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/auth/login?phone_no=...` | Start Google OAuth flow |
| `GET` | `/auth/callback` | OAuth callback |
| `POST` | `/tools/call` | Execute a Google tool |
| `GET` | `/tools` | List available tools |
| `GET` | `/sse` | MCP SSE stream |

### Media Server

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | Upload media (multipart) |
| `POST` | `/chat/text` | Forward text message |

---

## Security

- All secrets loaded via environment variables — nothing hardcoded
- OAuth tokens encrypted at rest using Fernet symmetric encryption
- Database connection pooling (max 20 connections)
- Traefik handles SSL termination with automatic Let's Encrypt certificates
- `.env` files are gitignored and never committed

---

## Related Repositories

- **[mysquad-n8n-workflows](https://github.com/Adekunle-1/mysquad-n8n-workflows)** — n8n automation workflows

---

## License

MIT
