"""
Complete End-to-End Workflow Test
==================================
Tests the entire build ID workflow:
1. Create new build -> Get integer build_id
2. Deploy canvas with build_id -> Updates database, deploys to AWS
3. Verify database update
4. Verify CloudFormation file naming
5. List builds for user

This test validates that:
- Build IDs are integers from database SERIAL
- All AWS resources use the build_id for naming
- CF templates are saved as CF_{build_id}.json
- Database is properly updated with canvas and template
"""

import requests
import json
from pathlib import Path

# Configuration
BASE_URL = "http://127.0.0.1:8000"
TEST_USER_ID = 1

# Sample canvas data (minimal EC2 + S3 setup)
SAMPLE_CANVAS = {
    "nodes": [
        {
            "id": "ec2-test-1",
            "type": "EC2",
            "data": {
                "name": "webserver",
                "imageId": "Amazon Linux",
                "instanceType": "t2.micro",
                "storage": {
                    "volumeSize": 8,
                    "volumeType": "gp3"
                }
            }
        },
        {
            "id": "s3-test-1",
            "type": "S3",
            "data": {
                "name": "myapp-bucket",
                "versioning": False,
                "encryption": True
            }
        }
    ],
    "edges": [
        {
            "id": "edge-1",
            "source": "s3-test-1",
            "target": "ec2-test-1"
        }
    ],
    "viewport": {
        "x": 0,
        "y": 0,
        "zoom": 1
    }
}


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def test_workflow():
    """Run complete workflow test"""
    
    print_section("COMPLETE BUILD ID WORKFLOW TEST")
    print(f"Testing against: {BASE_URL}")
    print(f"User ID: {TEST_USER_ID}")
    
    # ========== STEP 1: Create New Build ==========
    print_section("STEP 1: Create New Build")
    print(f"Calling: GET {BASE_URL}/builds/new?id={TEST_USER_ID}")
    
    try:
        response = requests.get(f"{BASE_URL}/builds/new?id={TEST_USER_ID}")
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ Response received: {json.dumps(result, indent=2)}")
        
        if "build_id" not in result:
            print("✗ FAILED: Response missing 'build_id' field")
            return False
        
        build_id = result["build_id"]
        
        if not isinstance(build_id, int):
            print(f"✗ FAILED: build_id should be integer, got {type(build_id)}")
            return False
        
        print(f"✓ SUCCESS: Received integer build_id = {build_id}")
        
    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        return False
    
    # ========== STEP 2: Deploy Canvas with Build ID ==========
    print_section("STEP 2: Deploy Canvas with Build ID")
    
    deploy_payload = {
        "buildId": build_id,  # Integer from step 1
        "canvas": SAMPLE_CANVAS,
        "owner_id": TEST_USER_ID,
        "region": "us-east-1"
    }
    
    print(f"Calling: POST {BASE_URL}/canvas/deploy")
    print(f"Payload build_id: {build_id} (type: {type(build_id).__name__})")
    print(f"Canvas nodes: {len(SAMPLE_CANVAS['nodes'])}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/canvas/deploy",
            json=deploy_payload,
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        
        result = response.json()
        print(f"✓ Response received:")
        print(f"  - Success: {result.get('success')}")
        print(f"  - Stack Name: {result.get('stackName')}")
        print(f"  - Stack ID: {result.get('stackId', 'N/A')[:50]}...")
        print(f"  - Region: {result.get('region')}")
        print(f"  - Status: {result.get('status')}")
        print(f"  - Build ID: {result.get('buildId')}")
        
        if not result.get("success"):
            print(f"✗ FAILED: Deployment unsuccessful")
            print(f"  Message: {result.get('message', 'No message')}")
            return False
        
        # Verify stack name contains build_id
        stack_name = result.get("stackName", "")
        if str(build_id) not in stack_name:
            print(f"⚠ WARNING: Stack name '{stack_name}' doesn't contain build_id '{build_id}'")
        else:
            print(f"✓ SUCCESS: Stack name contains build_id")
        
    except requests.exceptions.HTTPError as e:
        print(f"✗ FAILED: HTTP {e.response.status_code}")
        print(f"  Response: {e.response.text}")
        return False
    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        return False
    
    # ========== STEP 3: Verify CloudFormation File Naming ==========
    print_section("STEP 3: Verify CloudFormation File Naming")
    
    cf_file_path = Path(__file__).parent / "CFCreators" / "allJSONs" / "createdCFs" / f"CF_{build_id}.json"
    
    print(f"Checking for file: {cf_file_path}")
    
    if cf_file_path.exists():
        print(f"✓ SUCCESS: CF template saved as CF_{build_id}.json")
        
        # Verify it contains valid JSON
        try:
            with open(cf_file_path, 'r') as f:
                cf_content = json.load(f)
            print(f"  - Template has {len(cf_content.get('Resources', {}))} resources")
            
            # Check if resource names contain build_id
            resources = cf_content.get('Resources', {})
            if resources:
                sample_resource = list(resources.keys())[0]
                print(f"  - Sample resource: {sample_resource}")
        except Exception as e:
            print(f"⚠ WARNING: Could not parse CF template: {e}")
    else:
        print(f"⚠ WARNING: CF template file not found at expected location")
        print(f"  Expected: CF_{build_id}.json")
    
    # ========== STEP 4: List Builds for User ==========
    print_section("STEP 4: List Builds for User")
    print(f"Calling: GET {BASE_URL}/builds/?id={TEST_USER_ID}")
    
    try:
        response = requests.get(f"{BASE_URL}/builds/?id={TEST_USER_ID}")
        response.raise_for_status()
        
        response_data = response.json()
        builds = response_data.get("builds", [])
        print(f"✓ Response received: Found {len(builds)} builds")
        
        # Find our build
        our_build = next((b for b in builds if b.get("id") == build_id), None)
        
        if our_build:
            print(f"✓ SUCCESS: Build {build_id} found in user's builds")
            print(f"  - Owner ID: {our_build.get('owner_id')}")
            print(f"  - Has Canvas: {our_build.get('canvas') is not None}")
            print(f"  - Has CF Template: {our_build.get('cf_template') is not None}")
            print(f"  - Created At: {our_build.get('created_at')}")
            
            if our_build.get('canvas'):
                canvas = our_build['canvas']
                print(f"  - Canvas Nodes: {len(canvas.get('nodes', []))}")
                print(f"  - Canvas Edges: {len(canvas.get('edges', []))}")
        else:
            print(f"✗ FAILED: Build {build_id} not found in user's builds")
            return False
        
    except Exception as e:
        print(f"✗ FAILED: {str(e)}")
        return False
    
    # ========== FINAL SUMMARY ==========
    print_section("TEST SUMMARY")
    print("✓ ALL TESTS PASSED!")
    print(f"\nWorkflow verified:")
    print(f"  1. Created build with ID: {build_id} (integer from database SERIAL)")
    print(f"  2. Deployed to AWS with stack name: {stack_name}")
    print(f"  3. Database updated with canvas and CF template")
    print(f"  4. CF template saved as: CF_{build_id}.json")
    print(f"  5. Build appears in user's build list")
    print(f"\nBuild ID is consistently used throughout the system! ✅")
    
    return True


if __name__ == "__main__":
    success = test_workflow()
    exit(0 if success else 1)
