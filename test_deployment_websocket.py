"""
Test script for deployment tracking WebSocket

Run this after starting the FastAPI server to test the WebSocket endpoint.
"""

import asyncio
import websockets
import json


async def test_deployment_tracking():
    """
    Test the deployment tracking WebSocket.
    Replace 'build-12345678' with an actual stack name from your AWS account.
    """
    stack_name = "build-12345678"  # Replace with actual stack name
    uri = f"ws://localhost:8000/canvas/deploy/track/{stack_name}"
    
    print(f"Connecting to: {uri}")
    print("=" * 80)
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✓ Connected to WebSocket")
            print("Listening for deployment events...\n")
            
            # Receive messages
            while True:
                try:
                    message = await websocket.recv()
                    event = json.loads(message)
                    
                    # Pretty print the event
                    event_type = event.get('type')
                    
                    if event_type == 'resource_update':
                        resource = event['resource']
                        print(f"📦 {resource['type']}")
                        print(f"   ID: {resource['logicalId']}")
                        print(f"   Status: {resource['status']}")
                        if resource.get('physicalId'):
                            print(f"   Physical ID: {resource['physicalId']}")
                        print(f"   Progress: {resource['progress']}%")
                        print()
                    
                    elif event_type == 'stack_complete':
                        stack = event['stack']
                        print(f"✅ DEPLOYMENT COMPLETE")
                        print(f"   Status: {stack['status']}")
                        print(f"   Duration: {event.get('duration', 'N/A')}")
                        
                        if stack.get('outputs'):
                            print(f"\n   Outputs:")
                            for output in stack['outputs']:
                                print(f"     - {output['key']}: {output['value']}")
                        break
                    
                    elif event_type == 'error':
                        print(f"❌ ERROR: {event['message']}")
                        if event.get('resource'):
                            print(f"   Resource: {event['resource']['logicalId']}")
                        break
                    
                    elif event_type == 'initial_state':
                        print(f"📊 Initial State Received")
                        print(f"   Stack: {event['stack']['name']}")
                        print(f"   Status: {event['stack']['status']}")
                        print(f"   Resources: {event['stack']['totalResources']}")
                        print()
                
                except websockets.exceptions.ConnectionClosed:
                    print("\n✓ Connection closed")
                    break
    
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("Deployment Tracking Test")
    print("=" * 80)
    print("Make sure:")
    print("1. FastAPI server is running (python app.py or uvicorn app:app)")
    print("2. You have an active CloudFormation stack")
    print("3. Update 'stack_name' variable below with your actual stack name")
    print("=" * 80)
    print()
    
    asyncio.run(test_deployment_tracking())
