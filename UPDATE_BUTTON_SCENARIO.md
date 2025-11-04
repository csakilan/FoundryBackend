# Update Button Scenario

## Initial State: After Successful Deployment

**Step 1: User clicks "Deploy"**

Frontend sends to `POST /deploy`:
```json
{
  "canvas": {
    "nodes": [
      {
        "id": "s3:abc123",
        "type": "S3",
        "position": { "x": 100, "y": 100 },
        "data": {
          "label": "S3",
          "bucketName": "my-app-bucket"
        }
      }
    ],
    "edges": []
  },
  "owner_id": 1,
  "region": "us-east-1"
}
```

**Backend Response:**
```json
{
  "success": true,
  "message": "Deployment initiated",
  "buildId": 42,                              // ← SAVE THIS!
  "stackName": "foundry-stack-20251103-142530", // ← SAVE THIS!
  "stackId": "arn:aws:cloudformation:...",
  "region": "us-east-1"
}
```

**Frontend MUST save:**
- ✅ `buildId: 42`
- ✅ `stackName: "foundry-stack-20251103-142530"`

---

## User Modifies Canvas and Clicks "Update"

**Step 2: User adds an EC2 instance to canvas**

Canvas now has:
```javascript
{
  nodes: [
    { id: "s3:abc123", ... },      // Original S3 (kept)
    { id: "ec2:xyz789", ... }      // NEW EC2 (added)
  ],
  edges: []
}
```

**Step 3: User clicks "Update" button**

Frontend should send to `POST /deploy/update`:

```json
{
  "canvas": {
    "nodes": [
      {
        "id": "s3:abc123",           // ← Same as original
        "type": "S3",
        "position": { "x": 100, "y": 100 },
        "data": {
          "label": "S3",
          "bucketName": "my-app-bucket"
        }
      },
      {
        "id": "ec2:xyz789",          // ← NEW node
        "type": "EC2",
        "position": { "x": 300, "y": 100 },
        "data": {
          "label": "EC2",
          "name": "web-server",
          "imageId": "Ubuntu",
          "instanceType": "t3.micro",
          "storage": {
            "rootVolumeSizeGiB": 20,
            "rootVolumeType": "gp3",
            "deleteOnTermination": true
          }
        }
      }
    ],
    "edges": []
  },
  "build_id": 42,                              // ← From deploy response
  "stack_name": "foundry-stack-20251103-142530", // ← From deploy response
  "owner_id": 1,
  "region": "us-east-1",
  "auto_execute": false                        // ← Preview first!
}
```

---

## Key Points for Frontend

### **Required Fields:**
1. ✅ `canvas` - The ENTIRE current canvas (not just changes!)
2. ✅ `build_id` - From the original deploy response
3. ✅ `stack_name` - From the original deploy response

### **Important Notes:**

**❌ WRONG - Sending only new nodes:**
```json
{
  "canvas": {
    "nodes": [
      { "id": "ec2:xyz789", ... }  // ← Missing S3 node!
    ]
  }
}
```
This would DELETE the S3 bucket! ⚠️

**✅ CORRECT - Sending entire canvas:**
```json
{
  "canvas": {
    "nodes": [
      { "id": "s3:abc123", ... },  // ← Keep existing
      { "id": "ec2:xyz789", ... }  // ← Add new
    ]
  }
}
```

---

## Frontend State Management

**After Deployment:**
```javascript
// Save these from deploy response
const deployState = {
  buildId: response.buildId,
  stackName: response.stackName,
  deployedCanvas: currentCanvas  // Save the deployed canvas
};
```

**Before Update:**
```javascript
// When user clicks "Update" button
const updateRequest = {
  canvas: currentCanvas,           // Current canvas from ReactFlow
  build_id: deployState.buildId,   // From deployment
  stack_name: deployState.stackName, // From deployment
  owner_id: 1,
  region: 'us-east-1',
  auto_execute: false              // Or true if user confirmed
};

fetch('/deploy/update', {
  method: 'POST',
  body: JSON.stringify(updateRequest)
});
```

---

## Update Response

**Backend returns:**
```json
{
  "success": true,
  "message": "Change set created - awaiting execution",
  "buildId": 42,
  "changeSet": {
    "id": "arn:aws:cloudformation:...",
    "name": "foundry-changeset-20251103-143025",
    "status": "CREATE_COMPLETE",
    "hasChanges": true,
    "changes": [
      {
        "action": "Add",
        "logicalId": "EC2DefaultXyz789WebServer",
        "resourceType": "AWS::EC2::Instance",
        "replacement": "N/A"
      }
    ]
  },
  "executed": false
}
```

**Frontend should:**
1. Show the changes to user
2. Display "Add EC2 instance" action
3. Ask user to confirm
4. If confirmed, call `/deploy/execute-changeset` OR send another update with `auto_execute: true`

---

## Complete Frontend Flow

```javascript
// 1. Initial Deploy
const deployResponse = await fetch('/deploy', {
  method: 'POST',
  body: JSON.stringify({ canvas, owner_id: 1, region: 'us-east-1' })
});

const { buildId, stackName } = await deployResponse.json();

// Save these!
localStorage.setItem('buildId', buildId);
localStorage.setItem('stackName', stackName);

// 2. Later: User modifies canvas and clicks "Update"
const currentCanvas = getCanvasFromReactFlow(); // Get current state

const updateResponse = await fetch('/deploy/update', {
  method: 'POST',
  body: JSON.stringify({
    canvas: currentCanvas,              // ENTIRE canvas
    build_id: localStorage.getItem('buildId'),
    stack_name: localStorage.getItem('stackName'),
    owner_id: 1,
    region: 'us-east-1',
    auto_execute: false
  })
});

const { changeSet } = await updateResponse.json();

// 3. Show changes to user
showChangeSetPreview(changeSet.changes);

// 4. If user confirms, execute
if (userConfirmed) {
  await fetch('/deploy/execute-changeset', {
    method: 'POST',
    body: JSON.stringify({
      stack_name: localStorage.getItem('stackName'),
      change_set_name: changeSet.name
    })
  });
}
```

---

## Summary

**What frontend needs to send to `/deploy/update`:**

1. ✅ **Entire canvas** (all nodes + edges, not just changes)
2. ✅ **build_id** (from original deployment response)
3. ✅ **stack_name** (from original deployment response)
4. ✅ **auto_execute** (`false` to preview, `true` to apply immediately)

**The backend handles:**
- Comparing old vs new canvas
- Identifying what changed
- Creating CloudFormation change set
- Returning preview of changes
