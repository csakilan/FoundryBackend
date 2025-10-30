"""
Test script for CloudFormation Update functionality.

This script tests:
1. Creating a change set for an existing stack
2. Previewing changes
3. Executing or deleting the change set
"""

import json
from CFCreators.aws_deployer import CloudFormationDeployer

# Test canvas data - simulating a simple EC2 update
# Original: t2.micro instance
# Updated: t2.small instance (should show as a Modify action)
original_canvas = {
    "nodes": [
        {
            "id": "node-ec2-001",
            "type": "EC2",
            "data": {
                "name": "WebServer",
                "imageId": "Amazon Linux",
                "instanceType": "t2.micro",
                "storage": {
                    "volumeSize": 8,
                    "volumeType": "gp3",
                    "deleteOnTermination": True
                }
            }
        }
    ],
    "edges": []
}

updated_canvas = {
    "nodes": [
        {
            "id": "node-ec2-001",  # Same ID = stable naming
            "type": "EC2",
            "data": {
                "name": "WebServer",
                "imageId": "Amazon Linux",
                "instanceType": "t2.small",  # CHANGED: t2.micro -> t2.small
                "storage": {
                    "volumeSize": 16,  # CHANGED: 8 -> 16 GB
                    "volumeType": "gp3",
                    "deleteOnTermination": True
                }
            }
        }
    ],
    "edges": []
}

def test_update_flow():
    """Test the complete update flow with a real AWS stack."""
    
    print("=" * 80)
    print("CLOUDFORMATION UPDATE FLOW TEST")
    print("=" * 80)
    
    # Get stack name from user
    stack_name = input("\n📋 Enter the CloudFormation stack name to update: ").strip()
    
    if not stack_name:
        print("❌ Stack name is required!")
        return
    
    region = input("🌍 Enter AWS region (default: us-east-1): ").strip() or 'us-east-1'
    
    print(f"\n🎯 Testing update for stack: {stack_name}")
    print(f"📍 Region: {region}")
    
    try:
        # Initialize deployer
        print("\n[1/5] Initializing AWS deployer...")
        deployer = CloudFormationDeployer(region=region)
        print("  ✓ Deployer initialized")
        
        # Check if stack exists
        print("\n[2/5] Checking if stack exists...")
        try:
            stack_info = deployer.get_stack_status(stack_name)
            print(f"  ✓ Stack found: {stack_name}")
            print(f"    - Current Status: {stack_info['status']}")
        except Exception as e:
            print(f"  ❌ Stack not found: {str(e)}")
            print("\n💡 Tip: Deploy a stack first using POST /canvas/deploy")
            return
        
        # Generate updated template
        print("\n[3/5] Generating updated CloudFormation template...")
        from CFCreators.CFCreator import createGeneration
        
        print("  → Using test canvas with EC2 instance type change (t2.micro → t2.small)")
        updated_template = createGeneration(updated_canvas)
        template_json = updated_template.to_json()
        
        print("  ✓ Template generated")
        
        # Get VPC resources for parameters
        print("\n[4/5] Getting VPC resources...")
        vpc_resources = deployer.get_default_vpc_resources()
        print(f"  ✓ VPC resources retrieved")
        
        # Create change set
        print("\n[5/5] Creating change set...")
        change_set_result = deployer.update_stack(
            stack_name=stack_name,
            template_body=template_json,
            parameters=vpc_resources
        )
        
        print("\n" + "=" * 80)
        print("📊 CHANGE SET SUMMARY")
        print("=" * 80)
        print(f"Change Set ID: {change_set_result['changeSetId']}")
        print(f"Change Set Name: {change_set_result['changeSetName']}")
        print(f"Status: {change_set_result['status']}")
        print(f"Has Changes: {change_set_result['hasChanges']}")
        print(f"Total Changes: {len(change_set_result['changes'])}")
        
        if change_set_result['hasChanges']:
            print("\n📝 Changes:")
            for i, change in enumerate(change_set_result['changes'], 1):
                action = change['action']
                logical_id = change['logicalId']
                resource_type = change['resourceType']
                replacement = change['replacement']
                
                print(f"\n  {i}. {action}: {logical_id}")
                print(f"     Type: {resource_type}")
                if replacement not in ['N/A', 'False']:
                    print(f"     ⚠️  Replacement: {replacement}")
            
            # Ask user what to do
            print("\n" + "=" * 80)
            print("🤔 What would you like to do?")
            print("=" * 80)
            print("1. Execute change set (apply changes)")
            print("2. Delete change set (cancel)")
            print("3. Leave change set (do nothing)")
            
            choice = input("\nEnter choice (1/2/3): ").strip()
            
            if choice == "1":
                print("\n🚀 Executing change set...")
                stack_id = deployer.execute_change_set(
                    stack_name=stack_name,
                    change_set_name=change_set_result['changeSetName']
                )
                print(f"\n✅ Change set executed successfully!")
                print(f"   Stack ID: {stack_id}")
                print(f"   Status: Stack update in progress...")
                print(f"\n💡 Check stack status with: GET /canvas/deploy/status/{stack_name}")
                
            elif choice == "2":
                print("\n🗑️  Deleting change set...")
                deployer.delete_change_set(
                    stack_name=stack_name,
                    change_set_name=change_set_result['changeSetName']
                )
                print(f"\n✅ Change set deleted - no changes applied")
                
            else:
                print(f"\n📋 Change set '{change_set_result['changeSetName']}' left for manual review")
                print(f"   You can execute it later from AWS Console or API")
        else:
            print("\n✅ Stack is already up to date - no changes needed!")
        
        print("\n" + "=" * 80)
        print("✓ TEST COMPLETED SUCCESSFULLY")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


