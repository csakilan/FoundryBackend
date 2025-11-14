from . import template_composer
from .aws_deployer import CloudFormationDeployer, AWSDeploymentError
from .key_pair_manager import create_key_pairs_for_deployment, cleanup_key_pairs_for_stack
from datetime import datetime
from pathlib import Path
import json


def createGeneration(data: dict, save_to_file: bool = True, build_id: str = None, key_pairs: dict = None):
    """
    Takes frontend ReactFlow JSON and generates a CloudFormation template.
    
    Args:
        data: Frontend ReactFlow JSON containing nodes and edges
        save_to_file: Whether to save the template to createdCFs folder (default: True)
        build_id: Database build ID for file naming (used instead of timestamp)
        key_pairs: Optional dict of key pair information for EC2 instances
        
    Returns:
        CloudFormation Template object
    """
    CFTemplate = template_composer.make_stack_template(data, build_id=build_id, key_pairs=key_pairs)
    
    # Print the CloudFormation template in JSON format
    print("CLOUDFORMATION TEMPLATE (JSON):")
    print("=" * 80)
    print(CFTemplate.to_json())
    print("=" * 80)
    
    # Save to allJSONs/createdCFs folder
    if save_to_file:
        if build_id:
            filename = f"CF_{build_id}.json"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"CF_{timestamp}.json"
        
        output_path = Path(__file__).parent / "allJSONs" / "createdCFs" / filename
        
        # Ensure createdCFs directory exists
        output_path.parent.mkdir(exist_ok=True)
        
        # Convert to JSON and save with pretty formatting
        cf_json = CFTemplate.to_json()
        cf_dict = json.loads(cf_json)
        
        with open(output_path, 'w') as f:
            json.dump(cf_dict, f, indent=2)
        
        print(f"\n✓ CloudFormation template saved to: {output_path.relative_to(Path(__file__).parent.parent)}")
    
    return CFTemplate





def deployToAWS(canvas_data: dict, stack_name: str = None, region: str = 'us-east-1', build_id: str = None):
    """
    Complete deployment pipeline: Generate CloudFormation template and deploy to AWS.
    
    Args:
        canvas_data: Frontend ReactFlow JSON containing nodes and edges
        stack_name: Name for the CloudFormation stack (auto-generated if not provided)
        region: AWS region to deploy to (default: us-east-1)
        build_id: Database build ID for resource naming (used instead of timestamp)
        
    Returns:
        Dictionary with deployment details:
        {
            'success': bool,
            'stackId': str,
            'stackName': str,
            'region': str,
            'status': str,
            'outputs': list,
            'message': str
        }
    """
    
    print("=" * 80)
    print("STARTING AWS DEPLOYMENT PIPELINE")
    print("=" * 80)
    
    try:
        # Step 1: Create SSH key pairs for EC2 instances
        print("\n[1/5] Creating SSH key pairs for EC2 instances...")
        key_pairs = create_key_pairs_for_deployment(canvas_data, build_id or "default", region)
        
        if key_pairs:
            print(f"✓ Created {len(key_pairs)} key pair(s):")
            for instance_name, key_info in key_pairs.items():
                print(f"  - {instance_name}: {key_info['keyName']}")
        else:
            print("✓ No EC2 instances found, skipping key pair creation")
        
        # Step 2: Generate CloudFormation template
        print("\n[2/5] Generating CloudFormation template...")
        cf_template = createGeneration(canvas_data, build_id=build_id, key_pairs=key_pairs)
        template_json = cf_template.to_json()
        
        template_dict = json.loads(template_json)
        print(f"✓ Template generated")
        print(f"  - Resources: {list(template_dict.get('Resources', {}).keys())}")
        
        # Step 3: Initialize AWS deployer
        print(f"\n[3/5] Initializing AWS deployer (region: {region})...")
        deployer = CloudFormationDeployer(region=region)
        print("✓ AWS deployer initialized")
        
        # Step 4: Auto-discover VPC resources
        print("\n[4/5] Auto-discovering VPC resources...")
        vpc_resources = deployer.get_default_vpc_resources()
        print("✓ VPC resources discovered:")
        print(f"  - VPC: {vpc_resources['VpcId']}")
        print(f"  - Subnet: {vpc_resources['SubnetId']}")
        print(f"  - Security Group: {vpc_resources['SecurityGroupId']}")
        
        # Check if template has RDS and setup DB Subnet Group if needed
        has_rds = any(node.get("type") == "RDS" for node in canvas_data.get("nodes", []))
        if has_rds:
            print("\n  → RDS detected, setting up DB Subnet Group...")
            db_subnet_group = deployer.get_or_create_db_subnet_group(vpc_resources['VpcId'])
            vpc_resources['DBSubnetGroupName'] = db_subnet_group
        
        # Step 5: Deploy to AWS
        if not stack_name:
            if build_id:
                stack_name = f"foundry-stack-{build_id}"
            else:
                timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                stack_name = f"foundry-stack-{timestamp}"
        
        print(f"\n[5/5] Deploying stack '{stack_name}' to AWS...")
        stack_id = deployer.deploy_stack(
            template_body=template_json,
            stack_name=stack_name,
            parameters=vpc_resources  # Pass all parameters including DBSubnetGroupName if RDS
        )
        
        # Get initial status
        status_info = deployer.get_stack_status(stack_name)
        
        
        print("\n" + "=" * 80)
        print("✓ DEPLOYMENT SUCCESSFUL!")
        print("=" * 80)
        print(f"Stack ID: {stack_id}")
        print(f"Stack Name: {stack_name}")
        print(f"Status: {status_info['status']}")
        
        if key_pairs:
            print(f"\nSSH Key Pairs Created: {len(key_pairs)}")
            for instance_name in key_pairs:
                print(f"  - {instance_name}")
        
        return {
            'success': True,
            'stackId': stack_id,
            'stackName': stack_name,
            'region': region,
            'status': status_info['status'],
            'outputs': status_info.get('outputs', []),
            'keyPairs': key_pairs,  # Include key pair information
            'message': 'Deployment initiated successfully'
        }
        
    except AWSDeploymentError as e:
        error_msg = f"AWS Deployment Error: {str(e)}"
        print(f"\n✗ {error_msg}")
        return {
            'success': False,
            'message': error_msg,
            'error': str(e)
        }
    
    except Exception as e:
        error_msg = f"Unexpected Error: {str(e)}"
        print(f"\n✗ {error_msg}")
        return {
            'success': False,
            'message': error_msg,
            'error': str(e)
        }







def getStackStatus(stack_name: str, region: str = 'us-east-1'):
    """
    Get the current status of a deployed CloudFormation stack.
    
    Args:
        stack_name: Name of the CloudFormation stack
        region: AWS region (default: us-east-1)
        
    Returns:
        Dictionary with stack status and outputs:
        {
            'success': bool,
            'stackName': str,
            'region': str,
            'status': str,
            'outputs': list
        }
    """
    try:
        deployer = CloudFormationDeployer(region=region)
        status_info = deployer.get_stack_status(stack_name)
        
        return {
            'success': True,
            'stackName': stack_name,
            'region': region,
            'status': status_info['status'],
            'outputs': status_info.get('outputs', [])
        }
        
    except AWSDeploymentError as e:
        return {
            'success': False,
            'message': str(e),
            'error': str(e)
        }
    except Exception as e:
        return {
            'success': False,
            'message': str(e),
            'error': str(e)
        }

