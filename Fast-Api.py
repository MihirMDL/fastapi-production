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
            lines = output.split("\n")
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


#  EdgeX - Generate Password
@app.get("/generate-password", summary="Generate EdgeX Password", description="Generates a password for EdgeX.")
async def generate_password(username: str):
    """Generate EdgeX password using Docker commands"""
    cmd = (
        f"docker exec {EDGEX_CONTAINER} ./secrets-config proxy adduser "
        f"--user \"{username}\" --tokenTTL 60 --jwtTTL 119m --useRootToken"
    )

    result = run_docker_command(cmd, mode="edgex")

    return {
        "username": username,
        "result": result
    }


#  ChirpStack - Create API Key
@app.get("/create-chirpstack-api-key", summary="Create ChirpStack API Key", description="Creates an API key in ChirpStack.")
async def create_api_key(name: str):
    """Create ChirpStack API Key using Docker commands"""
    cmd = (
        f"docker exec {CHIRPSTACK_CONTAINER} "
        f"chirpstack --config /etc/chirpstack "
        f"create-api-key --name '{name}'"
    )

    result = run_docker_command(cmd, mode="chirpstack")

    return {
        "name": name,
        "result": result
    }


#  Root Tokens - Extract and Display
@app.get("/tokens", summary="Get Root Tokens", description="Extracts root tokens and returns them as JSON.")
def get_tokens():
    """Extract root tokens and return them as JSON."""
    cmd = f"docker exec {ROOT_CONTAINER} cat {ROOT_FILE_PATH}"
    tokens = run_docker_command(cmd, mode="root")

    if isinstance(tokens, dict) and "error" in tokens:
        return JSONResponse(content=tokens, status_code=500)

    return JSONResponse(content={"tokens": tokens})
