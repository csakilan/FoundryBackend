from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from CFCreators import CFCreator
import json
from pathlib import Path
import httpx
from database import save_build, log_activity, get_build, update_build_canvas_and_template, get_builds_by_owner
import boto3
from CICD.addYamlZip import addAppSpec, addBuildSpec, fastapi_appspec_template,fastapi_buildspec_template
from CICD.upload_s3 import upload_to_s3
import time
from CICD.trigger_codebuild import trigger_codebuild
from CICD.deploymentScripts import addStartScript,start_sh_template,stop_sh_template,addStopScript,addInstallScript,install_sh_template
from CICD.code_Deploy import codeDeploy
import requests
#settings imports 
from settings.get_user import get_users
from dotenv import load_dotenv
import os
import asyncpg,asyncio
from datetime import datetime

import random

from logs.logs import ec2_log

from costs.s3 import get_price
from costs.ec2 import ec2_price
# from costs.dynamo   import dynamoCost
# Import deployment tracking
from CFCreators.deploymentModal.websocket_handler import deployment_ws_manager





router = APIRouter(prefix="/canvas")
builds = APIRouter(prefix="/builds")


class DeployRequest(BaseModel):
    buildId: int  # REQUIRED - Build ID from /builds/new
    canvas: dict
    owner_id: int = 1  # Default user ID (TODO: Replace with actual auth)
    region: str = 'us-east-1'  # AWS region


class UpdateRequest(BaseModel):
    canvas: Optional[dict] = None  # Canvas data (can be nested or at root)
    build_id: Optional[int] = None  # ID of the build to update
    stack_name: Optional[str] = None  # CloudFormation stack name to update
    owner_id: int = 1  # Default user ID (TODO: Replace with actual auth)
    region: str = 'us-east-1'  # AWS region
    auto_execute: bool = False  # If True, automatically execute the change set


class DeleteRequest(BaseModel):
    stack_name: str  # CloudFormation stack name to delete
    build_id: Optional[int] = None  # Optional build ID for database updates
    owner_id: int = 1  # Default user ID (TODO: Replace with actual auth)
    region: str = 'us-east-1'  # AWS region
    cleanup_key_pairs: bool = True  # Whether to delete SSH key pairs
    auto_execute: bool = False  # If True, automatically execute the change set


@router.get('/health')
def get_health():
    return "this shi working dawg"

@router.post('/deploy')
def deploy_initiate(request: DeployRequest):
    """
    Deploy canvas infrastructure to AWS CloudFormation.
    
    Args:
        request: DeployRequest containing:
            - buildId: Build ID from /builds/new (REQUIRED)
            - canvas: Frontend ReactFlow JSON
            - owner_id: User ID (default: 1)
            - region: AWS region (default: us-east-1)
        
    Returns:
        Deployment result with stack information and build_id
    """
    print("=" * 80)
    print("DEPLOYMENT REQUEST RECEIVED")
    print("=" * 80)
    print(f"Build ID: {request.buildId}")
    print(f"Owner ID: {request.owner_id}")
    print(f"Region: {request.region}")
    print(f"Canvas nodes: {len(request.canvas.get('nodes', []))}")
    
    # Get build_id from request (created in /builds/new)
    build_id = request.buildId
    canvas_data = request.canvas
    
    # Verify build exists in database
    try:
        existing_build = get_build(build_id)
        if not existing_build:
            raise HTTPException(
                status_code=404,
                detail=f"Build ID {build_id} not found. Please create a new build first with /builds/new"
            )
        print(f"✓ Build {build_id} found in database")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error checking build: {str(e)}"
        )
    
    # Deploy to AWS using CFCreator with build_id
    try:
        print(f"\n[1/3] Deploying to AWS with build_id={build_id}...")
        result = CFCreator.deployToAWS(
            canvas_data=canvas_data,
            stack_name=None,  # Auto-generate using build_id
            region=request.region,
            build_id=str(build_id)  # Pass database ID for resource naming
        )
        
        if result['success']:
            print("\n✓ Deployment successful!")
            
            # Step 2: Update database with canvas and CloudFormation template
            try:
                print(f"\n[2/3] Updating build {build_id} with canvas and CF template...")
                
                # Get the generated CloudFormation template
                from CFCreators.CFCreator import createGeneration
                cf_template = createGeneration(canvas_data, build_id=str(build_id), save_to_file=True)
                template_json = json.loads(cf_template.to_json())
                
                # Update build with canvas and CF template
                update_build_canvas_and_template(
                    build_id=build_id,
                    canvas=canvas_data,
                    cf_template=template_json
                )
                
                print(f"✓ Build {build_id} updated successfully")
                
                # Log successful deployment activity
                print(f"\n[3/3] Logging deployment activity...")
                log_activity(
                    build_id=build_id,
                    user_id=request.owner_id,
                    change=f"Deployed to AWS: {result['stackName']} in {result['region']} (Status: {result['status']})"
                )
                
                print("✓ Activity logged")
                
            except Exception as update_error:
                # Log update error but don't fail the deployment response
                print(f"\n⚠ Warning: Database update failed: {str(update_error)}")
                print("Deployment was successful, but canvas/template was not saved to database")
            
            return {
                "success": True,
                "message": "Deployment initiated successfully",
                "stackId": result['stackId'],
                "stackName": result['stackName'],  # camelCase
                "stack_name": result['stackName'],  # snake_case for compatibility
                "region": result['region'],
                "status": result['status'],
                "outputs": result.get('outputs', []),
                "keyPairs": result.get('keyPairs', {}),  # SSH key pairs for EC2 instances
                "buildId": build_id,  # camelCase for JavaScript convention
                "build_id": build_id  # snake_case for Python convention (redundant but ensures compatibility)
            }
        else:
            print(f"\n✗ Deployment failed: {result.get('message')}")
            raise HTTPException(
                status_code=500,
                detail=result.get('message', 'Deployment failed')
            )
            
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Deployment error: {str(e)}"
        )


