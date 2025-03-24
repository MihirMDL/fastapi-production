
# ✅ Complete Production Setup: NGINX + systemd + Gunicorn

This guide provides a fully production-ready FastAPI deployment with:

- **NGINX** as the reverse proxy  
- **systemd** to manage FastAPI as a background service  
- **Gunicorn** to handle multiple worker processes for better performance  

---

Prerequisite

To install modules run 

- pip install -r requirements.txt

To Freeze and Update Requirements
If you add new dependencies, you can regenerate the requirements.txt by running:

- pip freeze > requirements.txt

To Run uvicorn command 

- uvicorn Fast-Api:app --host 0.0.0.0 --port 8118 --reload

## 🔥 1. FastAPI App: `main.py`

First, create the FastAPI app with Docker commands:

```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import subprocess
import json
import re

app = FastAPI()

# Docker Containers and Paths
EDGEX_CONTAINER = "edgex-security-proxy-setup"
CHIRPSTACK_CONTAINER = "chirpstack-chirpstack-1"
ROOT_CONTAINER = "edgex-security-secretstore-setup"
ROOT_FILE_PATH = "/vault/config/assets/resp-init.json"

def run_docker_command(cmd, mode="generic"):
    """Run Docker command and handle output based on mode."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=True
        )
        output = result.stdout.strip()

        # Mode-based parsing
        if mode == "chirpstack":
            api_key_data = {}
            lines = output.split("
")
            for line in lines:
                if line.startswith("id:"):
                    api_key_data["id"] = line.split("id:")[-1].strip()
                elif line.startswith("token:"):
                    api_key_data["token"] = line.split("token:")[-1].strip()
            return api_key_data if api_key_data else {"error": "Failed to parse ChirpStack API key"}

        elif mode == "edgex":
            try:
                parsed = json.loads(output)
                return {
                    "username": parsed.get("username", "N/A"),
                    "password": parsed.get("password", "No password found")
                }
            except json.JSONDecodeError:
                return {"error": "Unexpected EdgeX response", "raw_output": output}

        elif mode == "root":
            tokens = re.findall(r'"root_token"\s*:\s*"([^"]+)"', output)
            return tokens or {"message": "No root tokens found."}

        return {"output": output}

    except subprocess.CalledProcessError as e:
        return {"error": f"Command failed: {e.stderr.strip()}"}
    except Exception as ex:
        return {"error": str(ex)}

@app.get("/")
def home():
    """Home Endpoint"""
    return {"message": "Welcome to the ChirpStack, EdgeX, and Root Token Manager!"}
```
---

## 🔥 2. Gunicorn Configuration Script

✅ Create a Gunicorn service that runs FastAPI with multiple workers.

📌 **File:** `/etc/systemd/system/fastapi-daemon.service`

```ini
[Unit]
Description=FastAPI App with Gunicorn
After=network.target

[Service]
User=root
WorkingDirectory=/path/to/your/fastapi/app
ExecStart=/usr/bin/gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 127.0.0.1:8000 main:app
Restart=always

[Install]
WantedBy=multi-user.target
```
---

## 🔥 3. NGINX Configuration

✅ NGINX will act as a reverse proxy to forward requests to Gunicorn.

📌 **File:** `/etc/nginx/sites-available/fastapi`

```nginx
server {
    listen 80;
    server_name 183.82.1.171;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /docs {
        proxy_pass http://127.0.0.1:8000/docs;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:8000/redoc;
    }

    location /static/ {
        alias /path/to/your/fastapi/app/static/;
        expires 30d;
    }
}
```
---

## 🔥 4. Deployment Steps

✅ Install dependencies:
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx gunicorn
```
✅ Create and activate the virtual environment:
```bash
cd /path/to/your/fastapi/app
python3 -m venv env
source env/bin/activate
pip install fastapi uvicorn gunicorn
```
✅ Start Gunicorn with systemd:
```bash
sudo systemctl enable fastapi-daemon
sudo systemctl start fastapi-daemon
sudo systemctl status fastapi-daemon
```
✅ Enable NGINX configuration:
```bash
sudo ln -s /etc/nginx/sites-available/fastapi /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```
✅ Verify your app:
```bash
curl http://183.82.1.171
```
✅ Check logs:
```bash
# FastAPI logs
sudo journalctl -u fastapi-daemon

# NGINX logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log
```
---

## 🚀 **Final Architecture**
```
[Client] ---> [NGINX] ---> [Gunicorn with FastAPI] ---> [Docker Containers]
                     ↑
                  [systemd]
```

---

## ✅ **Advantages of This Setup**
- **High Performance:** Gunicorn handles multiple worker processes.  
- **Stability:** systemd ensures FastAPI automatically restarts if it crashes.  
- **Scalability:** NGINX handles SSL, static content, and can be scaled with load balancing.  
- **Security:** NGINX acts as a reverse proxy, protecting your FastAPI app.  

🔥 Your FastAPI app is now production-ready with NGINX, systemd, and Gunicorn! 🚀
