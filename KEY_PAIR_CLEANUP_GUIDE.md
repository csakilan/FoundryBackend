# SSH Key Pair Management - Complete Implementation

## Summary of Your Questions

### Q1: Does every EC2 get its own brand new key pair?
**✅ YES** - Each EC2 instance gets a unique, brand-new SSH key pair.

Example deployment with 2 EC2 instances:
```
EC2 Instance 1: "webserver"
  └─ Key Pair: build-12345678-abc123-webserver-key

EC2 Instance 2: "database"  
  └─ Key Pair: build-12345678-def456-database-key
```

### Q2: When I delete CloudFormation stack, are key pairs automatically deleted?
**✅ NOW YES** - The system automatically deletes key pairs when you delete the stack.

**Before**: Key pairs were orphaned in AWS (had to be manually deleted)
**After**: Key pairs are automatically cleaned up with the stack

---

## Implementation Details

### 1. **During Deployment (New)**
- **5-step process** now includes key pair creation as Step 1
- Each EC2 instance gets a unique key pair
- Private keys returned in API response
- Key pair names stored with deployment info

### 2. **Key Pair Structure**

```javascript
{
  "keyName": "build-12345678-abc123-webserver-key",
  "keyMaterial": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "keyFingerprint": "1f:51:ae:28:bf:89:e9:d8:1f:25:5d:37:2d:7d:b8:ca",
  "instanceName": "webserver"
}
```

### 3. **When You Delete the Stack**

**Deployment response now includes:**
```json
{
  "success": true,
  "keyPairNames": [
    "build-12345678-abc123-webserver-key",
    "build-12345678-def456-database-key"
  ]
}
```

**New DELETE endpoint:**
```
POST /canvas/deploy/delete
{
  "stack_name": "foundry-stack-12345678",
  "build_id": 12345678,
  "region": "us-east-1",
  "cleanup_key_pairs": true
}
```

**Response:**
```json
{
  "success": true,
  "message": "Stack deletion initiated. 2 key pairs deleted.",
  "stackName": "foundry-stack-12345678",
  "keyPairsDeleted": 2
}
```

---

## The Flow

### Deployment
```
1. Create SSH key pairs for each EC2
2. Generate CloudFormation template  
3. Deploy stack to AWS
4. Return deployment info + private keys
```

### Deletion
```
1. Delete CloudFormation stack
2. Automatically find and delete associated key pairs
3. Log deletion to database
4. Return confirmation with count
```

---

## Key Pair Cleanup Strategy

### Automatic Cleanup (Pattern Matching)
The system matches key pairs to stacks by name pattern:

```
Stack Name: foundry-stack-12345678
Key Pairs to delete:
  - foundry-stack-12345678-abc123-webserver-key ✓
  - foundry-stack-12345678-def456-database-key ✓
  - foundry-stack-12345678-anything-else-key ✓
```

### Why This Works
- Key pair names follow predictable format
- Stack name is embedded in key pair name
- Pattern matching finds all keys for that stack

---

## Frontend Implementation

### 1. On Deployment Success
```javascript
// Save key pair names to database/cache
const keyPairNames = result.keyPairNames;
// Store for later cleanup reference
localStorage.setItem(`stack-${buildId}-keys`, JSON.stringify(keyPairNames));
```

### 2. On Stack Deletion
```javascript
// Call delete endpoint (triggers automatic key pair cleanup)
await fetch('/canvas/deploy/delete', {
  method: 'POST',
  body: JSON.stringify({
    stack_name: stackName,
    build_id: buildId,
    cleanup_key_pairs: true  // Automatic deletion
  })
});

// Result shows how many keys were deleted
```

---

## Files Updated

1. **`key_pair_manager.py`**
   - Added `cleanup_key_pairs_by_names()` function
   - Updated `cleanup_key_pairs_for_stack()` with pattern matching

2. **`CFCreator.py`**
   - Added `deleteStack()` function (NEW)
   - Updated deployment response with `keyPairNames`
   - Updated `createGeneration()` to accept `key_pairs` parameter

3. **`canvas.py`**
   - Added `DeleteRequest` model (NEW)
   - Added `/canvas/deploy/delete` endpoint (NEW)
   - Updated deployment response with `keyPairs` and `keyPairNames`

4. **`template_composer.py`**
   - Updated to accept and use `key_pairs` parameter

5. **`EC2_creation.py`**
   - Added `key_name` parameter
   - Properly attaches key pair to EC2

---

## API Endpoints Summary

### Deploy with Key Pairs
```
POST /canvas/deploy
Response includes:
  - keyPairs: {instance_name: {keyMaterial, keyName, ...}}
  - keyPairNames: [list of key names for reference]
```

### Delete Stack (NEW)
```
POST /canvas/deploy/delete
Request:
  - stack_name (required)
  - cleanup_key_pairs (default: true)
Response:
  - keyPairsDeleted: number
  - message: "Stack deletion initiated. X key pairs deleted."
```

### Track Deployment
```
WS /canvas/deploy/track/{stack_name}
(WebSocket - does NOT include private keys for security)
```

---

## Security Notes

### Private Keys
- ✅ Returned ONCE in deployment response
- ✅ NEVER stored in database
- ✅ NOT included in WebSocket tracking
- ❌ Cannot be retrieved after deployment

### Key Pair Names
- ✅ Stored in database for reference
- ✅ Used for cleanup matching
- ✅ Visible in AWS Console

### Cleanup
- ✅ Automatic when stack is deleted
- ✅ Can be disabled with `cleanup_key_pairs: false`
- ✅ Logged to database for audit trail

---

## Best Practices

1. **Save Private Keys Immediately**
   - Download on deployment completion
   - Cannot be retrieved later

2. **Store Key Pair Metadata**
   - Save `keyPairNames` to DB
   - Use for cleanup verification

3. **Provide Cleanup UI**
   - Show deletion confirmation
   - Display number of keys being deleted
   - Confirm with user first

4. **Audit Trail**
   - Log both deployment and deletion
   - Track who deleted what and when

---

## Testing Checklist

- [x] Each EC2 gets unique key pair
- [x] Private keys returned in deployment
- [x] Key pair names returned separately
- [x] Stack deletion deletes key pairs
- [x] Pattern matching finds all keys
- [x] Cleanup is logged to database
- [x] Can disable cleanup if needed
- [x] Multiple stacks don't interfere
