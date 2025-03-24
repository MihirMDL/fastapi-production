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
from fastapi import FastAPI, HTTPException, Path
from fastapi.responses import JSONResponse
import json
import re
import logging
import subprocess

# === Logging Configuration ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(funcName)s - %(message)s"
)

# === Initialize FastAPI app ===
app = FastAPI()

# === Docker Configuration ===
CONTAINERS = {
    "edgex": "edgex-security-proxy-setup",
    "chirpstack": "chirpstack-chirpstack-1",
    "root": "edgex-security-secretstore-setup"
}
ROOT_FILE_PATH = "/vault/config/assets/resp-init.json"


# === Docker Command Execution ===
def run_docker_command(command: str) -> dict:
    """
    Runs a Docker command and returns the output or error.

    Args:
        command (str): The Docker command to execute.

    Returns:
        dict: Output or error response.
    """
    try:
        logging.info(f"Executing Docker command: {command}")
      
        result = subprocess.run(command, shell=True, capture_output=True, text=True)

        if result.returncode != 0:
            logging.error(f"Command failed: {result.stderr}")
            return {"error": result.stderr.strip()}

        logging.info(f"Command output: {result.stdout.strip()}")
        return {"output": result.stdout.strip()}

    except Exception as ex:
        logging.exception("Unexpected error occurred.")
        return {"error": str(ex)}


# === Output Parsing Functions ===
def parse_chirpstack_output(output: str) -> dict:
    """Parse ChirpStack API key creation output."""
    api_key_data = {}
    for line in output.split("\n"):
        if line.startswith("id:"):
            api_key_data["id"] = line.split("id:")[-1].strip()
        elif line.startswith("token:"):
            api_key_data["token"] = line.split("token:")[-1].strip()

    if not api_key_data:
        return {"error": "Failed to parse ChirpStack API key", "raw_output": output}
    return api_key_data


def parse_edgex_output(output: str) -> dict:
    """Parse EdgeX password creation output."""
    try:
        parsed = json.loads(output)
        if not parsed:
            return {"error": "EdgeX response was empty", "raw_output": output}

        return {
            "username": parsed.get("username", "N/A"),
            "password": parsed.get("password", "No password found"),
        }

    except json.JSONDecodeError:
        logging.error(f"Failed to parse EdgeX response: {output}")
        return {"error": "Unexpected EdgeX response", "raw_output": output}


def parse_root_tokens(output: str) -> dict:
    """Parse root tokens from JSON output."""
    tokens = re.findall(r'"root_token"\s*:\s*"([^"]+)"', output)

    if not tokens:
        return {"message": "No root tokens found.", "raw_output": output}

    return {"tokens": tokens}


# === FastAPI Endpoints ===
@app.get("/", summary="Home", description="Welcome message for the token manager.")
def home():
    """Home endpoint with welcome message."""
    logging.info("Home endpoint accessed.")
    return JSONResponse(
        content={"message": "Welcome to the ChirpStack, EdgeX, and Root Token Manager!"},
        status_code=200
    )


@app.get("/generate-password/{username}", summary="Generate EdgeX Password", description="Generates a password for EdgeX.")
async def generate_password(username: str):
    """Generate EdgeX password using Docker commands."""
    logging.info(f"Generating password for: {username}")

    cmd = (
        f"docker exec {CONTAINERS['edgex']} ./secrets-config proxy adduser "
        f"--user \"{username}\" --tokenTTL 60 --jwtTTL 119m --useRootToken"
    )

    result = run_docker_command(cmd)

    if "error" in result:
        return JSONResponse(content=result, status_code=500)

    parsed_result = parse_edgex_output(result["output"])
  
    if "error" in parsed_result:
        return JSONResponse(content=parsed_result, status_code=404)

    return JSONResponse(content={
        "message": f"User {username} created successfully.",
        "password": parsed_result["password"]
    }, status_code=200)


@app.get("/create-chirpstack-api-key/{name}", summary="Create ChirpStack API Key", description="Creates an API key in ChirpStack.")
async def create_api_key(name: str = Path(..., min_length=1, description="API key name")):
    """Create ChirpStack API Key using Docker commands."""

    if not name.strip() or name == ":name" or not re.match(r'^[a-zA-Z0-9_\-]+$', name):
        logging.warning("Invalid API key name received.")
        return JSONResponse(content={"error": "Invalid or missing 'name' parameter"}, status_code=404)

    logging.info(f"Creating ChirpStack API key for: {name}")

    cmd = (
        f"docker exec {CONTAINERS['chirpstack']} "
        f"chirpstack --config /etc/chirpstack "
        f"create-api-key --name '{name}'"
    )

    result = run_docker_command(cmd)

    if "error" in result:
        return JSONResponse(content=result, status_code=500)

    parsed_result = parse_chirpstack_output(result["output"])

    if "error" in parsed_result:
        return JSONResponse(content=parsed_result, status_code=404)

    return JSONResponse(content={"name": name, "result": parsed_result}, status_code=200)


@app.get("/tokens", summary="Get All Root Tokens", description="Extracts all root tokens and returns them as JSON.")
def get_tokens():
    """Extract all root tokens from Docker container and return them as JSON."""
    logging.info("Extracting all root tokens...")

    cmd = f"docker exec {CONTAINERS['root']} cat {ROOT_FILE_PATH}"
  
    result = run_docker_command(cmd)

    if "error" in result:
        return JSONResponse(content=result, status_code=500)

    parsed_result = parse_root_tokens(result["output"])

    if "tokens" not in parsed_result or not parsed_result["tokens"]:
        return JSONResponse(content={"message": "No root tokens found."}, status_code=404)

    return JSONResponse(content=parsed_result, status_code=200)
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
