"""
AWS CloudFormation Deployment Module

Simple, universal CloudFormation deployment that works with any template.
"""

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Dict, Optional


class AWSDeploymentError(Exception):
    """Custom exception for AWS deployment errors"""
    pass


class CloudFormationDeployer:
    """
    Simple CloudFormation deployment handler.
    Works with any CF template regardless of resources.
    """
    
    def __init__(self, region: str = 'us-east-1'):
        """Initialize AWS clients."""
        try:
            self.region = region
            self.cf_client = boto3.client('cloudformation', region_name=region)
            self.ec2_client = boto3.client('ec2', region_name=region)
            self.rds_client = boto3.client('rds', region_name=region)
        except NoCredentialsError:
            raise AWSDeploymentError(
                "AWS credentials not found. Please configure AWS credentials."
            )
    
    def get_default_vpc_resources(self) -> Dict[str, str]:
        """
        Find default VPC resources (VPC, Subnet, Security Group).
        
        Returns:
            Dictionary with VpcId, SubnetId, and SecurityGroupId
        """
        try:
            # Get default VPC
            vpcs = self.ec2_client.describe_vpcs(
                Filters=[{'Name': 'isDefault', 'Values': ['true']}]
            )
            
            if not vpcs['Vpcs']:
                raise AWSDeploymentError("No default VPC found")
            
            vpc_id = vpcs['Vpcs'][0]['VpcId']
            
            # Get a subnet in this VPC
            subnets = self.ec2_client.describe_subnets(
                Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
            )
            
            if not subnets['Subnets']:
                raise AWSDeploymentError(f"No subnets found in VPC {vpc_id}")
            
            subnet_id = subnets['Subnets'][0]['SubnetId']
            
            # Get default security group
            sgs = self.ec2_client.describe_security_groups(
                Filters=[
                    {'Name': 'vpc-id', 'Values': [vpc_id]},
                    {'Name': 'group-name', 'Values': ['default']}
                ]
            )
            
            if not sgs['SecurityGroups']:
                raise AWSDeploymentError(f"No security group found in VPC {vpc_id}")
            
            sg_id = sgs['SecurityGroups'][0]['GroupId']
            
            return {
                'VpcId': vpc_id,
                'SubnetId': subnet_id,
                'SecurityGroupId': sg_id
            }
            
        except ClientError as e:
            raise AWSDeploymentError(f"Failed to get VPC resources: {str(e)}")
    
    def get_or_create_db_subnet_group(self, vpc_id: str, subnet_ids: list = None) -> str:
        """
        Get existing DB Subnet Group or create a new one for RDS.
        DB Subnet Group must span at least 2 availability zones.
        
        Args:
            vpc_id: VPC ID to create subnet group in
            subnet_ids: List of subnet IDs (will auto-discover if not provided)
            
        Returns:
            DB Subnet Group name
        """
        try:
            db_subnet_group_name = f"foundry-db-subnet-group-{vpc_id}"
            
            # Check if it already exists
            try:
                response = self.rds_client.describe_db_subnet_groups(
                    DBSubnetGroupName=db_subnet_group_name
                )
                print(f"  ✓ Using existing DB Subnet Group: {db_subnet_group_name}")
                return db_subnet_group_name
            except ClientError as e:
                if e.response['Error']['Code'] != 'DBSubnetGroupNotFoundFault':
                    raise
            
            # Doesn't exist, create it
            # Get at least 2 subnets in different AZs
            if not subnet_ids:
                subnets_response = self.ec2_client.describe_subnets(
                    Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
                )
                
                if len(subnets_response['Subnets']) < 2:
                    raise AWSDeploymentError(
                        f"VPC {vpc_id} must have at least 2 subnets in different AZs for RDS"
                    )
                
                # Get subnets from different AZs
                az_subnets = {}
                for subnet in subnets_response['Subnets']:
                    az = subnet['AvailabilityZone']
                    if az not in az_subnets:
                        az_subnets[az] = subnet['SubnetId']
                
                if len(az_subnets) < 2:
                    raise AWSDeploymentError(
                        f"VPC {vpc_id} must have subnets in at least 2 different AZs for RDS"
                    )
                
                subnet_ids = list(az_subnets.values())[:2]  # Use first 2 AZs
            
            # Create DB Subnet Group
            self.rds_client.create_db_subnet_group(
                DBSubnetGroupName=db_subnet_group_name,
                DBSubnetGroupDescription=f"Foundry auto-generated DB subnet group for VPC {vpc_id}",
                SubnetIds=subnet_ids,
                Tags=[
                    {'Key': 'Name', 'Value': db_subnet_group_name},
                    {'Key': 'ManagedBy', 'Value': 'Foundry'}
                ]
            )
            
            print(f"  ✓ Created new DB Subnet Group: {db_subnet_group_name}")
            print(f"    - Subnets: {subnet_ids}")
            return db_subnet_group_name
            
        except ClientError as e:
            raise AWSDeploymentError(f"Failed to get/create DB subnet group: {str(e)}")
    
    def deploy_stack(
        self, 
        template_body: str, 
        stack_name: str,
        parameters: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Deploy a CloudFormation stack.
        
        Args:
            template_body: CloudFormation template as JSON string
            stack_name: Name for the stack
            parameters: Optional parameters (auto-discovered if not provided)
            
        Returns:
            Stack ID
        """
        try:
            # If parameters not provided, auto-discover them
            if parameters is None:
                parameters = self.get_default_vpc_resources()
            
            # Convert parameters to CloudFormation format
            cf_parameters = [
                {'ParameterKey': key, 'ParameterValue': value}
                for key, value in parameters.items()
            ]
            
            # Create the stack
            # Note: CAPABILITY_IAM is required when template creates IAM resources
            response = self.cf_client.create_stack(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=cf_parameters,
                Capabilities=['CAPABILITY_IAM'],  # Allow IAM role/policy creation
                OnFailure='ROLLBACK'
            )
            
            return response['StackId']
            
        except ClientError as e:
            error_msg = e.response['Error']['Message']
            raise AWSDeploymentError(f"Failed to create stack: {error_msg}")
    
    def get_stack_status(self, stack_name: str) -> Dict:
        """
        Get the current status of a CloudFormation stack.
        
        Args:
            stack_name: Name of the stack
            
        Returns:
            Dictionary with status and outputs
        """
        try:
            response = self.cf_client.describe_stacks(StackName=stack_name)
            stack = response['Stacks'][0]
            
            return {
                'status': stack['StackStatus'],
                'outputs': stack.get('Outputs', [])
            }
            
        except ClientError as e:
            raise AWSDeploymentError(f"Failed to get stack status: {str(e)}")
    
    def update_stack(
        self,
        stack_name: str,
        template_body: str,
        parameters: Optional[Dict[str, str]] = None
    ) -> Dict:
        """
        Update an existing CloudFormation stack using change sets.
        
        This method:
        1. Creates a change set to preview changes
        2. Returns the change set details for review
        3. Optionally executes the change set
        
        Args:
            stack_name: Name of the existing stack to update
            template_body: New CloudFormation template as JSON string
            parameters: Optional parameters (will reuse existing if not provided)
            
        Returns:
            Dictionary with change set information:
            {
                'changeSetId': str,
                'changeSetName': str,
                'changes': list,  # List of changes that will be applied
                'status': str,
                'hasChanges': bool
            }
        """
        import time
        from datetime import datetime
        
        try:
            # Generate unique change set name
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            change_set_name = f"foundry-changeset-{timestamp}"
            
            print(f"\n[Update] Creating change set '{change_set_name}'...")
            
            # Convert parameters to CloudFormation format if provided
            cf_parameters = None
            if parameters:
                cf_parameters = [
                    {'ParameterKey': key, 'ParameterValue': value}
                    for key, value in parameters.items()
                ]
            else:
                # Use existing parameter values
                cf_parameters = []
                stack_info = self.cf_client.describe_stacks(StackName=stack_name)
                for param in stack_info['Stacks'][0].get('Parameters', []):
                    cf_parameters.append({
                        'ParameterKey': param['ParameterKey'],
                        'UsePreviousValue': True
                    })
            
            # Create change set
            response = self.cf_client.create_change_set(
                StackName=stack_name,
                TemplateBody=template_body,
                Parameters=cf_parameters,
                Capabilities=['CAPABILITY_IAM'],
                ChangeSetName=change_set_name,
                Description=f"Foundry update at {timestamp}"
            )
            
            change_set_id = response['Id']
            print(f"  ✓ Change set created: {change_set_id}")
            
            # Wait for change set creation to complete
            print("  → Waiting for change set to be created...")
            waiter = self.cf_client.get_waiter('change_set_create_complete')
            
            try:
                waiter.wait(
                    ChangeSetName=change_set_name,
                    StackName=stack_name,
                    WaiterConfig={'Delay': 2, 'MaxAttempts': 30}
                )
            except Exception as waiter_error:
                # Check if it failed because there are no changes
                change_set_info = self.cf_client.describe_change_set(
                    ChangeSetName=change_set_name,
                    StackName=stack_name
                )
                
                if change_set_info['Status'] == 'FAILED':
                    status_reason = change_set_info.get('StatusReason', '')
                    if "didn't contain changes" in status_reason or "No updates" in status_reason:
                        print("  ℹ No changes detected - stack is already up to date")
                        
                        # Clean up the change set
                        self.cf_client.delete_change_set(
                            ChangeSetName=change_set_name,
                            StackName=stack_name
                        )
                        
                        return {
                            'changeSetId': change_set_id,
                            'changeSetName': change_set_name,
                            'changes': [],
                            'status': 'NO_CHANGES',
                            'hasChanges': False,
                            'message': 'Stack is already up to date - no changes required'
                        }
                    else:
                        raise AWSDeploymentError(f"Change set creation failed: {status_reason}")
                else:
                    raise waiter_error
            
            # Get change set details
            print("  → Retrieving change set details...")
            change_set_info = self.cf_client.describe_change_set(
                ChangeSetName=change_set_name,
                StackName=stack_name
            )
            
            changes = change_set_info.get('Changes', [])
            print(f"  ✓ Change set ready with {len(changes)} change(s)")
            
            # Format changes for easier reading
            formatted_changes = []
            for change in changes:
                resource_change = change.get('ResourceChange', {})
                formatted_changes.append({
                    'action': resource_change.get('Action'),  # Add, Modify, Remove, etc.
                    'logicalId': resource_change.get('LogicalResourceId'),
                    'resourceType': resource_change.get('ResourceType'),
                    'replacement': resource_change.get('Replacement', 'N/A'),  # True, False, Conditional
                    'details': resource_change.get('Details', [])
                })
                
                # Print change summary
                action = resource_change.get('Action')
                logical_id = resource_change.get('LogicalResourceId')
                resource_type = resource_change.get('ResourceType')
                replacement = resource_change.get('Replacement', 'N/A')
                
                action_symbol = {
                    'Add': '➕',
                    'Modify': '✏️',
                    'Remove': '➖',
                    'Dynamic': '🔄'
                }.get(action, '•')
                
                print(f"    {action_symbol} {action}: {logical_id} ({resource_type})")
                if replacement != 'N/A' and replacement != 'False':
                    print(f"      ⚠️  Replacement: {replacement}")
            
            return {
                'changeSetId': change_set_id,
                'changeSetName': change_set_name,
                'changes': formatted_changes,
                'status': change_set_info['Status'],
                'hasChanges': len(changes) > 0,
                'message': f'Change set created with {len(changes)} change(s)'
            }
            
        except ClientError as e:
            error_msg = e.response['Error']['Message']
            raise AWSDeploymentError(f"Failed to create change set: {error_msg}")
    
    def execute_change_set(self, stack_name: str, change_set_name: str) -> str:
        """
        Execute a change set to apply updates to the stack.
        
        Args:
            stack_name: Name of the stack
            change_set_name: Name of the change set to execute
            
        Returns:
            Stack ID
        """
        try:
            print(f"\n[Update] Executing change set '{change_set_name}'...")
            
            response = self.cf_client.execute_change_set(
                ChangeSetName=change_set_name,
                StackName=stack_name
            )
            
            print("  ✓ Change set execution initiated")
            print(f"  → Stack update in progress...")
            
            # Get stack ID
            stack_info = self.cf_client.describe_stacks(StackName=stack_name)
            stack_id = stack_info['Stacks'][0]['StackId']
            
            return stack_id
            
        except ClientError as e:
            error_msg = e.response['Error']['Message']
            raise AWSDeploymentError(f"Failed to execute change set: {error_msg}")
    
    def delete_change_set(self, stack_name: str, change_set_name: str):
        """
        Delete a change set without executing it.
        
        Args:
            stack_name: Name of the stack
            change_set_name: Name of the change set to delete
        """
        try:
            self.cf_client.delete_change_set(
                ChangeSetName=change_set_name,
                StackName=stack_name
            )
            print(f"  ✓ Change set '{change_set_name}' deleted")
            
        except ClientError as e:
            error_msg = e.response['Error']['Message']
            raise AWSDeploymentError(f"Failed to delete change set: {error_msg}")