@router.get('/deploy/status/{stack_name}')
def get_deployment_status(stack_name: str, region: str = 'us-east-1'):
    """
    Get the current status of a CloudFormation stack deployment.
    
    Args:
        stack_name: Name of the CloudFormation stack
        region: AWS region (default: us-east-1)
        
    Returns:
        Stack status and outputs
    """
    try:
        result = CFCreator.getStackStatus(stack_name, region)
        
        if result['success']:
            return {
                "success": True,
                "stackName": result['stackName'],
                "region": result['region'],
                "status": result['status'],
                "outputs": result.get('outputs', [])
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=result.get('message', 'Stack not found')
            )
            
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting stack status: {str(e)}"
        )


@router.post('/deploy/update')
def deploy_update(request: UpdateRequest):
    """
    Update an existing CloudFormation stack with a new canvas.
    
    This endpoint:
    1. Retrieves the old canvas from the database
    2. Generates a new CloudFormation template from the new canvas
    3. Creates a change set to preview changes
    4. Optionally executes the change set (if auto_execute=True)
    5. Updates the database with the new canvas and template
    
    Args:
        request: UpdateRequest containing:
            - canvas: New ReactFlow canvas JSON
            - build_id: ID of the build to update
            - stack_name: CloudFormation stack name to update
            - owner_id: User ID (default: 1)
            - region: AWS region (default: us-east-1)
            - auto_execute: Whether to automatically execute changes (default: False)
        
    Returns:
        Update result with change set details and execution status
    """
    print("=" * 80)
    print("UPDATE REQUEST RECEIVED")
    print("=" * 80)
    
    # Validate required fields
    if not request.build_id:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: build_id. The update endpoint requires build_id to identify which build to update."
        )
    
    if not request.stack_name:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: stack_name. The update endpoint requires stack_name to identify which CloudFormation stack to update."
        )
    
    if not request.canvas:
        raise HTTPException(
            status_code=400,
            detail="Missing required field: canvas. The update endpoint requires canvas data to generate the new CloudFormation template."
        )
    
    print(f"Build ID: {request.build_id}")
    print(f"Stack Name: {request.stack_name}")
    print(f"Owner ID: {request.owner_id}")
    print(f"Region: {request.region}")
    print(f"Auto Execute: {request.auto_execute}")
    print(f"Canvas nodes: {len(request.canvas.get('nodes', []))}")
    
    try:
        # Step 1: Get the old build from database
        from database import get_build, update_build_canvas_and_template
        
        print(f"\n[1/5] Retrieving existing build from database...")
        old_build = get_build(request.build_id)
        
        if not old_build:
            raise HTTPException(
                status_code=404,
                detail=f"Build with ID {request.build_id} not found"
            )
        
        print(f"  ✓ Build retrieved: {old_build['id']}")
        print(f"    - Created: {old_build['created_at']}")
        print(f"    - Previous canvas nodes: {len(old_build['canvas'].get('nodes', []))}")
        
        # Step 2: Generate new CloudFormation template from new canvas
        print(f"\n[2/5] Generating new CloudFormation template...")
        from CFCreators.CFCreator import createGeneration
        new_cf_template = createGeneration(request.canvas)
        new_template_json = new_cf_template.to_json()
        new_template_dict = json.loads(new_template_json)
        
        print(f"  ✓ New template generated")
        print(f"    - Resources: {list(new_template_dict.get('Resources', {}).keys())}")
        
        # Step 3: Create change set
        print(f"\n[3/5] Creating CloudFormation change set for stack '{request.stack_name}'...")
        from CFCreators.aws_deployer import CloudFormationDeployer
        deployer = CloudFormationDeployer(region=request.region)
        
        # Get VPC resources
        vpc_resources = deployer.get_default_vpc_resources()
        
        # Check if template has RDS and setup DB Subnet Group if needed
        has_rds = any(node.get("type") == "RDS" for node in request.canvas.get("nodes", []))
        if has_rds:
            db_subnet_group = deployer.get_or_create_db_subnet_group(vpc_resources['VpcId'])
            vpc_resources['DBSubnetGroupName'] = db_subnet_group
        
        # Create change set
        change_set_result = deployer.update_stack(
            stack_name=request.stack_name,
            template_body=new_template_json,
            parameters=vpc_resources
        )
        
        print(f"  ✓ Change set created: {change_set_result['changeSetName']}")
        print(f"    - Status: {change_set_result['status']}")
        print(f"    - Has changes: {change_set_result['hasChanges']}")
        print(f"    - Change count: {len(change_set_result['changes'])}")
        
        # Step 5: Execute change set if auto_execute is True
        executed = False
        if request.auto_execute and change_set_result['hasChanges']:
            print(f"\n[4/5] Auto-executing change set...")
            stack_id = deployer.execute_change_set(
                stack_name=request.stack_name,
                change_set_name=change_set_result['changeSetName']
            )
            executed = True
            print(f"  ✓ Change set executed - stack update in progress")
        else:
            print(f"\n[4/5] Change set created but not executed (auto_execute={request.auto_execute})")
        
        # Step 6: Update database with new canvas and template
        print(f"\n[5/5] Updating database...")
        update_build_canvas_and_template(
            build_id=request.build_id,
            canvas=request.canvas,
            cf_template=new_template_dict
        )
        print(f"  ✓ Database updated")
        
        # Log activity
        from database import log_activity
        log_activity(
            build_id=request.build_id,
            user_id=request.owner_id,
            change=f"Updated stack (Change set: {change_set_result['changeSetName']}, Executed: {executed})"
        )
        
        print("\n" + "=" * 80)
        print("✓ UPDATE COMPLETED")
        print("=" * 80)
        
        return {
            "success": True,
            "message": "Stack update initiated" if executed else "Change set created - awaiting execution",
            "buildId": request.build_id,
            "changeSet": {
                "id": change_set_result['changeSetId'],
                "name": change_set_result['changeSetName'],
                "status": change_set_result['status'],
                "hasChanges": change_set_result['hasChanges'],
                "changes": change_set_result['changes']
            },
            "executed": executed,
            "region": request.region
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"\n✗ Update failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Update error: {str(e)}"
        )


