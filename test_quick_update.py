"""
Quick test: Deploy a simple stack, then test update functionality.
"""

import json
import time
from CFCreators.CFCreator import deployToAWS, createGeneration
from CFCreators.aws_deployer import CloudFormationDeployer

# Simple test canvas - EC2 only
initial_canvas = {
    "nodes": [
        {
            "id": "test-node-123",
            "type": "EC2",
            "data": {
                "name": "TestServer",
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

# Updated canvas - change instance type
updated_canvas = {
    "nodes": [
        {
            "id": "test-node-123",  # SAME ID = stable naming
            "type": "EC2",
            "data": {
                "name": "TestServer",
                "imageId": "Amazon Linux",
                "instanceType": "t2.small",  # CHANGED: micro -> small
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

print("=" * 80)
print("QUICK UPDATE TEST")
print("=" * 80)
print("\nThis test will:")
print("1. Deploy a simple EC2 stack (t2.micro)")
print("2. Create a change set to update it (t2.small)")
print("3. Show the change preview")
print()

proceed = input("Continue? (y/n): ").strip().lower()
if proceed != 'y':
    print("Test cancelled")
    exit(0)

try:
    # Step 1: Deploy initial stack
    print("\n" + "=" * 80)
    print("[STEP 1] Deploying initial stack...")
    print("=" * 80)
    
    result = deployToAWS(
        canvas_data=initial_canvas,
        stack_name=None,  # Auto-generate
        region='us-east-1'
    )
    
    if not result['success']:
        print(f"❌ Deployment failed: {result.get('message')}")
        exit(1)
    
    stack_name = result['stackName']
    stack_id = result['stackId']
    
    print(f"\n✅ Stack deployed!")
    print(f"   Stack Name: {stack_name}")
    print(f"   Stack ID: {stack_id}")
    print(f"   Status: {result['status']}")
    
    # Wait a bit for stack to initialize
    print("\n⏳ Waiting 10 seconds for stack to initialize...")
    time.sleep(60)
    
    # Step 2: Create change set
    print("\n" + "=" * 80)
    print("[STEP 2] Creating change set...")
    print("=" * 80)
    print("Change: EC2 instance type t2.micro → t2.small")
    
    deployer = CloudFormationDeployer(region='us-east-1')
    
    # Generate new template
    new_template = createGeneration(updated_canvas)
    template_json = new_template.to_json()
    
    # Get VPC resources
    vpc_resources = deployer.get_default_vpc_resources()
    
    # Create change set
    change_set_result = deployer.update_stack(
        stack_name=stack_name,
        template_body=template_json,
        parameters=vpc_resources
    )
    
    print("\n" + "=" * 80)
    print("📊 CHANGE SET PREVIEW")
    print("=" * 80)
    print(f"Change Set: {change_set_result['changeSetName']}")
    print(f"Status: {change_set_result['status']}")
    print(f"Has Changes: {change_set_result['hasChanges']}")
    print(f"Change Count: {len(change_set_result['changes'])}")
    
    if change_set_result['hasChanges']:
        print("\n📝 Changes Detected:")
        for change in change_set_result['changes']:
            print(f"  • {change['action']}: {change['logicalId']} ({change['resourceType']})")
            if change['replacement'] not in ['N/A', 'False']:
                print(f"    ⚠️  Replacement: {change['replacement']}")
    
    # Step 3: Execute change set
    print("\n" + "=" * 80)
    print("[STEP 3] Change Set Actions")
    print("=" * 80)
    
    if change_set_result['hasChanges']:
        print("What would you like to do?")
        print("1. Execute change set (update the stack)")
        print("2. Delete change set (cancel update)")
        print("3. Keep stack and change set (for manual cleanup later)")
        
        choice = input("\nChoice (1/2/3): ").strip()
        
        if choice == "1":
            print("\n🚀 Executing change set...")
            stack_id = deployer.execute_change_set(
                stack_name=stack_name,
                change_set_name=change_set_result['changeSetName']
            )
            print(f"✅ Change set executed! Stack updating...")
            print(f"   Stack ID: {stack_id}")
            
        elif choice == "2":
            print("\n🗑️  Deleting change set...")
            deployer.delete_change_set(
                stack_name=stack_name,
                change_set_name=change_set_result['changeSetName']
            )
            print("✅ Change set deleted")
    else:
        print("ℹ️  No changes detected - stack already up to date")
    
    print("\n" + "=" * 80)
    print("✓ TEST COMPLETED")
    print("=" * 80)
    print(f"\n📝 Stack Name: {stack_name}")
    print(f"💡 Don't forget to delete the stack when done:")
    print(f"   aws cloudformation delete-stack --stack-name {stack_name}")
    print("=" * 80)
    
except Exception as e:
    print(f"\n❌ Test failed: {str(e)}")
    import traceback
    traceback.print_exc()
