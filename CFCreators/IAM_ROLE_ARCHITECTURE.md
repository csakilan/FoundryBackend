# IAM Role Architecture for EC2 Instances

## Overview

The system creates **dynamic IAM roles** based on what services each EC2 instance needs to access. Roles are created **per EC2 instance** and scoped to only the specific resources that EC2 needs.

## ✅ Fixed Issues

- **BEFORE**: EC2 instances hardcoded to use `"ec2CodeDeploy"` profile (which must pre-exist)
- **AFTER**: EC2 instances use dynamically created instance profiles with least-privilege access

## IAM Role Creation Logic

### 1. **EC2 → S3 Only**

**Function**: `create_ec2_s3_role()`

- **Permissions**: GetObject, PutObject, DeleteObject, ListBucket
- **Scope**: Only the specific S3 bucket(s) connected to this EC2
- **Resources Created**:
  - IAM Role: `{build_id}-{unique_id}-ec2-s3-role`
  - Instance Profile: `{build_id}-{unique_id}-ec2-s3-profile`

### 2. **EC2 → DynamoDB Only**

**Function**: `create_ec2_dynamodb_role()`

- **Permissions**: GetItem, PutItem, UpdateItem, DeleteItem, Query, Scan
- **Scope**: Only the specific DynamoDB table(s) connected to this EC2
- **Resources Created**:
  - IAM Role: `{build_id}-{unique_id}-ec2-dynamodb-role`
  - Instance Profile: `{build_id}-{unique_id}-ec2-dynamodb-profile`

### 3. **EC2 → Multiple Services (S3 + DynamoDB)**

**Function**: `create_ec2_multi_service_role()`

- **Permissions**: Combined S3 and DynamoDB policies
- **Scope**: Only resources connected to this specific EC2
- **Resources Created**:
  - IAM Role: `{build_id}-{unique_id}-ec2-multi-service-role`
  - Instance Profile: `{build_id}-{unique_id}-ec2-multi-service-profile`
- **Policies**:
  - S3 Access Policy (if S3 buckets connected)
  - DynamoDB Access Policy (if DynamoDB tables connected)

### 4. **EC2 → RDS**

**No IAM role created** - RDS uses credential-based authentication

- Connection details passed as environment variables:
  - `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_ENGINE`

## How It Works (template_composer.py)

### Phase 1: Parse Dependencies

```python
# Build dependency map from edges
ec2_dependencies = {
    "ec2_node_id": {
        "s3": [s3_node_ids],
        "dynamodb": [dynamo_node_ids],
        "rds": [rds_node_ids]
    }
}
```

### Phase 2: Create Resources (S3, RDS, DynamoDB)

Create all non-EC2 resources first and store references

### Phase 3: Create EC2 with IAM Roles

For each EC2:

1. Check what services it needs (from dependency map)
2. Create appropriate IAM role:
   - **S3 + DynamoDB** → `create_ec2_multi_service_role()`
   - **S3 only** → Would use `create_ec2_s3_role()` (currently goes to multi)
   - **DynamoDB only** → Would use `create_ec2_dynamodb_role()` (currently goes to multi)
3. Generate environment variables for resource names
4. Attach instance profile to EC2

## Environment Variables Injected

### S3 Connections

- `S3_BUCKET_NAME` - First bucket
- `S3_BUCKET_2`, `S3_BUCKET_3`, etc. - Additional buckets

### DynamoDB Connections

- `DYNAMODB_TABLE_NAME` - First table
- `DYNAMODB_TABLE_2`, `DYNAMODB_TABLE_3`, etc. - Additional tables

### RDS Connections

- `DB_HOST` - RDS endpoint address
- `DB_PORT` - RDS port
- `DB_NAME` - Database name
- `DB_USER` - Master username
- `DB_PASSWORD` - Master password
- `DB_ENGINE` - postgres/mysql/etc.

Multiple RDS: `DB_2_HOST`, `DB_2_PORT`, etc.

## Security Best Practices ✓

1. **Least Privilege**: Each EC2 only gets access to resources it's connected to
2. **Scoped Permissions**: S3 access limited to specific buckets, not all S3
3. **Resource-Specific**: DynamoDB access limited to specific tables
4. **Unique Names**: Each role/profile has unique name to avoid conflicts
5. **Tagging**: All IAM resources tagged with BuildId for tracking

## Example CloudFormation Output

For an EC2 connected to S3 and DynamoDB:

```yaml
IAMRole:
  Type: AWS::IAM::Role
  Properties:
    RoleName: build-12345678-abc123-ec2-multi-service-role
    AssumeRolePolicyDocument: { ... }
    Policies:
      - PolicyName: build-12345678-abc123-s3-access-policy
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action: [s3:GetObject, s3:PutObject, ...]
              Resource: [arn:aws:s3:::bucket-name, arn:aws:s3:::bucket-name/*]
      - PolicyName: build-12345678-abc123-dynamodb-access-policy
        PolicyDocument:
          Statement:
            - Effect: Allow
              Action: [dynamodb:GetItem, ...]
              Resource: arn:aws:dynamodb:us-east-1:123456789:table/table-name

InstanceProfile:
  Type: AWS::IAM::InstanceProfile
  Properties:
    InstanceProfileName: build-12345678-abc123-ec2-multi-service-profile
    Roles: [!Ref IAMRole]

EC2Instance:
  Type: AWS::EC2::Instance
  Properties:
    IamInstanceProfile: !Ref InstanceProfile
    UserData: |
      #!/bin/bash
      export S3_BUCKET_NAME="bucket-name"
      export DYNAMODB_TABLE_NAME="table-name"
      # User's custom UserData here...
```

## Testing Checklist

- [x] EC2 alone (no connections) - No IAM role
- [x] EC2 → S3 - S3 access role created
- [x] EC2 → DynamoDB - DynamoDB access role created
- [x] EC2 → S3 + DynamoDB - Multi-service role created
- [x] EC2 → RDS - No IAM role, env vars set
- [x] Multiple EC2s with different dependencies - Each gets own role
- [x] Instance profile properly attached to EC2
