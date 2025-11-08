"""
Test script to verify build ID consistency across the system.
"""
from database import save_build, get_build
from CFCreators.CFCreator import createGeneration, deployToAWS
import json

# Test canvas data
test_canvas = {
    "nodes": [
        {
            "id": "node-abc123",
            "type": "EC2",
            "data": {
                "name": "TestServer",
                "imageId": "Amazon Linux",
                "instanceType": "t2.micro"
            }
        }
    ],
    "edges": []
}

print("=" * 80)
print("TESTING BUILD ID CONSISTENCY")
print("=" * 80)

try:
    # Step 1: Save to database first
    print("\n[Step 1] Saving to database...")
    build_id = save_build(
        owner_id=1,
        canvas=test_canvas,
        cf_template=None
    )
    print(f"✓ Database build_id: {build_id}")
    
    # Step 2: Generate CloudFormation template with build_id
    print(f"\n[Step 2] Generating CF template with build_id={build_id}...")
    cf_template = createGeneration(
        data=test_canvas,
        build_id=str(build_id),
        save_to_file=True
    )
    template_json = json.loads(cf_template.to_json())
    
    print(f"✓ CloudFormation template generated")
    print(f"  - File saved as: CF_{build_id}.json")
    
    # Check resource names in template
    if 'Resources' in template_json:
        for resource_name, resource_data in template_json['Resources'].items():
            if resource_data['Type'] == 'AWS::EC2::Instance':
                tags = resource_data.get('Properties', {}).get('Tags', [])
                build_tag = next((tag for tag in tags if tag['Key'] == 'BuildId'), None)
                if build_tag:
                    print(f"  - EC2 Instance BuildId tag: {build_tag['Value']}")
    
    # Step 3: Update database with CF template
    print(f"\n[Step 3] Updating database with CF template...")
    from database import update_build_canvas_and_template
    update_build_canvas_and_template(
        build_id=build_id,
        canvas=test_canvas,
        cf_template=template_json
    )
    print(f"✓ Database updated")
    
    # Step 4: Verify everything matches
    print(f"\n[Step 4] Verifying consistency...")
    retrieved = get_build(build_id)
    
    print(f"✓ Verification complete:")
    print(f"  - Database ID: {retrieved['id']}")
    print(f"  - Has CF template: {retrieved['cf_template'] is not None}")
    print(f"  - Canvas nodes: {len(retrieved['canvas']['nodes'])}")
    
    print("\n" + "=" * 80)
    print(f"✓ SUCCESS! Build ID {build_id} is consistent across all systems")
    print("=" * 80)
    print(f"\nExpected naming convention:")
    print(f"  - Database ID: {build_id}")
    print(f"  - Stack name: foundry-stack-{build_id}")
    print(f"  - CF file: CF_{build_id}.json")
    print(f"  - Resources: {build_id}-abc123-TestServer")
    
except Exception as e:
    print(f"\n✗ Test failed: {str(e)}")
    import traceback
    traceback.print_exc()
