import os
import hmac
import hashlib
from fastapi import APIRouter, Request, Header, HTTPException
from dotenv import load_dotenv
import time
import requests

# Import your existing CICD functions
from CICD.trigger_codebuild import trigger_codebuild
from CICD.code_Deploy import codeDeploy
from CICD.upload_s3 import upload_to_s3
from CICD.addYamlZip import addBuildSpec, addAppSpec, fastapi_buildspec_template, fastapi_appspec_template
from CICD.deploymentScripts import addStartScript, addStopScript, addInstallScript, start_sh_template, stop_sh_template, install_sh_template
from CICD.add_webhook import create_github_webhook
from database import get_access_token_for_owner

load_dotenv()  # Load environment variables

router = APIRouter(prefix="/github")  # All routes here will start with /github


@router.post("/add_webhook")
async def add_webhook(request: Request):
    """
    Endpoint to create GitHub webhook using provided repo details.
    The user's OAuth token is retrieved from the database using the owner/username.
    """
    body = await request.json()

    try:
        owner = body["owner"]  # The GitHub username used for the DB lookup
        repo = body["repo"]
    except KeyError as e:
        # Handle cases where the request body is missing required fields
        raise HTTPException(status_code=400, detail=f"Missing required field: {e.args[0]}")
    
    webhook_url = "https://overslack-stonily-allegra.ngrok-free.dev/github/webhook"

    # 2. Retrieve the clean access token from the database
    try:
        # If the user or token is not found, get_access_token_for_owner 
        # should raise HTTPException(404), which FastAPI handles automatically.
        token = get_access_token_for_owner(owner)
        
    except HTTPException:
        # Re-raise the exception (e.g., 404 Not Found from the database function)
        raise
    except Exception as e:
        # Handle unexpected errors during DB connection/query
        raise HTTPException(status_code=500, detail=f"Database retrieval error: {e}")

    success, response_message = create_github_webhook(owner, repo, token, webhook_url)
    if success:
        return {"status": "success", "message": response_message}
    else:
        raise HTTPException(status_code=400, detail=f"GitHub API Error: Failed to create webhook. Response: {response_message}")


@router.post("/webhook")
async def github_webhook(request: Request):
    """
    Test route — prints the payload when GitHub pushes code
    """

    event_type = request.headers.get('X-GitHub-Event')

    if event_type == 'ping':
        print("Webhook ping received. Responding OK.")
        # Return a 200 OK without processing the payload
        return {"message": "pong"}
    
    body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()

    # verify signature if secret exists
    if secret and signature_header:
        digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
        expected = f"sha256={digest}"
        if not hmac.compare_digest(expected, signature_header):
            print("Invalid webhook signature")
            return {"message": "Invalid signature"}

    payload = await request.json()
    print("Webhook received!")

    repo_url = payload["repository"]["clone_url"]

    owner = repo_url.split("/")[3]
    repo = repo_url.split("/")[4].replace(".git", "")
    ref = payload["ref"].split("/")[-1]

    zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{ref}"
    out_file = f"{repo}-{ref}.zip" 
    S3_BUCKET_NAME = "foundry-codebuild-zip"
    S3_KEY = f"{owner}/{out_file}"

    response = requests.get(zip_url, allow_redirects=True)
    if response.status_code == 200:
        with open(out_file, "wb") as f:
            f.write(response.content)
        path = addBuildSpec(out_file, fastapi_buildspec_template, overWrite=True)
        addAppSpec(out_file, fastapi_appspec_template, overWrite=True)
        addStopScript(out_file, stop_sh_template, overWrite=True)
        addInstallScript(out_file, install_sh_template, overWrite=True)
        addStartScript(out_file, start_sh_template, overWrite=True)
    else:
        print(f"Failed to download repo: {response.status_code}")
        return {"message": "Download failed"}

    upload_to_s3(out_file, S3_BUCKET_NAME, S3_KEY)
    time.sleep(10)

    build_status = trigger_codebuild("foundryCICD", S3_BUCKET_NAME, S3_KEY, path, f"{owner}-{repo}")
    if build_status["build_status"] == "SUCCEEDED":
        codeDeploy(owner, repo, "foundry-artifacts-bucket", f"founryCICD-{owner}-{repo}")
        return {"message": "Build and deploy completed successfully"}
    else:
        return {"message": "Build failed, skipping deploy"}