@router.post('/deploy/execute-changeset')
def execute_changeset(
    stack_name: str,
    change_set_name: str,
    build_id: int,
    owner_id: int = 1,
    region: str = 'us-east-1'
):
    """
    Execute a previously created change set.
    
    This is used when a change set was created with auto_execute=False,
    the user reviewed the changes, and now wants to apply them.
    
    Args:
        stack_name: CloudFormation stack name
        change_set_name: Name of the change set to execute
        build_id: Build ID for activity logging
        owner_id: User ID (default: 1)
        region: AWS region (default: us-east-1)
        
    Returns:
        Execution result with stack ID
    """
    print("=" * 80)
    print("EXECUTE CHANGE SET REQUEST")
    print("=" * 80)
    print(f"Stack Name: {stack_name}")
    print(f"Change Set: {change_set_name}")
    print(f"Build ID: {build_id}")
    
    try:
        from CFCreators.aws_deployer import CloudFormationDeployer
        from database import log_activity
        
        deployer = CloudFormationDeployer(region=region)
        
        # Execute the change set
        stack_id = deployer.execute_change_set(
            stack_name=stack_name,
            change_set_name=change_set_name
        )
        
        # Log activity
        log_activity(
            build_id=build_id,
            user_id=owner_id,
            change=f"Executed change set: {change_set_name} on stack {stack_name}"
        )
        
        return {
            "success": True,
            "message": "Change set executed - stack update in progress",
            "stackId": stack_id,
            "stackName": stack_name,
            "changeSetName": change_set_name,
            "region": region
        }
        
    except Exception as e:
        print(f"\n✗ Execution failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to execute change set: {str(e)}"
        )


