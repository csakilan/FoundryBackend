import time
from fastapi import FastAPI, Request
import hmac
import hashlib
import os
from dotenv import load_dotenv
import requests
from CICD.trigger_codebuild import trigger_codebuild
from CICD.code_Deploy import codeDeploy
from CICD.addYamlZip import addBuildSpec, addAppSpec,fastapi_buildspec_template, fastapi_appspec_template
from CICD.deploymentScripts import addStartScript,start_sh_template,stop_sh_template,addStopScript,addInstallScript,install_sh_template
from CICD.upload_s3 import upload_to_s3
from github_webhook_test.add_webhook import create_github_webhook

load_dotenv()

app = FastAPI()

# add webhook adds a webhook to the user's github. decide when to do this (when the user first uploads their repo probs)

@app.post("/add_webhook")
async def add_webhook(request: Request):
    body = await request.json()
    owner = body["owner"]
    repo = body["repo"]
    token = body["token"]
    webhook_url = "https://overslack-stonily-allegra.ngrok-free.dev/github/webhook"
    success, response_message = create_github_webhook(owner, repo, token, webhook_url)
    if success:
        return {"status": "success", "message": response_message}
    else:
        return {"status": "error", "message": response_message}

@app.post("/github/webhook")
async def github_webhook(request: Request):
    """
    Test route — prints the payload when GitHub pushes code
    """
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