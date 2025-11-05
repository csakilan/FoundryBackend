# RDS_creation.py
from typing import Dict, Any
from troposphere import Template, Ref, Tags, Output, GetAtt, Sub
import troposphere.rds as rds


def sanitize_rds_identifier(identifier: str) -> str:
    """
    Sanitize a string to meet RDS identifier requirements.
    
    RDS identifiers must:
    - Be 1-63 characters long
    - Contain only lowercase letters, numbers, and hyphens
    - Start with a letter
    - Not end with a hyphen or contain two consecutive hyphens
    
    Args:
        identifier: Raw identifier string
        
    Returns:
        Sanitized identifier that meets RDS requirements
    """
    # Convert to lowercase
    identifier = identifier.lower()
    
    # Replace invalid characters with hyphens
    valid_chars = []
    for char in identifier:
        if char.isalnum():
            valid_chars.append(char)
        elif char in ['-', '_', ' ']:
            valid_chars.append('-')
        else:
            valid_chars.append('-')
    
    # Join and remove consecutive hyphens
    identifier = ''.join(valid_chars)
    while '--' in identifier:
        identifier = identifier.replace('--', '-')
    
    # Remove leading/trailing hyphens
    identifier = identifier.strip('-')
    
    # Ensure it starts with a letter
    if identifier and not identifier[0].isalpha():
        identifier = 'db' + identifier
    
    # Ensure it's not empty and not too long
    if not identifier:
        identifier = 'database'
    elif len(identifier) > 63:
        identifier = identifier[:63].rstrip('-')
    
    return identifier

def add_rds_instance(
    t: Template,
    node: Dict[str, Any],
    subnet_group_param,
    sg_param,
    *,
    logical_id: str = None,
    build_id: str = "default",
) -> rds.DBInstance:
    """
    Add an AWS::RDS::DBInstance to the given Template.
    Expects node['data'] with: dbName, engine, masterUsername, masterUserPassword.
    
    All other settings (dbInstanceClass, storage, multiAZ, encryption, etc.) are hardcoded
    based on the simplified RDS configuration.
    
    Args:
        t: Troposphere Template object
        node: Node dictionary from ReactFlow canvas
        subnet_group_param: Parameter reference for DB subnet group
        sg_param: Parameter reference for VPC security group
        logical_id: CloudFormation logical resource ID (auto-generated if None)
        build_id: Build ID to prefix the database instance identifier
    
    Returns:
        The created RDS DBInstance resource
    """
    data = node["data"]
    
    # Generate unique instance identifier: <build_id>-<unique_number>-<user_dbname>
    # Use node ID for stability across template generations
    unique_number = sanitize_rds_identifier(node['id'][:6])  # First 6 characters of node ID
    user_db_name = sanitize_rds_identifier(data['dbName'])  # Sanitize user name
    build_id_clean = sanitize_rds_identifier(build_id)  # Sanitize build_id
    db_instance_identifier = f"{build_id_clean}-{unique_number}-{user_db_name}"
    
    # Generate logical ID if not provided
    if logical_id is None:
        # CloudFormation logical IDs can't have hyphens, use CamelCase
        logical_id = f"RDS{build_id.replace('-', '').title()}{unique_number.replace('-', '')}{user_db_name.replace('-', '').title()}"
    
    print(f"  → Generated unique RDS instance identifier: {db_instance_identifier}")
    print(f"  → Generated logical ID: {logical_id}")
    
    # Build properties with hardcoded defaults
    props: Dict[str, Any] = dict(
        # User-configurable fields
        DBName=data["dbName"],
        Engine=data["engine"],  # postgres or mysql
        MasterUsername=data["masterUsername"],
        MasterUserPassword=data["masterUserPassword"],
        
        # Auto-generated identifier
        DBInstanceIdentifier=db_instance_identifier,
        
        # Hardcoded instance configuration
        DBInstanceClass="db.t4g.micro",  # Graviton2, burstable performance
        AllocatedStorage=20,  # 20 GB minimum
        StorageType="gp3",  # General Purpose SSD v3
        StorageEncrypted=True,  # Always encrypted for security
        
        # Hardcoded availability and access settings
        MultiAZ=False,  # Single-AZ for cost optimization
        PubliclyAccessible=False,  # Private only (security best practice)
        
        # Hardcoded backup settings
        BackupRetentionPeriod=7,  # 7 days automated backups
        
        # Hardcoded protection settings
        DeletionProtection=False,  # Allow deletion by default
        
        # Networking from parameters
        DBSubnetGroupName=Ref(subnet_group_param),
        VPCSecurityGroups=[Ref(sg_param)],
        
        # Tags for resource management
        Tags=Tags(
            Name=db_instance_identifier,
            OriginalName=data['dbName'],
            ManagedBy="CloudFormation",
            Engine=data["engine"],
            BuildId=build_id,
        ),
    )
    
    # Engine version: use latest stable (AWS will auto-select)
    # Note: We don't specify EngineVersion to let AWS use the latest stable release
    
    # Create the RDS instance
    instance = rds.DBInstance(logical_id, **props)
    t.add_resource(instance)
    
    # Helpful outputs (namespaced to avoid collisions with multiple RDS instances)
    t.add_output([
        Output(
            f"{logical_id}Endpoint",
            Description=f"Connection endpoint for {db_instance_identifier}",
            Value=GetAtt(instance, "Endpoint.Address")
        ),
        Output(
            f"{logical_id}Port",
            Description=f"Port number for {db_instance_identifier}",
            Value=GetAtt(instance, "Endpoint.Port")
        ),
        Output(
            f"{logical_id}Arn",
            Description=f"ARN of {db_instance_identifier}",
            Value=Sub(f"arn:aws:rds:${{AWS::Region}}:${{AWS::AccountId}}:db:${{{logical_id}}}")
        ),
        Output(
            f"{logical_id}InstanceId",
            Description=f"Generated DB Instance Identifier",
            Value=Ref(instance)
        ),
        Output(
            f"{logical_id}OriginalName",
            Description=f"User's original database name",
            Value=data['dbName']
        ),
    ])
    
    return instance