@router.delete('/deploy/changeset')
def delete_changeset(
    stack_name: str,
    change_set_name: str,
    region: str = 'us-east-1'
):
    """
    Delete a change set without executing it.
    
    This is used when a user reviews changes and decides not to proceed.
    
    Args:
        stack_name: CloudFormation stack name
        change_set_name: Name of the change set to delete
        region: AWS region (default: us-east-1)
        
    Returns:
        Deletion confirmation
    """
    print("=" * 80)
    print("DELETE CHANGE SET REQUEST")
    print("=" * 80)
    print(f"Stack Name: {stack_name}")
    print(f"Change Set: {change_set_name}")
    
    try:
        from CFCreators.aws_deployer import CloudFormationDeployer
        
        deployer = CloudFormationDeployer(region=region)
        
        # Delete the change set
        deployer.delete_change_set(
            stack_name=stack_name,
            change_set_name=change_set_name
        )
        
        return {
            "success": True,
            "message": "Change set deleted successfully",
            "stackName": stack_name,
            "changeSetName": change_set_name
        }
        
    except Exception as e:
        print(f"\n✗ Deletion failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete change set: {str(e)}"
        )



@builds.get('/new')
def new_build(id: str):
  
    
    try:
        # Create new build with empty canvas and cf_template
        build_id = save_build(
            owner_id=int(id),
            canvas=None,
            cf_template=None
        )
        
        
        return {"build_id": build_id}
        
    except Exception as e:
        print(f"✗ Failed to create build: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create build: {str(e)}"
        )


@builds.get('/')
def get_builds(id: str):
  
    try:
        builds = get_builds_by_owner(owner_id=int(id))


        
        
        return {"builds": builds}
        
    except Exception as e:
        print(f"✗ Failed to fetch builds: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch builds: {str(e)}"
        )


