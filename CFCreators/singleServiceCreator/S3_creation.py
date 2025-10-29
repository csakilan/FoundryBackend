# S3_creation.py
from typing import Dict, Any
from troposphere import Template, Ref, Output, GetAtt, Sub
import troposphere.s3 as s3
import uuid


def generate_unique_bucket_name(user_bucket_name: str = None, build_id: str = "default") -> str:
    """
    Generate a unique S3 bucket name following the pattern:
    <build_id>-<unique_number>-<user_bucket_name>
    
    Args:
        user_bucket_name: User-specified bucket name (optional)
        build_id: Build ID to prefix the bucket name
        
    Returns:
        Unique bucket name in lowercase
        
    Example:
        default-a1b2c3-my-app-storage
        prod-123-d4e5f6-user-uploads
        
    Note:
        - All parts are converted to lowercase and sanitized for S3 requirements
        - If no user_bucket_name provided, defaults to "bucket"
    """
    # Generate unique number (6 characters)
    unique_number = uuid.uuid4().hex[:6]
    
    # Sanitize and use user bucket name, or default to "bucket"
    if user_bucket_name:
        sanitized_user_name = sanitize_bucket_name_part(user_bucket_name)
    else:
        sanitized_user_name = "bucket"
    
    # Build bucket name: <build_id>-<unique_number>-<user_name>
    bucket_name = f"{build_id}-{unique_number}-{sanitized_user_name}"
    
    # Ensure it meets S3 naming requirements
    bucket_name = bucket_name.lower()
    
    # Truncate if too long (max 63 chars)
    if len(bucket_name) > 63:
        # Keep build_id and unique_number, truncate user name
        prefix = f"{build_id}-{unique_number}-"
        max_user_name_length = 63 - len(prefix)
        truncated_user_name = sanitized_user_name[:max_user_name_length]
        bucket_name = f"{prefix}{truncated_user_name}"
    
    return bucket_name


def sanitize_bucket_name_part(name: str) -> str:
    """
    Sanitize a part of the bucket name to meet S3 requirements.
    
    Args:
        name: Raw name part
        
    Returns:
        Sanitized name part (lowercase, only letters/numbers/hyphens)
    """
    # Convert to lowercase
    name = name.lower()
    
    # Replace invalid characters with hyphens
    valid_chars = []
    for char in name:
        if char.isalnum():
            valid_chars.append(char)
        elif char in ['-', '_']:
            valid_chars.append('-')
        else:
            valid_chars.append('-')
    
    # Join and remove consecutive hyphens
    name = ''.join(valid_chars)
    while '--' in name:
        name = name.replace('--', '-')
    
    return name.strip('-')


def add_s3_bucket(
    t: Template,
    node: Dict[str, Any],
    *,
    logical_id: str = None,
    build_id: str = "default",
) -> s3.Bucket:
    """
    Add an AWS::S3::Bucket to the given Template.
    Expects node['data'] with: bucketName (optional).
    
    Generates unique bucket name using pattern:
    <build_id>-<unique_number>-<userspecifiedbucketname>
    
    All security settings are hardcoded:
    - Encryption: Always enabled (AES-256)
    - Public Access: Always blocked
    - Versioning: Disabled
    - Ownership Controls: BucketOwnerEnforced (ACLs disabled)
    
    Args:
        t: CloudFormation Template object
        node: Node data from frontend JSON
        logical_id: CloudFormation logical resource ID (auto-generated if None)
        build_id: Build ID for bucket naming
        
    Returns:
        The created S3 Bucket resource
    """
    data = node["data"]
    
    # Get user-specified bucket name (optional)
    user_bucket_name = data.get("bucketName")
    
    # Generate unique bucket name using consistent pattern
    bucket_name = generate_unique_bucket_name(
        user_bucket_name=user_bucket_name,
        build_id=build_id
    )
    
    # Generate unique number for logical ID if not provided
    if logical_id is None:
        unique_number = uuid.uuid4().hex[:6]
        sanitized_user_name = sanitize_bucket_name_part(user_bucket_name) if user_bucket_name else "Bucket"
        logical_id = f"S3{build_id.replace('-', '').title()}{unique_number}{sanitized_user_name.title()}"
    
    print(f"  → Generated unique S3 bucket name: {bucket_name}")
    print(f"  → Generated logical ID: {logical_id}")
    
    # Build bucket properties
    props: Dict[str, Any] = dict(
        # Use the generated unique bucket name
        BucketName=bucket_name,
        
        # Tags for resource management
        Tags=[
            {"Key": "Name", "Value": bucket_name},
            {"Key": "OriginalName", "Value": user_bucket_name or "bucket"},
            {"Key": "ManagedBy", "Value": "CloudFormation"},
            {"Key": "BuildId", "Value": build_id},
        ],
        
        # Encryption configuration (always enabled)
        BucketEncryption=s3.BucketEncryption(
            ServerSideEncryptionConfiguration=[
                s3.ServerSideEncryptionRule(
                    ServerSideEncryptionByDefault=s3.ServerSideEncryptionByDefault(
                        SSEAlgorithm="AES256"
                    )
                )
            ]
        ),
        
        # Public access block configuration (always block public access)
        PublicAccessBlockConfiguration=s3.PublicAccessBlockConfiguration(
            BlockPublicAcls=True,
            BlockPublicPolicy=True,
            IgnorePublicAcls=True,
            RestrictPublicBuckets=True
        ),
        
        # Ownership controls (disable ACLs - AWS best practice)
        OwnershipControls=s3.OwnershipControls(
            Rules=[
                s3.OwnershipControlsRule(
                    ObjectOwnership="BucketOwnerEnforced"
                )
            ]
        )
    )
    
    # Create the S3 bucket
    bucket = s3.Bucket(logical_id, **props)
    t.add_resource(bucket)
    
    # Add helpful outputs
    t.add_output([
        Output(
            f"{logical_id}Name",
            Value=Ref(bucket),
            Description="Generated unique bucket name"
        ),
        Output(
            f"{logical_id}OriginalName",
            Value=user_bucket_name or "bucket",
            Description="User's original bucket name"
        ),
        Output(
            f"{logical_id}Arn",
            Value=GetAtt(bucket, "Arn"),
            Description="ARN of the S3 bucket"
        ),
        Output(
            f"{logical_id}DomainName",
            Value=GetAtt(bucket, "DomainName"),
            Description="Domain name of the S3 bucket"
        )
    ])
    
    return bucket
