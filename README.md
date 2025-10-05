VectorShift Integrations – Setup Guide (Backend + Frontend)

This guide helps you run the project on a completely new device (Windows, macOS, or Linux).

Prerequisites
- Git
- Node.js (LTS recommended, e.g., 18.x)
- Docker (for Redis), or a local Redis service
- Python 3.11 (recommended for backend)

Project Structure
- backend: FastAPI app and integrations
- frontend: React app

1) Redis (Docker)
Recommended: run Redis with port mapping so the backend can connect to localhost:6379.

Windows/macOS/Linux (PowerShell/Terminal):
```
docker run -d --name redis --restart unless-stopped -p 6379:6379 redis:7
docker exec -it redis redis-cli ping  # expect PONG
```

If port 6379 is in use, stop the conflicting container or map another host port (e.g., -p 6380:6379) and adjust the backend to use that host port.

2) Backend (FastAPI)
From the project root:
```
cd backend
```

Create and activate a Python 3.11 virtual environment:
Windows (PowerShell):
```
py -3.11 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -V  # should be 3.11.x
```


Install minimal required packages (fast install):
```
python -m pip install --upgrade pip setuptools wheel
pip install fastapi==0.94.0 uvicorn==0.21.0 httpx==0.24.1 requests==2.28.2 redis==4.6.0 python-multipart==0.0.6
```

Set environment variables (HubSpot OAuth):
- Create a HubSpot developer app and configure:
  - Scopes: `crm.objects.contacts.read crm.objects.deals.read`
  - Redirect URL: `http://localhost:8000/integrations/hubspot/oauth2callback`
- Copy Client ID and Client Secret.

Windows (PowerShell):
```
$env:HUBSPOT_CLIENT_ID="YOUR_CLIENT_ID"
$env:HUBSPOT_CLIENT_SECRET="YOUR_CLIENT_SECRET"
$env:HUBSPOT_REDIRECT_URI="http://localhost:8000/integrations/hubspot/oauth2callback"
$env:REDIS_HOST="127.0.0.1"
```


Run the backend:
```
uvicorn main:app --reload
```

The API starts at http://localhost:8000

3) Frontend (React)
From the project root:
```
cd frontend
npm install
npm start
```

The app opens at http://localhost:3000

4) Using the App
1. Open the app at http://localhost:3000
2. Select an integration (e.g., HubSpot) in the dropdown.
3. Click "Connect to HubSpot" and complete OAuth in the popup.
4. After the popup closes, click "Load Data" to fetch sample items (contacts).

Troubleshooting
- Redis connection error: Ensure Docker Redis is published on localhost:6379 (`docker ps` shows `0.0.0.0:6379->6379`).
- OAuth redirect mismatch: Confirm your HubSpot app Redirect URL matches `HUBSPOT_REDIRECT_URI` exactly.
- Python dependency errors: Use Python 3.11 and the minimal packages list above. If you prefer using `requirements.txt`, you may need system build tools and additional libraries.

Environment Persistence (optional)
Windows (persist env vars):
```
setx HUBSPOT_CLIENT_ID "YOUR_CLIENT_ID"
setx HUBSPOT_CLIENT_SECRET "YOUR_CLIENT_SECRET"
setx HUBSPOT_REDIRECT_URI "http://localhost:8000/integrations/hubspot/oauth2callback"
setx REDIS_HOST "127.0.0.1"
```
Open a new terminal for them to take effect.


