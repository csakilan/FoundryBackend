# DynamoDB_creation.py
from typing import Dict, Any, List
from troposphere import Template, Ref, Tags, Output, GetAtt
import troposphere.dynamodb as dynamodb

def add_dynamodb_table(
    t: Template,
    node: Dict[str, Any],
    *,
    logical_id: str = None,
    build_id: str = "default",
) -> dynamodb.Table:
    """
    Add an AWS::DynamoDB::Table to the given Template.
    Expects node['data'] with: tableName, partitionKey, partitionKeyType, sortKey (optional), sortKeyType.
    
    All other settings (billing mode, encryption, PITR, etc.) are hardcoded
    based on the simplified DynamoDB configuration.
    
    Args:
        t: Troposphere Template object
        node: Node dictionary from ReactFlow canvas
        logical_id: CloudFormation logical resource ID (auto-generated if None)
        build_id: Build ID to prefix the table name
    
    Returns:
        The created DynamoDB Table resource
    """
    data = node["data"]
    
    # Generate unique table name: <build_id>-<unique_number>-<user_tablename>
    # Use node ID for stability across template generations
    unique_number = node['id'][:6]  # First 6 characters of node ID
    user_table_name = data['tableName'].replace(" ", "").replace("_", "")  # Sanitize user name
    table_name = f"{build_id}-{unique_number}-{user_table_name}"
    
    # Generate logical ID if not provided
    if logical_id is None:
        # CloudFormation logical IDs can't have hyphens, use CamelCase
        logical_id = f"DynamoDB{build_id.replace('-', '').title()}{unique_number}{user_table_name}"
    
    print(f"  → Generated unique DynamoDB table name: {table_name}")
    print(f"  → Generated logical ID: {logical_id}")
    
    # Build attribute definitions (required for key schema)
    attribute_definitions = [
        dynamodb.AttributeDefinition(
            AttributeName=data["partitionKey"],
            AttributeType=data["partitionKeyType"]  # S or N
        )
    ]
    
    # Build key schema (partition key is always required)
    key_schema = [
        dynamodb.KeySchema(
            AttributeName=data["partitionKey"],
            KeyType="HASH"  # Partition key
        )
    ]
    
    # Add sort key if provided
    if data.get("sortKey") and data["sortKey"].strip():
        attribute_definitions.append(
            dynamodb.AttributeDefinition(
                AttributeName=data["sortKey"],
                AttributeType=data["sortKeyType"]  # S or N
            )
        )
        key_schema.append(
            dynamodb.KeySchema(
                AttributeName=data["sortKey"],
                KeyType="RANGE"  # Sort key
            )
        )
    
    # Build table properties with hardcoded defaults
    props: Dict[str, Any] = dict(
        # User-configurable fields
        TableName=table_name,
        AttributeDefinitions=attribute_definitions,
        KeySchema=key_schema,
        
        # Hardcoded billing mode (on-demand, no capacity planning)
        BillingMode="PAY_PER_REQUEST",
        
        # Hardcoded encryption settings (AWS-owned key, no additional cost)
        SSESpecification=dynamodb.SSESpecification(
            SSEEnabled=True
            # Note: No SSEType needed for AWS-owned keys (default encryption)
            # Use SSEType="KMS" only if using customer-managed KMS keys
        ),
        
        # Hardcoded backup settings (35-day point-in-time recovery)
        PointInTimeRecoverySpecification=dynamodb.PointInTimeRecoverySpecification(
            PointInTimeRecoveryEnabled=True
        ),
        
        # Hardcoded deletion protection (disabled by default)
        DeletionProtectionEnabled=False,
        
        # Tags for resource management
        Tags=Tags(
            Name=table_name,
            OriginalName=data['tableName'],
            ManagedBy="CloudFormation",
            BuildId=build_id,
        ),
    )
    
    # Note: DynamoDB Streams and TTL are NOT configured by default
    # These can be enabled later via AWS Console or API if needed:
    # - StreamSpecification: For change data capture (CDC) and Lambda triggers
    # - TimeToLiveSpecification: For automatic item expiration
    
    # Create the DynamoDB table
    table = dynamodb.Table(logical_id, **props)
    t.add_resource(table)
    
    # Helpful outputs (namespaced to avoid collisions with multiple tables)
    outputs: List[Output] = [
        Output(
            f"{logical_id}Name",
            Description=f"Generated unique table name",
            Value=Ref(table)
        ),
        Output(
            f"{logical_id}OriginalName",
            Description=f"User's original table name",
            Value=data['tableName']
        ),
        Output(
            f"{logical_id}Arn",
            Description=f"ARN of the DynamoDB table",
            Value=GetAtt(table, "Arn")
        ),
    ]
    
    # Add stream ARN output only if streams are enabled (currently not supported)
    # If streams are added in future, uncomment:
    # if props.get("StreamSpecification"):
    #     outputs.append(
    #         Output(
    #             f"{logical_id}StreamArn",
    #             Description=f"ARN of the DynamoDB stream",
    #             Value=GetAtt(table, "StreamArn")
    #         )
    #     )
    
    t.add_output(outputs)
    
    return table
