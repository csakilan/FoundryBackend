# IAM_creation.py
from typing import Dict, Any, List
from troposphere import Template, Ref, GetAtt, Sub
import troposphere.iam as iam

def create_ec2_s3_role(
    t: Template,
    s3_bucket_resource,
    *,
    logical_id: str = None,
    build_id: str = "default",
    unique_id: str = None
) -> tuple:
    """
    Create IAM role and instance profile for EC2 to access S3.
    
    Args:
        t: Troposphere Template object
        s3_bucket_resource: The S3 bucket resource object
        logical_id: CloudFormation logical resource ID (auto-generated if None)
        build_id: Build ID to prefix the role name
        unique_id: Unique identifier for stable naming (e.g., EC2 node ID)
    
    Returns:
        Tuple of (iam_role, instance_profile)
    """
    
    # Generate unique identifiers: <build_id>-<unique_number>-<purpose>
    # Use unique_id if provided for stability, otherwise fallback to timestamp
    if unique_id:
        unique_number = unique_id[:6]
    else:
        import time
        unique_number = str(int(time.time()))[-6:]
    
    role_name = f"{build_id}-{unique_number}-ec2-s3-role"
    policy_name = f"{build_id}-{unique_number}-s3-access-policy"
    
    # Generate logical ID if not provided
    if logical_id is None:
        logical_id = f"IAM{build_id.replace('-', '').title()}{unique_number}EC2S3Role"
    
    print(f"  → Generated unique IAM role name: {role_name}")
    print(f"  → Generated logical ID: {logical_id}")
    
    # Create IAM Role with EC2 assume role policy
    role = iam.Role(
        logical_id,
        RoleName=role_name,  # Explicit role name for consistency
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        },
        Policies=[
            iam.Policy(
                PolicyName=policy_name,  # Use generated unique policy name
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket"
                        ],
                        "Resource": [
                            GetAtt(s3_bucket_resource, "Arn"),              # Bucket itself
                            Sub(f"${{BucketArn}}/*", BucketArn=GetAtt(s3_bucket_resource, "Arn"))  # Objects in bucket
                        ]
                    }]
                }
            )
        ],
        Tags=[
            {"Key": "Name", "Value": role_name},
            {"Key": "OriginalPurpose", "Value": "ec2-s3-access"},
            {"Key": "ManagedBy", "Value": "CloudFormation"},
            {"Key": "BuildId", "Value": build_id}
        ]
    )
    
    t.add_resource(role)
    
    # Create Instance Profile (required bridge between IAM role and EC2)
    instance_profile_name = f"{build_id}-{unique_number}-ec2-s3-profile"
    instance_profile_logical_id = f"{logical_id}InstanceProfile"
    
    instance_profile = iam.InstanceProfile(
        instance_profile_logical_id,
        InstanceProfileName=instance_profile_name,  # Explicit instance profile name
        Roles=[Ref(role)]
    )
    
    t.add_resource(instance_profile)
    
    return role, instance_profile


def create_ec2_dynamodb_role(
    t: Template,
    dynamodb_table_resource,
    *,
    logical_id: str = None,
    build_id: str = "default",
    unique_id: str = None
) -> tuple:
    """
    Create IAM role and instance profile for EC2 to access DynamoDB.
    
    Args:
        t: Troposphere Template object
        dynamodb_table_resource: The DynamoDB table resource object
        logical_id: CloudFormation logical resource ID (auto-generated if None)
        build_id: Build ID to prefix the role name
        unique_id: Unique identifier for stable naming (e.g., EC2 node ID)
    
    Returns:
        Tuple of (iam_role, instance_profile)
    """
    
    # Generate unique identifiers: <build_id>-<unique_number>-<purpose>
    # Use unique_id if provided for stability, otherwise fallback to timestamp
    if unique_id:
        unique_number = unique_id[:6]
    else:
        import time
        unique_number = str(int(time.time()))[-6:]
    
    role_name = f"{build_id}-{unique_number}-ec2-dynamodb-role"
    policy_name = f"{build_id}-{unique_number}-dynamodb-access-policy"
    
    # Generate logical ID if not provided
    if logical_id is None:
        logical_id = f"IAM{build_id.replace('-', '').title()}{unique_number}EC2DynamoDBRole"
    
    print(f"  → Generated unique IAM role name: {role_name}")
    print(f"  → Generated logical ID: {logical_id}")
    
    # Create IAM Role with EC2 assume role policy
    role = iam.Role(
        logical_id,
        RoleName=role_name,  # Explicit role name for consistency
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        },
        Policies=[
            iam.Policy(
                PolicyName=policy_name,  # Use generated unique policy name
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:GetItem",
                            "dynamodb:PutItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:DeleteItem",
                            "dynamodb:Query",
                            "dynamodb:Scan"
                        ],
                        "Resource": GetAtt(dynamodb_table_resource, "Arn")
                    }]
                }
            )
        ],
        Tags=[
            {"Key": "Name", "Value": role_name},
            {"Key": "OriginalPurpose", "Value": "ec2-dynamodb-access"},
            {"Key": "ManagedBy", "Value": "CloudFormation"},
            {"Key": "BuildId", "Value": build_id}
        ]
    )
    
    t.add_resource(role)
    
    # Create Instance Profile
    instance_profile_name = f"{build_id}-{unique_number}-ec2-dynamodb-profile"
    instance_profile_logical_id = f"{logical_id}InstanceProfile"
    
    instance_profile = iam.InstanceProfile(
        instance_profile_logical_id,
        InstanceProfileName=instance_profile_name,  # Explicit instance profile name
        Roles=[Ref(role)]
    )
    
    t.add_resource(instance_profile)
    
    return role, instance_profile


