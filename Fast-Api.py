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
