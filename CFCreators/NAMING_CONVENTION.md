# AWS Resource Naming Convention

## Overview

All AWS resources created by this system follow a **consistent naming pattern** to ensure uniqueness and easy identification.

## Naming Pattern

```
<build_id>-<unique_number>-<user_provided_name>
```

### Components

1. **`build_id`** - Unique identifier for the entire build/deployment

   - Example: `12345`, `67890`, `42`
   - Generated from database or system (unique per deployment)
   - Groups all resources belonging to the same deployment

2. **`unique_number`** - 6-character identifier from node ID

   - Example: `a1b2c3`, `xyz789`
   - Ensures no naming collisions between resources in the same build
   - **Stable across regenerations** (same canvas → same names)

3. **`user_provided_name`** - User's chosen name (sanitized)
   - Example: `webserver`, `uploads`, `database`
   - Makes resources human-readable

---

## Examples by Service

### EC2 Instances

**Pattern:** `<build_id>-<unique_number>-<instance_name>`

```
12345-a1b2c3-webserver
67890-xyz789-apiserver
42-123abc-worker
```

### S3 Buckets

**Pattern:** `<build_id>-<unique_number>-<bucket_name>`

```
12345-d4e5f6-uploads
67890-abc123-storage
42-789xyz-backups
```

### RDS Databases

**Pattern:** `<build_id>-<unique_number>-<db_name>`

```
12345-f7g8h9-userdb
67890-def456-analytics
42-ghi789-cache
```

### DynamoDB Tables

**Pattern:** `<build_id>-<unique_number>-<table_name>`

```
12345-j1k2l3-sessions
67890-jkl012-products
42-mno345-logs
```

### IAM Roles

**Pattern:** `<build_id>-<unique_number>-<purpose>-role`

```
12345-m4n5o6-ec2-s3-role
67890-pqr678-ec2-dynamodb-role
42-stu901-ec2-multi-service-role
```

---

## Why This Matters

### ✅ Before (With Stable Node IDs)

```
Same canvas → Same template → Same resource names
Result: CloudFormation UPDATES resources ✓
```

### ❌ Without Stable IDs

```
Same canvas → Different template → Different resource names
Result: CloudFormation REPLACES resources (downtime, data loss) ✗
```

---

## Technical Details

### How `unique_number` is Generated

The 6-character unique number comes from the **first 6 characters of the node ID** from the ReactFlow canvas:

```python
unique_number = node['id'][:6]  # e.g., "abc123"
```

- **Node ID** is stable across template regenerations
- **Same node** always produces the **same unique_number**
- Prevents resource replacements during updates

### Name Sanitization Rules

User-provided names are sanitized to meet AWS requirements:

- **Spaces** removed: `My Server` → `MyServer`
- **Underscores** removed: `user_data` → `userdata`
- **Lowercase** (S3 only): `MyBucket` → `mybucket`
- **Invalid characters** replaced with hyphens

---

## Tags Applied

All resources also receive these CloudFormation tags:

| Tag            | Description          | Example                 |
| -------------- | -------------------- | ----------------------- |
| `Name`         | Full resource name   | `prod-a1b2c3-webserver` |
| `OriginalName` | User's original name | `My Web Server`         |
| `BuildId`      | Project identifier   | `prod`                  |
| `ManagedBy`    | Management system    | `CloudFormation`        |

---

## Backward Compatibility

For resources created without node IDs (older code), the system falls back to:

```python
# Fallback: timestamp-based unique number
import time
unique_number = str(int(time.time()))[-6:]
```

This ensures the system doesn't break if node IDs aren't available.

---

## Quick Reference

| Service      | Max Length | Special Rules                      |
| ------------ | ---------- | ---------------------------------- |
| **EC2**      | 255 chars  | Alphanumeric, hyphens              |
| **S3**       | 63 chars   | Lowercase, no underscores          |
| **RDS**      | 63 chars   | Alphanumeric, hyphens              |
| **DynamoDB** | 255 chars  | Alphanumeric, hyphens, underscores |
| **IAM**      | 64 chars   | Alphanumeric, hyphens, underscores |

---

## Example: Full Resource Lifecycle

1. **User creates canvas** with EC2 node ID: `node-abc123xyz`
2. **User names instance:** `"My Web Server"`
3. **System generates:**
   - `build_id`: `12345` (from database build ID)
   - `unique_number`: `abc123` (from node ID)
   - `sanitized_name`: `MyWebServer`
4. **Final resource name:** `12345-abc123-MyWebServer`
5. **User updates canvas** (same node)
6. **System regenerates** template with **same name**: `12345-abc123-MyWebServer`
7. **CloudFormation updates** resource in-place ✓ (no replacement)

---

## Related Files

- `CFCreators/singleServiceCreator/EC2_creation.py`
- `CFCreators/singleServiceCreator/S3_creation.py`
- `CFCreators/singleServiceCreator/RDS_creation.py`
- `CFCreators/singleServiceCreator/DynamoDB_creation.py`
- `CFCreators/singleServiceCreator/IAM_creation.py`

---

**Last Updated:** October 29, 2025  
**Version:** 2.0 (Stable Node IDs)