def test_no_changes():
    """Test update with no changes (should detect no changes needed)."""
    
    print("\n" + "=" * 80)
    print("TEST: Update with No Changes")
    print("=" * 80)
    
    stack_name = input("\n📋 Enter stack name: ").strip()
    if not stack_name:
        print("❌ Stack name required")
        return
    
    region = input("🌍 Region (default: us-east-1): ").strip() or 'us-east-1'
    
    try:
        print("\n[1/3] Initializing...")
        deployer = CloudFormationDeployer(region=region)
        
        print("\n[2/3] Getting current stack template...")
        # Get the current template from the stack
        import boto3
        cf_client = boto3.client('cloudformation', region_name=region)
        response = cf_client.get_template(
            StackName=stack_name,
            TemplateStage='Original'
        )
        current_template = response['TemplateBody']
        
        print("\n[3/3] Creating change set with same template...")
        vpc_resources = deployer.get_default_vpc_resources()
        
        # Convert dict to JSON string if needed
        if isinstance(current_template, dict):
            current_template = json.dumps(current_template)
        
        result = deployer.update_stack(
            stack_name=stack_name,
            template_body=current_template,
            parameters=vpc_resources
        )
        
        print("\n" + "=" * 80)
        print("RESULT:")
        print("=" * 80)
        print(f"Status: {result['status']}")
        print(f"Has Changes: {result['hasChanges']}")
        print(f"Message: {result.get('message')}")
        
        if result['hasChanges']:
            print("\n⚠️  WARNING: Expected no changes, but got some!")
        else:
            print("\n✅ SUCCESS: Correctly detected no changes needed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n🧪 CloudFormation Update Test Suite")
    print("=" * 80)
    print("\nAvailable Tests:")
    print("1. Test complete update flow (create change set → execute/cancel)")
    print("2. Test no-changes detection (same template)")
    print()
    
    choice = input("Select test (1/2): ").strip()
    
    if choice == "1":
        test_update_flow()
    elif choice == "2":
        test_no_changes()
    else:
        print("Invalid choice!")
