# Demo Mode Setup Guide

## Problem
IAM role creation during CloudFormation deployment takes **30-90 seconds** due to AWS's eventual consistency delay. This is too slow for a 2-minute live demo.

## Solution
Use a **pre-created reusable IAM role** that exists before the demo. This skips IAM role creation entirely, making deployments **much faster**.

---

## Setup (Run ONCE before your demo)

### Step 1: Create the Demo IAM Role
```bash
python3 setup_demo_iam_role.py
```

This creates:
- IAM Role: `foundry-demo-ec2-role`
- Instance Profile: `foundry-demo-ec2-profile`
- Permissions: S3 and DynamoDB access for resources starting with `default-*`

### Step 2: Verify .env Configuration
Make sure your `.env` file has:
```bash
DEMO_MODE=true
DEMO_IAM_ROLE_NAME=foundry-demo-ec2-role
DEMO_IAM_INSTANCE_PROFILE_NAME=foundry-demo-ec2-profile
USE_DEFAULT_BUILD_ID=true
```

---

## How It Works

### Production Mode (DEMO_MODE=false)
```
Deploy → Create IAM Role → Wait 30-90s → Create Instance Profile → Create EC2
         ⏱️ SLOW
```

### Demo Mode (DEMO_MODE=true)
```
Deploy → Use existing IAM Role → Create EC2 immediately
         ⚡ FAST (saves 30-90 seconds!)
```

---

## During Your Demo

1. **Keep DEMO_MODE=true in .env**
2. Deploy your stack normally
3. You'll see: `🚀 DEMO MODE: Using pre-created instance profile`
4. Stack creation will skip IAM role creation
5. **30-90 seconds saved!** ✨

---

## After Your Demo

### Option 1: Keep Demo Role (Recommended)
Just leave it - it doesn't cost anything and you can use it for future demos.

### Option 2: Delete Demo Role
```bash
aws iam remove-role-from-instance-profile --instance-profile-name foundry-demo-ec2-profile --role-name foundry-demo-ec2-role
aws iam delete-instance-profile --instance-profile-name foundry-demo-ec2-profile
aws iam delete-role-policy --role-name foundry-demo-ec2-role --policy-name FoundryDemoPolicy
aws iam delete-role --role-name foundry-demo-ec2-role
```

---

## Switching Back to Production Mode

When you want full dynamic IAM role creation (for real deployments):

1. Set `DEMO_MODE=false` in `.env`
2. Restart your backend server
3. Deployments will create unique IAM roles per stack

---

## Security Note

The demo IAM role has **broad permissions** to any S3 bucket or DynamoDB table starting with `default-*`. This is fine for demos but not recommended for production use.

For production, use `DEMO_MODE=false` to create scoped IAM roles for each specific deployment.
