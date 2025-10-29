"""
Test script to verify database integration works
"""
import json
from database import save_build, get_build, log_activity

# Test data
test_canvas = {
    "nodes": [
        {
            "id": "node-abc123",
            "type": "EC2",
            "data": {
                "name": "TestServer",
                "imageId": "ami-12345",
                "instanceType": "t2.micro"
            }
        }
    ],
    "edges": []
}

test_template = {
    "AWSTemplateFormatVersion": "2010-09-09",
    "Description": "Test template",
    "Resources": {
        "EC2Instance": {
            "Type": "AWS::EC2::Instance",
            "Properties": {
                "ImageId": "ami-12345",
                "InstanceType": "t2.micro"
            }
        }
    }
}

print("Testing database integration...")
print("=" * 60)

try:
    # Test 1: Save build
    print("\n[1/3] Testing save_build()...")
    build_id = save_build(
        owner_id=1,
        canvas=test_canvas,
        cf_template=test_template
    )
    print(f"✓ Build saved successfully with ID: {build_id}")
    
    # Test 2: Retrieve build
    print("\n[2/3] Testing get_build()...")
    retrieved = get_build(build_id)
    print(f"✓ Build retrieved successfully")
    print(f"  - Build ID: {retrieved['id']}")
    print(f"  - Owner ID: {retrieved['owner_id']}")
    print(f"  - Canvas nodes: {len(retrieved['canvas']['nodes'])}")
    print(f"  - Has CF template: {retrieved['cf_template'] is not None}")
    print(f"  - Created at: {retrieved['created_at']}")
    
    # Test 3: Log activity
    print("\n[3/3] Testing log_activity()...")
    log_activity(
        build_id=build_id,
        action="test_activity",
        details={"test": "success"}
    )
    print(f"✓ Activity logged successfully")
    
    print("\n" + "=" * 60)
    print("✓ All database integration tests passed!")
    print("=" * 60)
    
except Exception as e:
    print(f"\n✗ Test failed: {str(e)}")
    import traceback
    traceback.print_exc()
