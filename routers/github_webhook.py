# routers/github_webhook.py

import os
import hmac
import hashlib
from fastapi import APIRouter, Request, Header, HTTPException
from dotenv import load_dotenv

# Import your existing CICD functions
from CICD.trigger_codebuild import trigger_codebuild
from CICD.code_Deploy import codeDeploy
from CICD.upload_s3 import upload_to_s3
from CICD.addYamlZip import addBuildSpec, addAppSpec, fastapi_buildspec_template, fastapi_appspec_template
from CICD.deploymentScripts import addStartScript, addStopScript, addInstallScript, start_sh_template, stop_sh_template, install_sh_template

load_dotenv()  # Load environment variables

router = APIRouter(prefix="/github")  # All routes here will start with /github


@router.post("/webhook")
async def github_webhook(request: Request, x_hub_signature_256: str | None = Header(None)):
    """
    Receives GitHub push events and triggers redeploy
    """

    body = await request.body()

    # verify signature makes sure that
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "").encode()
    if secret and x_hub_signature_256:
        digest = hmac.new(secret, body, hashlib.sha256).hexdigest()
        expected_signature = f"sha256={digest}"
        if not hmac.compare_digest(expected_signature, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid signature — not from GitHub")

    # 3️⃣ Parse payload
    payload = await request.json()
    repo_url = payload["repository"]["html_url"]
    branch = payload["ref"].split("/")[-1]
    owner = repo_url.split("/")[-2]
    repo_name = repo_url.split("/")[-1]

    print(f"🔔 Push detected on {repo_url} [{branch}]")

    # 4️⃣ Prepare S3 zip key and local zip filename
    zip_url = f"https://api.github.com/repos/{owner}/{repo_name}/zipball/{branch}"
    out_file = f"{repo_name}-{branch}.zip"
    s3_bucket = "foundry-codebuild-zip"
    s3_key = f"{owner}/{out_file}"

    # 5️⃣ Download zip
    import requests
    response = requests.get(zip_url, allow_redirects=True)
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"Failed to download repo zip: {response.status_code}")
    with open(out_file, "wb") as f:
        f.write(response.content)

    # 6️⃣ Inject buildspec/appspec/scripts
    addBuildSpec(out_file, fastapi_buildspec_template, overWrite=True)
    addAppSpec(out_file, fastapi_appspec_template, overWrite=True)
    addStopScript(out_file, stop_sh_template, overWrite=True)
    addInstallScript(out_file, install_sh_template, overWrite=True)
    addStartScript(out_file, start_sh_template, overWrite=True)

    # 7️⃣ Upload to S3
    upload_to_s3(out_file, s3_bucket, s3_key)

    # 8️⃣ Trigger CodeBuild
    status = trigger_codebuild("foundryCICD", s3_bucket, s3_key, "buildspec.yml", f"{owner}-{repo_name}")

    # 9️⃣ Trigger CodeDeploy if build succeeded
    if status.get("build_status") == "SUCCEEDED":
        codeDeploy(owner, repo_name, "foundry-artifacts-bucket", f"founryCICD-{owner}-{repo_name}")
        print(f"✅ Redeploy triggered for {repo_url}")

    return {"message": f"Redeploy triggered for {repo_url}:{branch}"}
