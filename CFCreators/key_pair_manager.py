"""
EC2 Key Pair Management

Handles automatic creation and retrieval of EC2 key pairs for SSH access.
"""

import boto3
from botocore.exceptions import ClientError
from typing import Dict, Optional, Tuple
import json


class KeyPairManager:
    """
    Manages EC2 key pair creation and retrieval.
    Creates unique key pairs per EC2 instance for secure SSH access.
    """
    
    def __init__(self, region: str = 'us-east-1'):
        """
        Initialize EC2 client for key pair operations.
        
        Args:
            region: AWS region (default: us-east-1)
        """
        self.region = region
        self.ec2_client = boto3.client('ec2', region_name=region)
    
    def create_key_pair(self, key_name: str) -> Dict[str, str]:
        """
        Create a new EC2 key pair.
        
        Args:
            key_name: Name for the key pair (must be unique in region)
            
        Returns:
            Dictionary with:
            - keyName: The key pair name
            - keyMaterial: The private key (PEM format) - STORE THIS SECURELY
            - keyFingerprint: The key fingerprint
            
        Raises:
            ClientError: If key pair already exists or creation fails
        """
        try:
            response = self.ec2_client.create_key_pair(KeyName=key_name)
            
            return {
                'keyName': response['KeyName'],
                'keyMaterial': response['KeyMaterial'],  # Private key - only returned once!
                'keyFingerprint': response['KeyFingerprint'],
                'keyPairId': response.get('KeyPairId', '')
            }
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'InvalidKeyPair.Duplicate':
                # Key pair already exists, return info without private key
                return {
                    'keyName': key_name,
                    'keyMaterial': None,  # Can't retrieve existing private key
                    'error': 'Key pair already exists. Private key cannot be retrieved.',
                    'exists': True
                }
            else:
                raise
    
    def delete_key_pair(self, key_name: str) -> bool:
        """
        Delete an EC2 key pair.
        
        Args:
            key_name: Name of the key pair to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            self.ec2_client.delete_key_pair(KeyName=key_name)
            return True
        except ClientError:
            return False
    
    def key_pair_exists(self, key_name: str) -> bool:
        """
        Check if a key pair exists.
        
        Args:
            key_name: Name of the key pair to check
            
        Returns:
            True if exists, False otherwise
        """
        try:
            response = self.ec2_client.describe_key_pairs(KeyNames=[key_name])
            return len(response['KeyPairs']) > 0
        except ClientError as e:
            if e.response['Error']['Code'] == 'InvalidKeyPair.NotFound':
                return False
            raise
    
    def get_or_create_key_pair(self, key_name: str) -> Dict[str, str]:
        """
        Get existing key pair info or create a new one.
        
        Args:
            key_name: Name for the key pair
            
        Returns:
            Dictionary with key pair information
            Note: keyMaterial (private key) is only available for newly created keys
        """
        if self.key_pair_exists(key_name):
            # Key exists - we can't retrieve the private key
            try:
                response = self.ec2_client.describe_key_pairs(KeyNames=[key_name])
                key_pair = response['KeyPairs'][0]
                
                return {
                    'keyName': key_pair['KeyName'],
                    'keyMaterial': None,  # Can't retrieve existing private key
                    'keyFingerprint': key_pair.get('KeyFingerprint', ''),
                    'keyPairId': key_pair.get('KeyPairId', ''),
                    'exists': True,
                    'warning': 'Key pair already exists. Private key was not re-generated.'
                }
            except ClientError:
                pass
        
        # Create new key pair
        return self.create_key_pair(key_name)
    
    def generate_key_name(self, build_id: str, instance_name: str) -> str:
        """
        Generate a unique key pair name for an EC2 instance.
        
        Args:
            build_id: Build ID
            instance_name: EC2 instance name
            
        Returns:
            Key pair name in format: {build_id}-{instance_name}-key
        """
        # Sanitize the name (key pair names have restrictions)
        safe_build_id = build_id.replace(':', '-').replace('_', '-')
        safe_instance_name = instance_name.replace(':', '-').replace('_', '-')
        
        key_name = f"{safe_build_id}-{safe_instance_name}-key"
        
        # Key pair names are limited to 255 characters
        if len(key_name) > 255:
            key_name = key_name[:255]
        
        return key_name


def create_key_pairs_for_deployment(canvas_data: dict, build_id: str, region: str = 'us-east-1') -> Dict[str, Dict]:
    """
    Create key pairs for all EC2 instances in a deployment.
    
    Args:
        canvas_data: Canvas JSON with nodes
        build_id: Build ID for naming
        region: AWS region
        
    Returns:
        Dictionary mapping instance names to key pair info:
        {
            "instance-name": {
                "keyName": "build-123-instance-key",
                "keyMaterial": "-----BEGIN RSA PRIVATE KEY-----...",
                "keyFingerprint": "...",
                "instanceLogicalId": "EC2Instance1"
            }
        }
    """
    manager = KeyPairManager(region)
    key_pairs = {}
    
    # Find all EC2 nodes
    for node in canvas_data.get('nodes', []):
        if node.get('type') == 'EC2':
            node_id = node.get('id')
            node_data = node.get('data', {})
            instance_name = node_data.get('name', 'instance')
            
            # Generate unique key name
            unique_number = node_id[:6].replace('-', '').replace(':', '')
            sanitized_name = instance_name.replace(' ', '-').replace(':', '-')
            key_name = f"{build_id}-{unique_number}-{sanitized_name}-key"
            
            # Create key pair
            print(f"Creating key pair for EC2 instance: {instance_name}")
            key_pair_info = manager.create_key_pair(key_name)
            
            # Store with instance information
            key_pairs[instance_name] = {
                **key_pair_info,
                'instanceNodeId': node_id,
                'instanceName': instance_name
            }
            
            print(f"  ✓ Key pair created: {key_name}")
    
    return key_pairs


def cleanup_key_pairs_for_stack(stack_name: str, region: str = 'us-east-1') -> int:
    """
    Clean up key pairs associated with a CloudFormation stack.
    
    Args:
        stack_name: CloudFormation stack name
        region: AWS region
        
    Returns:
        Number of key pairs deleted
    """
    manager = KeyPairManager(region)
    ec2_client = boto3.client('ec2', region_name=region)
    
    try:
        # Get all key pairs
        response = ec2_client.describe_key_pairs()
        deleted_count = 0
        
        # Delete key pairs that match the stack/build pattern
        for key_pair in response['KeyPairs']:
            key_name = key_pair['KeyName']
            
            # Check if this key belongs to the stack
            if stack_name in key_name or key_name.startswith(f"{stack_name}-"):
                if manager.delete_key_pair(key_name):
                    print(f"  ✓ Deleted key pair: {key_name}")
                    deleted_count += 1
        
        return deleted_count
        
    except ClientError as e:
        print(f"Error cleaning up key pairs: {e}")
        return 0
