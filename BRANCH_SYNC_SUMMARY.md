# Branch Sync Summary - Demo Mode & IAM Features

This document confirms all critical code has been synced to the current branch (`hola`).

## ✅ Changes Applied

### 1. **Template Composer - Demo Mode IAM Logic**
**File**: `CFCreators/template_composer.py`

Added DEMO_MODE support to skip IAM role creation and use pre-created instance profile:

```python
# Check if DEMO_MODE is enabled
demo_mode = os.getenv('DEMO_MODE', 'false').lower() == 'true'

# If EC2 has connections, create IAM role and env vars (or use demo role)
if has_s3 or has_dynamodb:
    if demo_mode:
        # Use pre-created demo IAM role (skips IAM propagation delay)
        demo_profile_name = os.getenv('DEMO_IAM_INSTANCE_PROFILE_NAME', 'foundry-demo-ec2-profile')
        print(f"  🚀 DEMO MODE: Using pre-created instance profile: {demo_profile_name}")
        print(f"  ⚡ Skipping IAM role creation (saves 30-90 seconds)")
        
        # Reference existing instance profile by name (no resource creation)
        instance_profile = demo_profile_name  # Store as string instead of object
    else:
        # Production mode: Create new IAM role dynamically
        # ... creates IAM role with create_ec2_multi_service_role()
```

### 2. **EC2 Creation - Custom AMI Support**
**File**: `CFCreators/singleServiceCreator/EC2_creation.py`

Already present - Demo mode uses custom pre-configured Ubuntu AMI:

```python
# DEMO MODE: Use custom Ubuntu AMI with pre-installed dependencies
demo_mode = os.getenv('DEMO_MODE', 'false').lower() == 'true'
if demo_mode and image_input == "Ubuntu":
    custom_ami = "ami-0650b7c7445670128"
    print(f"  🚀 DEMO MODE: Using custom Ubuntu AMI: {custom_ami}")
    return custom_ami
```

### 3. **EC2 Creation - Instance Profile Handling**
**File**: `CFCreators/singleServiceCreator/EC2_creation.py`

Already present - Supports both string (demo mode) and object (production) instance profiles:

```python
# Add IAM instance profile if provided (for S3, DynamoDB access)
if instance_profile:
    # Check if instance_profile is a string (demo mode) or a Troposphere object
    if isinstance(instance_profile, str):
        # Demo mode: Use pre-created instance profile by name
        props['IamInstanceProfile'] = instance_profile
    else:
        # Production mode: Reference dynamically created instance profile
        props['IamInstanceProfile'] = Ref(instance_profile)
else:
    # Fallback to ec2CodeDeploy if no custom instance profile
    props['IamInstanceProfile'] = "ec2CodeDeploy"
```

### 4. **IAM Creation Functions**
**File**: `CFCreators/singleServiceCreator/IAM_creation.py`

Already present - All three IAM creation functions with proper sanitization:

- `create_ec2_s3_role()` - EC2 to S3 access
- `create_ec2_dynamodb_role()` - EC2 to DynamoDB access  
- `create_ec2_multi_service_role()` - EC2 to multiple services (S3 + DynamoDB)

All functions include:
- Name sanitization for IAM compliance
- Unique role/policy naming with build_id prefix
- Proper tags (Name, OriginalPurpose, ManagedBy, BuildId)
- Instance profile creation

## ✅ Environment Variables Preserved

**File**: `.env`

```dotenv
# Testing: Force all resources to use "default" as build_id prefix
USE_DEFAULT_BUILD_ID=true

# Demo mode: Use pre-created IAM role to skip IAM propagation delay (saves 30-90 seconds)
DEMO_MODE=true
DEMO_IAM_ROLE_NAME=foundry-demo-ec2-role
DEMO_IAM_INSTANCE_PROFILE_NAME=foundry-demo-ec2-profile
```

Plus database credentials:
- `RDS_PASSWORD`
- `RDS_DATABASE`
- `RDS_HOST`
- `RDS_PORT`
- `RDS_USER`
- `DATABASE_URL`
- `GITHUB_WEBHOOK_SECRET`

## 🎯 Key Features Now Available

1. **DEMO_MODE** - When enabled (`DEMO_MODE=true`):
   - Skips IAM role creation (saves 30-90 seconds deployment time)
   - Uses pre-created instance profile: `foundry-demo-ec2-profile`
   - Uses custom Ubuntu AMI with pre-installed dependencies: `ami-0650b7c7445670128`

2. **USE_DEFAULT_BUILD_ID** - When enabled:
   - Forces all resources to use "default" as build_id prefix
   - Simplifies testing and debugging

3. **Dynamic IAM Creation** - When DEMO_MODE is off:
   - Automatically creates IAM roles based on EC2 dependencies
   - Supports S3, DynamoDB, and multi-service access
   - Proper naming conventions and tagging

4. **Environment Variable Injection**:
   - Auto-injects S3 bucket names (`S3_BUCKET_NAME`)
   - Auto-injects DynamoDB table names (`DYNAMODB_TABLE_NAME`)
   - Auto-injects RDS connection info (`DB_HOST`, `DB_PORT`, etc.)

## 🚀 Next Steps

The branch is now fully synced with all IAM and demo mode features. To verify:

1. Set `DEMO_MODE=true` in `.env`
2. Deploy an EC2 instance connected to S3/DynamoDB
3. Verify it uses the pre-created instance profile (check logs for "🚀 DEMO MODE")
4. Deployment should be 30-90 seconds faster (no IAM propagation delay)

## 📝 Files Modified in This Sync

1. `CFCreators/template_composer.py` - Added DEMO_MODE logic
2. `CFCreators/singleServiceCreator/EC2_creation.py` - Already had demo AMI support
3. `CFCreators/singleServiceCreator/IAM_creation.py` - Already had all IAM functions
4. `.env` - Already had all environment variables

All code is now in sync with the `liveDemo` branch features! ✅
