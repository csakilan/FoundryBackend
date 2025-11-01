# AWS Resource Naming Convention

## Overview

All AWS resources created by this system follow a **consistent naming pattern** to ensure uniqueness and easy identification.

## Naming Pattern

```
<build_id>-<unique_number>-<user_provided_name>

Note: recent changes (Oct 2025) also sanitize the auto-generated parts derived from node IDs and build IDs so the full resource name always meets each service's naming pattern.

- **`unique_number`** (derived from node id) is sanitized before use: underscores and other invalid chars are converted/removed so the 6-character token contains only characters valid for the target resource type.
- **`build_id`** is sanitized when used in S3/RDS names to remove invalid characters.
1. **`build_id`** - Unique identifier for the entire build/deployment

   - Example: `12345`, `67890`, `42`
   - Generated from database or system (unique per deployment)
   - Groups all resources belonging to the same deployment

2. **`unique_number`** - 6-character identifier from node ID

   - Example: `a1b2c3`, `xyz789`

Notes / recent changes:

- The implementation now sanitizes the `unique_number` produced from the node id (e.g. `s3_bucket_1` → `s3buc`) before building the bucket name, so underscores in node ids will not end up in the bucket name.
- All S3 bucket name parts are lowercased and cleaned to meet S3 rules (lowercase letters, numbers, hyphens only; no underscores).
- The code uses a dedicated sanitizer that replaces invalid characters with hyphens, removes consecutive hyphens, and trims leading/trailing hyphens. Build ids are sanitized as well.
- Examples after sanitization:

```

prod-s3buc-my-app-storage
default-s3buc-appstorage

```
   - Ensures no naming collisions between resources in the same build
   - **Stable across regenerations** (same canvas → same names)

3. **`user_provided_name`** - User's chosen name (sanitized)
   - Example: `webserver`, `uploads`, `database`
   - Makes resources human-readable

---


Notes / recent changes:

- RDS identifiers must match a stricter pattern (alphanumeric and hyphens). Node-derived tokens and build IDs are now sanitized to ensure the generated `DBInstanceIdentifier` follows the CloudFormation/RDS pattern: no underscores, only letters/numbers and single hyphens where needed.
- The code now runs a sanitizer that converts non-alphanumeric characters to hyphens, collapses repeated hyphens, and trims leading/trailing hyphens before composing the final identifier.
- Example: node id `rds_in_001` + build `foundry-test` + dbName `app_db5` → `foundry-test-rdsin-appdb5`
## Examples by Service

### EC2 Instances

## CloudFormation / Deployment Notes (IAM capability)

- Templates that create IAM resources with explicit names now require the CloudFormation capability `CAPABILITY_NAMED_IAM`. The deployer and change-set flow were updated to pass `CAPABILITY_NAMED_IAM` when creating stacks and change sets. If you see an error about IAM capabilities, ensure you consent to `CAPABILITY_NAMED_IAM` when deploying.

**Pattern:** `<build_id>-<unique_number>-<instance_name>`

```

12345-a1b2c3-webserver
67890-xyz789-apiserver
42-123abc-worker

```
token = sanitize(node['id'][:6])  # e.g., "s3_buc" -> "s3buc" or "s3-buc" depending on sanitizer
unique_number = token

- **Node ID** is stable across template regenerations

```

12345-d4e5f6-uploads
67890-abc123-storage
42-789xyz-backups

```

### RDS Databases

**Pattern:** `<build_id>-<unique_number>-<db_name>`

- Implementation detail:
- S3 creation now uses Troposphere's `Tags(...)` helper (a `Tags` object) when building the template rather than a raw Python list of dictionaries. This ensures the generated CloudFormation template adheres to troposphere expectations and avoids runtime errors like: `S3s3bucket1.Tags is <class 'list'>, expected <class 'troposphere.Tags'>`.

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

````

---

## Technical Details

### How `unique_number` is Generated

The 6-character unique number comes from the **first 6 characters of the node ID** from the ReactFlow canvas:

```python
unique_number = node['id'][:6]  # e.g., "abc123"
````

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