def create_ec2_multi_service_role(
    t: Template,
    services: Dict[str, Any],
    *,
    logical_id: str = None,
    build_id: str = "default",
    unique_id: str = None
) -> tuple:
    """
    Create IAM role with policies for multiple services (S3, DynamoDB, RDS).
    
    Args:
        t: Troposphere Template object
        services: Dict with keys like 's3_buckets', 'dynamodb_tables' containing resource objects
        logical_id: CloudFormation logical resource ID (auto-generated if None)
        build_id: Build ID to prefix the role name
        unique_id: Unique identifier for stable naming (e.g., EC2 node ID)
    
    Returns:
        Tuple of (iam_role, instance_profile)
    """
    
    # Generate unique identifiers: <build_id>-<unique_number>-<purpose>
    # Use unique_id if provided for stability, otherwise fallback to timestamp
    if unique_id:
        unique_number = unique_id[:6]
    else:
        import time
        unique_number = str(int(time.time()))[-6:]
    
    role_name = f"{build_id}-{unique_number}-ec2-multi-service-role"
    
    # Generate logical ID if not provided
    if logical_id is None:
        logical_id = f"IAM{build_id.replace('-', '').title()}{unique_number}EC2MultiServiceRole"
    
    print(f"  → Generated unique multi-service IAM role name: {role_name}")
    print(f"  → Generated logical ID: {logical_id}")
    
    policies = []
    
    # Add S3 policies if S3 buckets exist
    if "s3_buckets" in services and services["s3_buckets"]:
        s3_resources = []
        for bucket in services["s3_buckets"]:
            s3_resources.append(GetAtt(bucket, "Arn"))
            # Use Sub() to concatenate GetAtt with string
            s3_resources.append(Sub(f"${{BucketArn}}/*", BucketArn=GetAtt(bucket, "Arn")))
        
        policies.append(
            iam.Policy(
                PolicyName=f"{build_id}-{unique_number}-s3-access-policy",  # Unique policy name
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "s3:GetObject",
                            "s3:PutObject",
                            "s3:DeleteObject",
                            "s3:ListBucket"
                        ],
                        "Resource": s3_resources
                    }]
                }
            )
        )
    
    # Add DynamoDB policies if tables exist
    if "dynamodb_tables" in services and services["dynamodb_tables"]:
        dynamodb_resources = [GetAtt(table, "Arn") for table in services["dynamodb_tables"]]
        
        policies.append(
            iam.Policy(
                PolicyName=f"{build_id}-{unique_number}-dynamodb-access-policy",  # Unique policy name
                PolicyDocument={
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:GetItem",
                            "dynamodb:PutItem",
                            "dynamodb:UpdateItem",
                            "dynamodb:DeleteItem",
                            "dynamodb:Query",
                            "dynamodb:Scan"
                        ],
                        "Resource": dynamodb_resources
                    }]
                }
            )
        )
    
    # Create IAM Role
    role = iam.Role(
        logical_id,
        RoleName=role_name,  # Explicit role name for consistency
        AssumeRolePolicyDocument={
            "Version": "2012-10-17",
            "Statement": [{
                "Effect": "Allow",
                "Principal": {"Service": "ec2.amazonaws.com"},
                "Action": "sts:AssumeRole"
            }]
        },
        Policies=policies,
        Tags=[
            {"Key": "Name", "Value": role_name},
            {"Key": "OriginalPurpose", "Value": "ec2-multi-service-access"},
            {"Key": "ManagedBy", "Value": "CloudFormation"},
            {"Key": "BuildId", "Value": build_id}
        ]
    )
    
    t.add_resource(role)
    
    # Create Instance Profile
    instance_profile_name = f"{build_id}-{unique_number}-ec2-multi-service-profile"
    instance_profile_logical_id = f"{logical_id}InstanceProfile"
    
    instance_profile = iam.InstanceProfile(
        instance_profile_logical_id,
        InstanceProfileName=instance_profile_name,  # Explicit instance profile name
        Roles=[Ref(role)]
    )
    
    t.add_resource(instance_profile)
    
    return role, instance_profile
