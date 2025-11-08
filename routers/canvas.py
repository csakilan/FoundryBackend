from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from CFCreators import CFCreator
import json
from pathlib import Path
import httpx
from database import save_build, log_activity, get_build, update_build_canvas_and_template, get_builds_by_owner


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


# ============================================================================
# BUILD MANAGEMENT ENDPOINTS
# ============================================================================

@builds.get('/new')
def new_build(id: str):
    """
    Create a new build record in the database.
    Returns the auto-generated build_id that frontend will use for deployment.
    
    Args:
        id: User/owner ID
        
    Returns:
        {"build_id": <integer>}
    """
    print("=" * 60)
    print(f"[NEW BUILD] Creating new build for user: {id}")
    print("=" * 60)
    
    try:
        # Create new build with empty canvas and cf_template
        build_id = save_build(
            owner_id=int(id),
            canvas=None,
            cf_template=None
        )
        
        print(f"✓ Build created with ID: {build_id}")
        print(f"  - Owner: {id}")
        print(f"  - Canvas: Empty (will be filled on deploy)")
        print(f"  - CF Template: Empty (will be filled on deploy)")
        
        return {"build_id": build_id}
        
    except Exception as e:
        print(f"✗ Failed to create build: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create build: {str(e)}"
        )


@builds.get('/')
def get_builds(id: str):
    """
    Get all builds for a specific owner/user.
    
    Args:
        id: User/owner ID
        
    Returns:
        List of builds with their metadata
    """
    print("=" * 60)
    print(f"[GET BUILDS] Fetching builds for user: {id}")
    print("=" * 60)

    try:
        builds = get_builds_by_owner(owner_id=int(id))
        
        print(f"✓ Found {len(builds)} builds for user {id}")
        
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















