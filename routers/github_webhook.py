import os
import hmac
import hashlib
from fastapi import APIRouter, Request, Header, HTTPException, WebSocket,WebSocketDisconnect
from dotenv import load_dotenv
import time
import requests
import boto3
# Import your existing CICD functions
from CICD.trigger_codebuild import trigger_codebuild
from CICD.code_Deploy import codeDeploy
from CICD.upload_s3 import upload_to_s3
from CICD.addYamlZip import addBuildSpec, addAppSpec, fastapi_buildspec_template, fastapi_appspec_template
from CICD.deploymentScripts import addStartScript, addStopScript, addInstallScript, start_sh_template, stop_sh_template, install_sh_template
from CICD.add_webhook import create_github_webhook
from database import get_access_token_for_owner
from database import get_access_token_for_owner
import asyncpg
load_dotenv()  # Load environment variables
build_id_store = {}
build_id_store = {}
router = APIRouter(prefix="/github")  # All routes here will start with /github


sockets: dict[str, WebSocket] = {}

async def emit(build_id, message: str): 
    websocket = sockets.get(build_id)

    print(",websocket",websocket)
    if websocket:
        await websocket.send_text(message)
    else:
        print("no connection")


   



sockets: dict[str, WebSocket] = {} #global dictionary 

@router.websocket("/ws/{build_id}")
async def ws_build(websocket: WebSocket, build_id: str):
    
    await websocket.accept()
    sockets[build_id] = websocket

   

  

    try: 
        while True:
            data = await websocket.receive_text()
           
      
           
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for build_id {build_id}")
        sockets.pop(build_id, None)



@router.post("/add_webhook")
async def add_webhook(request: Request):
    """
    Endpoint to create GitHub webhook using provided repo details.
    The user's OAuth token is retrieved from the database using the owner/username.
    """
    body = await request.json()
    try:
        owner = body["owner"]
        repo = body["repo"]
        build_id = body["build_id"]

  
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e.args[0]}")

    build_id_store[(owner, repo)] = build_id
    print(f"Stored build_id: {build_id} for {owner}/{repo}")

    try:
        token = get_access_token_for_owner(owner)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving token for {owner}: {e}")

    try:
        owner = body["owner"]
        repo = body["repo"]
        build_id = body["build_id"]
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e.args[0]}")

    build_id_store[(owner, repo)] = build_id
    print(f"Stored build_id: {build_id} for {owner}/{repo}")

    try:
        token = get_access_token_for_owner(owner)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving token for {owner}: {e}")

    webhook_url = "https://overslack-stonily-allegra.ngrok-free.dev/github/webhook"  # Update with correct URL

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
    # print("Webhook received!",payload)

    repo_url = payload["repository"]["clone_url"]

    owner = repo_url.split("/")[3]
    repo = repo_url.split("/")[4].replace(".git", "")
    event = request.headers.get("X-GitHub-Event")
    print(f"GitHub event: {event}")

    # Handle ping event (sent immediately after webhook creation)
    if event == "ping":
        print("Received ping event from GitHub — webhook setup successful.")
        return {"message": "pong"}

    # Only push events have a ref field
    if "ref" not in payload:
        print("No ref in payload — skipping.")
        return {"message": "Ignored non-push event"}
    event = request.headers.get("X-GitHub-Event")
    # print(f"GitHub event: {event}")

    # Handle ping event (sent immediately after webhook creation)
    if event == "ping":
        print("Received ping event from GitHub — webhook setup successful.")
        return {"message": "pong"}

    # Only push events have a ref field
    if "ref" not in payload:
        print("No ref in payload — skipping.")
        return {"message": "Ignored non-push event"}
    ref = payload["ref"].split("/")[-1]

    build_id = build_id_store.get((owner, repo), None)
    print(f"Retrieved build_id: {build_id} for {owner}/{repo}")
    

    
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
    time.sleep(2)

    build_status = await trigger_codebuild("foundryCICD", S3_BUCKET_NAME, S3_KEY, path, f"{owner}-{repo}",build_id,emit)
    if build_status["build_status"] == "SUCCEEDED":
        await codeDeploy(owner, repo, "foundry-artifacts-bucket", f"founryCICD-{owner}-{repo}", build_id, emit)
        
        ec2_details = boto3.client('ec2', region_name='us-east-1')
        ec2_address = ec2_details.describe_instances(Filters=[{'Name': 'tag:BuildId', 'Values': [build_id]}])

        print("response",ec2_address['Reservations'][0]['Instances'][0]['PublicIpAddress'])

        try: 
            database = os.getenv("DATABASE_URL")

            connect = await asyncpg.connect(database)

            public_ip = ec2_address['Reservations'][0]['Instances'][0]['PublicIpAddress']


            endpoint =  f"http://{public_ip}:8000"
               

            update = await connect.execute("UPDATE build SET endpoint = $1 WHERE id = $2",endpoint,int(build_id))


            print("update",update)

            return {"endpoint": endpoint}
        
        except Exception as e:
            
            print("failed to fetch ec2 details",e)
             

      