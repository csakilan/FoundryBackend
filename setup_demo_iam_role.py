#!/usr/bin/env python3
"""
Setup Demo IAM Role for Foundry

Creates a pre-configured IAM role and instance profile for demo purposes.
This role has broad permissions for S3 and DynamoDB to work with any demo deployment.

Run this ONCE before your demo to create the reusable IAM role.
This skips the 30-90 second IAM propagation delay during live demos.
"""

import boto3
import json
from botocore.exceptions import ClientError

# IAM role and instance profile names (must match .env file)
ROLE_NAME = "foundry-demo-ec2-role"
INSTANCE_PROFILE_NAME = "foundry-demo-ec2-profile"
REGION = "us-east-1"

# Broad permissions for demo (allows access to any S3 bucket or DynamoDB table with "default-*" prefix)
POLICY_DOCUMENT = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:ListBucket"
            ],
            "Resource": [
                "arn:aws:s3:::default-*",
                "arn:aws:s3:::default-*/*"
            ]
        },
        {
            "Effect": "Allow",
            "Action": [
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan"
            ],
            "Resource": "arn:aws:dynamodb:*:*:table/default-*"
        }
    ]
}

ASSUME_ROLE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {"Service": "ec2.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }
    ]
}


def create_demo_iam_role():
    """Create the demo IAM role and instance profile."""
    iam = boto3.client('iam', region_name=REGION)
    
    print("=" * 80)
    print("FOUNDRY DEMO IAM ROLE SETUP")
    print("=" * 80)
    print(f"\nCreating demo IAM resources:")
    print(f"  - Role: {ROLE_NAME}")
    print(f"  - Instance Profile: {INSTANCE_PROFILE_NAME}")
    print(f"  - Region: {REGION}\n")
    
    # Step 1: Create IAM Role
    try:
        print(f"[1/4] Creating IAM role '{ROLE_NAME}'...")
        iam.create_role(
            RoleName=ROLE_NAME,
            AssumeRolePolicyDocument=json.dumps(ASSUME_ROLE_POLICY),
            Description="Foundry demo role - allows EC2 to access S3 and DynamoDB",
            Tags=[
                {"Key": "Purpose", "Value": "FoundryDemo"},
                {"Key": "ManagedBy", "Value": "FoundrySetupScript"}
            ]
        )
        print(f"  ✓ Role created successfully")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"  ⚠ Role already exists, skipping...")
        else:
            raise
    
    # Step 2: Attach inline policy to role
    try:
        print(f"\n[2/4] Attaching permissions policy...")
        iam.put_role_policy(
            RoleName=ROLE_NAME,
            PolicyName="FoundryDemoPolicy",
            PolicyDocument=json.dumps(POLICY_DOCUMENT)
        )
        print(f"  ✓ Policy attached successfully")
    except ClientError as e:
        print(f"  ⚠ Error attaching policy: {e}")
        raise
    
    # Step 3: Create instance profile
    try:
        print(f"\n[3/4] Creating instance profile '{INSTANCE_PROFILE_NAME}'...")
        iam.create_instance_profile(
            InstanceProfileName=INSTANCE_PROFILE_NAME,
            Tags=[
                {"Key": "Purpose", "Value": "FoundryDemo"},
                {"Key": "ManagedBy", "Value": "FoundrySetupScript"}
            ]
        )
        print(f"  ✓ Instance profile created successfully")
    except ClientError as e:
        if e.response['Error']['Code'] == 'EntityAlreadyExists':
            print(f"  ⚠ Instance profile already exists, skipping...")
        else:
            raise
    
    # Step 4: Add role to instance profile
    try:
        print(f"\n[4/4] Adding role to instance profile...")
        iam.add_role_to_instance_profile(
            InstanceProfileName=INSTANCE_PROFILE_NAME,
            RoleName=ROLE_NAME
        )
        print(f"  ✓ Role added to instance profile successfully")
    except ClientError as e:
        if e.response['Error']['Code'] == 'LimitExceeded':
            print(f"  ⚠ Role already added to instance profile, skipping...")
        else:
            raise
    
    print("\n" + "=" * 80)
    print("✅ DEMO IAM ROLE SETUP COMPLETE!")
    print("=" * 80)
    print("\nYour demo IAM resources are ready:")
    print(f"  - Role ARN: arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:role/{ROLE_NAME}")
    print(f"  - Instance Profile ARN: arn:aws:iam::{boto3.client('sts').get_caller_identity()['Account']}:instance-profile/{INSTANCE_PROFILE_NAME}")
    print("\nPermissions granted:")
    print("  ✓ S3: Read/write to any bucket starting with 'default-'")
    print("  ✓ DynamoDB: Full access to any table starting with 'default-'")
    print("\nTo use in demos:")
    print("  1. Set DEMO_MODE=true in your .env file")
    print("  2. Deploy stacks - they'll use this pre-created role")
    print("  3. Deployment will be 30-90 seconds faster!")
    print("\nTo delete these resources later:")
    print(f"  aws iam remove-role-from-instance-profile --instance-profile-name {INSTANCE_PROFILE_NAME} --role-name {ROLE_NAME}")
    print(f"  aws iam delete-instance-profile --instance-profile-name {INSTANCE_PROFILE_NAME}")
    print(f"  aws iam delete-role-policy --role-name {ROLE_NAME} --policy-name FoundryDemoPolicy")
    print(f"  aws iam delete-role --role-name {ROLE_NAME}")
    print()


if __name__ == "__main__":
    try:
        create_demo_iam_role()
    except Exception as e:
        print(f"\n❌ Error: {e}")
        exit(1)
