# CloudFormation Update Feature - Testing Guide

## 🎯 What We Built

A complete CloudFormation stack update system with:

- ✅ Stable resource naming (node IDs)
- ✅ Database integration (stores canvas versions)
- ✅ Change set preview (review before applying)
- ✅ Safe updates (no unexpected replacements)
- ✅ Activity logging (audit trail)

---

## 🧪 Testing the Update Flow

### Test 1: Quick Automated Test (Recommended First Test)

```bash
cd /Users/ak/Documents/Pro/VSWorkspace/Projects/FoundryBackend
python3 test_quick_update.py
```

**What it does:**

1. Deploys a simple EC2 stack (t2.micro)
2. Creates a change set to update it (t2.small)
3. Shows change preview with actions (Add/Modify/Remove)
4. Lets you execute or cancel the change set

**Expected output:**

```
📊 CHANGE SET PREVIEW
================================================================================
Change Set: foundry-changeset-20251029-223045
Status: CREATE_COMPLETE
Has Changes: True
Change Count: 1

📝 Changes Detected:
  • Modify: EC2Instance (AWS::EC2::Instance)
```

---

### Test 2: Manual API Testing

#### Step 1: Deploy Initial Stack

```bash
curl -X POST http://localhost:8000/canvas/deploy \
  -H "Content-Type: application/json" \
  -d '{
    "canvas": {
      "nodes": [{
        "id": "node-123",
        "type": "EC2",
        "data": {
          "name": "TestServer",
          "imageId": "Amazon Linux",
          "instanceType": "t2.micro"
        }
      }],
      "edges": []
    },
    "owner_id": 1,
    "region": "us-east-1"
  }'
```

**Response:**

```json
{
  "success": true,
  "stackId": "arn:aws:...",
  "stackName": "foundry-stack-20251029-220205",
  "buildId": 2,
  "status": "CREATE_IN_PROGRESS"
}
```

#### Step 2: Update Stack (Create Change Set)

```bash
curl -X POST http://localhost:8000/canvas/deploy/update \
  -H "Content-Type: application/json" \
  -d '{
    "canvas": {
      "nodes": [{
        "id": "node-123",
        "type": "EC2",
        "data": {
          "name": "TestServer",
          "imageId": "Amazon Linux",
          "instanceType": "t2.small"
        }
      }],
      "edges": []
    },
    "build_id": 2,
    "stack_name": "foundry-stack-20251029-220205",
    "owner_id": 1,
    "region": "us-east-1",
    "auto_execute": false
  }'
```

**Response:**

```json
{
  "success": true,
  "message": "Change set created - awaiting execution",
  "buildId": 2,
  "changeSet": {
    "id": "arn:aws:cloudformation:...",
    "name": "foundry-changeset-20251029-223045",
    "status": "CREATE_COMPLETE",
    "hasChanges": true,
    "changes": [
      {
        "action": "Modify",
        "logicalId": "EC2Instance",
        "resourceType": "AWS::EC2::Instance",
        "replacement": "False"
      }
    ]
  },
  "executed": false
}
```

#### Step 3a: Execute Change Set (If Approved)

```bash
curl -X POST "http://localhost:8000/canvas/deploy/execute-changeset?stack_name=foundry-stack-20251029-220205&change_set_name=foundry-changeset-20251029-223045&build_id=2"
```

#### Step 3b: Cancel Change Set (If Rejected)

```bash
curl -X DELETE "http://localhost:8000/canvas/deploy/changeset?stack_name=foundry-stack-20251029-220205&change_set_name=foundry-changeset-20251029-223045"
```

---

## 🔍 What to Look For

### ✅ Success Indicators:

1. **Stable Naming:**

   - Same node ID → Same resource name across updates
   - Example: `node-123` always generates `12345-node12-TestServer`

2. **Change Detection:**

   - Modify actions when properties change
   - Add actions for new resources
   - Remove actions for deleted resources

3. **No Unexpected Replacements:**

   - `replacement: "False"` for property changes
   - Warnings shown if replacement needed

4. **Database Updates:**
   - Canvas saved after deployment
   - Activity logged for each action
   - Build ID returned for tracking

### ❌ Issues to Watch For:

1. **Different Resource Names:**

   - If node ID changes → new resource name → replacement
   - Fix: Keep node IDs stable

2. **Unexpected Replacements:**

   - Some property changes require replacement
   - Review change set carefully

3. **Database Errors:**
   - Check `.env` has correct database name (MyDB)
   - Verify tables exist

---

## 📊 Key Files Created

| File                              | Purpose                                             |
| --------------------------------- | --------------------------------------------------- |
| `CFCreators/aws_deployer.py`      | Update functions (update_stack, execute_change_set) |
| `routers/canvas.py`               | API endpoints (/deploy/update, /execute-changeset)  |
| `database.py`                     | Database operations (save_build, log_activity)      |
| `CFCreators/NAMING_CONVENTION.md` | Documentation of naming pattern                     |
| `.env`                            | Database credentials (MyDB)                         |

---

## 🚀 Next Steps

1. **Test with Real Canvas:**

   - Use your frontend to create a canvas
   - Deploy it
   - Modify it
   - Update the deployment

2. **Test Different Changes:**

   - Add a resource (S3 bucket)
   - Remove a resource
   - Modify properties
   - Change connections

3. **Monitor in AWS Console:**
   - View change sets in CloudFormation
   - Watch stack updates
   - Review resources

---

## 💡 Tips

- **Always review change sets** before executing
- **Watch for replacement warnings** ⚠️
- **Keep node IDs stable** for consistent naming
- **Use build_id** to track deployments
- **Check activity logs** for audit trail

---

## 🐛 Troubleshooting

### Issue: "Stack not found"

- Deploy a stack first using `/canvas/deploy`
- Verify stack name is correct

### Issue: "No changes detected"

- Canvas is identical to deployed version
- This is expected behavior ✓

### Issue: "Replacement: True"

- Some property changes require resource replacement
- Review carefully before executing
- Data may be lost on replacement

### Issue: "Database errors"

- Check `.env` has `RDS_DATABASE=MyDB`
- Verify tables exist in MyDB database
- Test connection with `python3 database.py`

---

## 📝 Summary

You now have a **production-ready CloudFormation update system** that:

- ✅ Generates stable, consistent resource names
- ✅ Previews changes before applying
- ✅ Tracks all deployments in database
- ✅ Logs all activities for audit
- ✅ Handles errors gracefully

**Happy testing!** 🎉