@router.get('/')
async def get_repos(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    token = authorization.split(" ")[1]
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.github.com/users/{token}/repos")
        repos = response.json()
        # print(repos)
        simplified = [
        {
            "name": repo["name"],
            "html_url": repo["html_url"],
            "owner": repo["owner"]["login"],
            "ref": "main",
        }
        for repo in repos
    ]
        return simplified


@router.post("/builds")
async def cicd(Data: dict):
    print('route reached')
#websocket connections


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

   
# async def emit(build_id, message: str): #function to send message to specific websocket(reusable)
#     websocket = sockets.get(build_id)

#     # await websocket.send_text(message)

#     if websocket:
#         await websocket.send_text(message)
   
#     else:
#         print(f"No active websocket for build_id: {build_id}")

#uncomment the rest of this
# @router.post("/builds")
# async def cicd(Data: dict):
  

#     url = Data.get("repo")

#     # tag = Data.get("tag")

#     # name = Data.get("name")

#     # print("socccer",sockets)


#     # print("build data",Data)

#     # print("tag",tag)




#     # print("url",url)

#     # owner = url.split("/")[1]
#     # repo = url.split("/")[0]

#     # print(owner,repo)


#     # ref = "main"

#     # zip_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{ref}" 

    print(zip_url)


#     # out_file = f"{repo}-{ref}.zip"

#     # headers = {"user":"test"}

#     # response = requests.get(zip_url, headers=headers,allow_redirects=True)  #make the request to download the zip file

#     # S3_BUCKET_NAME = "foundry-codebuild-zip"



#     # S3_KEY = f"{owner}/{out_file}"  # the path for the file in the s3 bucket

#     # print(S3_KEY)


#     # if response.status_code == 200: 
#     #     with open(out_file, "wb") as file:
#     #         file.write(response.content)  #write the content to a file
#     #     print(f"Downloaded {out_file} successfully.")
#     #     path = addBuildSpec(out_file, fastapi_buildspec_template, overWrite=True)
#     #     addAppSpec(out_file,fastapi_appspec_template, overWrite=True)
#     #     addStopScript(out_file, stop_sh_template, overWrite=True)
#     #     addInstallScript(out_file, install_sh_template, overWrite=True)
#     #     addStartScript(out_file, start_sh_template, overWrite=True)
       
#     # else: 
#     #     print(f"Failed to download file: {response.status_code} - {response.text}")

    
    upload_to_s3(out_file, S3_BUCKET_NAME, S3_KEY)
    time.sleep(10)  #wait for a few seconds to ensure the file is available in s3

    status = trigger_codebuild("foundryCICD", S3_BUCKET_NAME, S3_KEY,path,f"{owner}-{repo}")
#     # upload_to_s3(out_file, S3_BUCKET_NAME, S3_KEY)
   

#     # status = await trigger_codebuild("foundryCICD", S3_BUCKET_NAME, S3_KEY,path,f"{owner}-{repo}",emit,tag)

#     # print(status)

#     # if(status['build_status'] == 'SUCCEEDED'):
#     #     await codeDeploy(owner,repo,"foundry-artifacts-bucket",f"founryCICD-{owner}-{repo}",tag,emit)
#     #     ec2_details = boto3.client('ec2', region_name='us-east-1')


#     #     ec2_address = ec2_details.describe_instances(Filters=[{'Name': 'tag:BuildId', 'Values': [tag]}])
        
#     #     print("response",ec2_address['Reservations'][0]['Instances'][0]['PublicIpAddress'])


#     #     try:

#     #         database = os.getenv("DATABASE_URL")

#     #         connect = await asyncpg.connect(database)

#     #         public_ip = ec2_address['Reservations'][0]['Instances'][0]['PublicIpAddress']

  
#     #         endpoint =  f"http://{public_ip}:8000"
               

#     #         update = await connect.execute("UPDATE build SET endpoint = $1 WHERE id = $2",endpoint,int(tag))


#     #         print("update",update)  



            
            
#     #         return {"ec2_address": f"http:{ec2_address['Reservations'][0]['Instances'][0]['PublicIpAddress']}:8000"}    

    
#     #     except Exception as e:
#     #         print("failed to fetch ec2 details",e)


        
        
       
    

    
    

@router.get("/users")
async def get_user_info():
    load_dotenv()

    DATABASE_URL = os.getenv("DATABASE_URL")

    print("DATABASE_URL:", DATABASE_URL)

    try: 
        info = await asyncpg.connect(DATABASE_URL)


        rows = await info.fetch("SELECT * FROM users;")

        user_info = []
        for row in rows:
            user_info.append({"id": row["id"], "email": row["email"]})

    
        # print("users:",user_info)


        await info.close()




        return user_info
    

    except Exception as e: 
        print(f"Failed to connect to database: {e}")
        return


@router.post('/settings')
async def settings(data: dict): 

    print("data received:",data)

    project = data.get("projectName")

    id = data.get("build_id")

    description = data.get("description")

    try: 

        database = await asyncpg.connect(os.getenv("DATABASE_URL"))


        result = await database.execute("UPDATE build SET project_name = $1 WHERE id = $2", project,int(id))

        print("result",result)



    except Exception as e: 

        print("failed to save",e)


@router.post("/invite")
async def send_invites(data: dict): 


    

    
    invites = data.get('invite_id')

    build_id = data.get('build_id')

    owner_id = data.get('owner_id')

    project_name = data.get('project_name')

    description = data.get('description')

    try: 
 
        database = await asyncpg.connect(os.getenv("DATABASE_URL"))


        update_build = await database.execute("UPDATE build SET project_name = $1,description = $2 WHERE id = $3",project_name,description, int(build_id))


        for invite in invites:
            id = random.randint(100000,999999)
            result = await database.execute("INSERT INTO invites (invite__id, build_id, owner_id, project_name, description,id) VALUES ($1, $2, $3, $4, $5,$6)",
                                            int(invite), int(build_id), int(owner_id), project_name, description,id
)


    

    except Exception as e: 
        print("failed to send invites",e)


@builds.get("/invitations")
async def get_invite_info(id: str):

    try: 

        database = await asyncpg.connect(os.getenv("DATABASE_URL"))


        response = await database.fetch("SELECT * FROM invites WHERE invite__id = $1", int(id)) 
        return [dict(row) for row in response] 

        


    
    except Exception as e: 
        print("error",e)
    
    
    # print("hello world")


@builds.post("/invitations/decline")
async def decline_invite(data: dict): 

    id = data.get("id")

    print(id)

    try: 

        database = await asyncpg.connect(os.getenv("DATABASE_URL"))


        response = await database.execute("DELETE FROM invites WHERE id = $1", int(id)) 

        print("response",response)



    except Exception as e: 
        print("error",e)


@builds.post('/invitations/accept')
async def accept_invite(data:dict):

    


    try: 
        database = await asyncpg.connect(os.getenv("DATABASE_URL"))


        update = await database.execute("UPDATE invites SET invite_status = $1 WHERE id = $2", True, int(data.get("id")))

        print("update",update)




    except Exception as e:

        print("error",e)


@router.post("/deployments")
async def deployment(data:dict): 


    print("data",data)

    try:

        database = await asyncpg.connect(os.getenv("DATABASE_URL"))

        update = await database.execute("UPDATE build SET status = $1 WHERE id = $2", True, int(data.get("build_id"))) 


    
    except Exception as e:
        print("error",e)


@router.get("/settings")
async def get_settings(build_id: str):

    try: 

        database = os.getenv("DATABASE_URL")


        connect = await asyncpg.connect(database)

        response = await connect.fetch("SELECT * FROM build WHERE id = $1", int(build_id))

        print("response",response)


        return [dict(row) for row in response]



    
    except Exception as e: 
        print("error",e)


@router.websocket("/deploy/track/{stack_name}")
async def track_deployment(websocket: WebSocket, stack_name: str, region: str = 'us-east-1'):
    """
    WebSocket endpoint for real-time CloudFormation deployment tracking.
    
    Streams live updates as AWS resources are created/updated/deleted.
    
    Args:
        websocket: WebSocket connection
        stack_name: CloudFormation stack name to track
        region: AWS region (default: us-east-1)
        
    WebSocket Message Format:
        {
            "type": "resource_update" | "stack_complete" | "error" | "initial_state",
            "timestamp": "2025-11-13T10:30:45Z",
            "resource": {
                "logicalId": "MyEC2Instance",
                "type": "AWS::EC2::Instance",
                "status": "CREATE_IN_PROGRESS",
                "statusReason": "",
                "physicalId": "i-1234567890abcdef",
                "progress": 66
            },
            "stack": {
                "name": "build-12345678",
                "status": "CREATE_IN_PROGRESS",
                "totalResources": 5,
                "completedResources": 3,
                "inProgressResources": 1,
                "failedResources": 0,
                "progress": 60
            }
        }
    """
    await deployment_ws_manager.connect(websocket, stack_name, region)
    
    try:
        # Keep connection alive and handle any incoming messages
        while True:
            # Wait for messages from client (e.g., ping to keep alive)
            try:
                data = await websocket.receive_text()
                # Echo back to acknowledge (optional)
                # Can handle client commands here if needed
            except WebSocketDisconnect:
                break
            
    except Exception as e:
        print(f"WebSocket error for {stack_name}: {e}")
    finally:
        deployment_ws_manager.disconnect(websocket, stack_name)


@router.post('/deploy/delete')
def delete_stack(request: DeleteRequest):
    """
    Delete a CloudFormation stack and clean up associated resources (including SSH key pairs).
    
    Args:
        request: DeleteRequest containing:
            - stack_name: CloudFormation stack name to delete (REQUIRED)
            - build_id: Optional build ID for database updates
            - owner_id: User ID (default: 1)
            - region: AWS region (default: us-east-1)
            - cleanup_key_pairs: Whether to delete SSH key pairs (default: True)
        
    Returns:
        Deletion result with number of key pairs deleted
    """
    print("=" * 80)
    print("DELETE STACK REQUEST RECEIVED")
    print("=" * 80)
    print(f"Stack Name: {request.stack_name}")
    print(f"Build ID: {request.build_id}")
    print(f"Region: {request.region}")
    print(f"Cleanup Key Pairs: {request.cleanup_key_pairs}")
    
    try:
        # Delete stack and key pairs
        result = CFCreator.deleteStack(
            stack_name=request.stack_name,
            region=request.region,
            cleanup_key_pairs=request.cleanup_key_pairs
        )
        
        if result['success']:
            print(f"\n✓ Stack deletion initiated!")
            
            # Update database activity log if build_id provided
            if request.build_id:
                try:
                    print(f"\nLogging deletion activity...")
                    log_activity(
                        build_id=request.build_id,
                        user_id=request.owner_id,
                        change=f"Deleted stack: {request.stack_name} in {request.region}. Key pairs deleted: {result.get('keyPairsDeleted', 0)}"
                    )
                    print("✓ Activity logged")
                except Exception as log_error:
                    print(f"⚠ Warning: Failed to log activity: {str(log_error)}")
            
            return {
                "success": True,
                "message": result['message'],
                "stackName": result['stackName'],
                "keyPairsDeleted": result.get('keyPairsDeleted', 0),
                "region": request.region
            }
        else:
            print(f"\n✗ Deletion failed: {result.get('message')}")
            raise HTTPException(
                status_code=500,
                detail=result.get('message', 'Stack deletion failed')
            )
            
    except Exception as e:
        print(f"\n✗ Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Deletion error: {str(e)}"
        )



@router.get('/endpoint/')
async def endpoint(build_id: str):





    print("id",type(build_id))

    try:

        database = os.getenv("DATABASE_URL")

        connect = await asyncpg.connect(database)

        response = await connect.fetch("SELECT endpoint FROM build WHERE id = $1", int(build_id))

        print("response",response)


        return [dict(row) for row in response]



    
    except Exception as e: 
        print("error",e)    

@router.get('/costs')
def get_costs(build_id: str):

    

#     print("build_id",build_id)
    
    s3_price = get_price(build_id)


    print("s3 innnn",s3_price)

    
#left off here 
    ec2_cost = ec2_price(build_id)

    print("ec2 cost",ec2_cost)

    # for service in ec2_cost:
    #     if service['t3.micro'] == 0

    
    
    # print("ec2 innnn",ec2_cost)

    # ec2_vals = []
    # # for instance_type in ec2_cost:
    # #     if ec2_cost[instance_type] != 0:
    # #         ec2_vals.append({instance_type: ec2_cost[instance_type]})
            

    # print("ec2 vals",ec2_vals)

    return {'s3': s3_price,'ec2': ec2_cost}

#     ec2_services =ec2_price(build_id)

#     # ec2_cost = 0
#     # for service in ec2_services:
#     #     ec2_cost += service['price']
        




#     dynamo_price = dynamoCost(build_id)

#     pricing = { 
#     's3': s3_price,
#     'ec2': ec2_services,
#     'dynamo': dynamo_price,

# }
#     print("pricing",pricing)




#     return {"data":pricing}  


@router.get('/logs')
def logs(build_id:str):

    logs = ec2_log(build_id)


    if logs is None:
        raise HTTPException(
            status_code=404,
            detail=f"No logs found for build_id {build_id}"
        )
        return
  
    
   

    return {"logs":logs}


    



   