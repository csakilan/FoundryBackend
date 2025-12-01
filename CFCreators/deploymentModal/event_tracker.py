"""
CloudFormation Event Tracker

Polls CloudFormation stack events and tracks resource creation/update progress.
"""

import boto3
from botocore.exceptions import ClientError
from typing import Dict, List, Optional, Set
from datetime import datetime
import time


class DeploymentEventTracker:
    """
    Tracks CloudFormation stack deployment events in real-time.
    Polls stack events and provides structured updates.
    """
    
    def __init__(self, stack_name: str, region: str = 'us-east-1'):
        """
        Initialize event tracker for a specific stack.
        
        Args:
            stack_name: CloudFormation stack name to track
            region: AWS region (default: us-east-1)
        """
        self.stack_name = stack_name
        self.region = region
        self.cf_client = boto3.client('cloudformation', region_name=region)
        
        # Track which events we've already seen (by event ID)
        self.seen_event_ids: Set[str] = set()
        
        # Cache of resource statuses
        self.resource_statuses: Dict[str, Dict] = {}
        
        # Stack-level tracking
        self.stack_status: Optional[str] = None
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
    
    def get_new_events(self) -> List[Dict]:
        """
        Fetch new stack events that haven't been seen before.
        
        Returns:
            List of new event dictionaries, ordered chronologically (oldest first)
        """
        try:
            # Fetch stack events (AWS returns newest first)
            response = self.cf_client.describe_stack_events(StackName=self.stack_name)
            all_events = response['StackEvents']
            
            # Filter out events we've already seen
            new_events = []
            for event in all_events:
                event_id = event['EventId']
                if event_id not in self.seen_event_ids:
                    self.seen_event_ids.add(event_id)
                    new_events.append(event)
            
            # Reverse to get chronological order (oldest to newest)
            new_events.reverse()
            
            # Update resource cache
            for event in new_events:
                self._update_resource_status(event)
            
            return new_events
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == 'ValidationError':
                # Stack might not exist yet or was deleted
                return []
            raise
    
    def _update_resource_status(self, event: Dict):
        """
        Update internal resource status cache from an event.
        
        Args:
            event: CloudFormation event dictionary
        """
        logical_id = event.get('LogicalResourceId')
        resource_type = event.get('ResourceType')
        status = event.get('ResourceStatus')
        
        if logical_id and resource_type:
            self.resource_statuses[logical_id] = {
                'logicalId': logical_id,
                'type': resource_type,
                'status': status,
                'statusReason': event.get('ResourceStatusReason', ''),
                'physicalId': event.get('PhysicalResourceId', ''),
                'timestamp': event.get('Timestamp')
            }
            
            # Track stack-level status
            if logical_id == self.stack_name and resource_type == 'AWS::CloudFormation::Stack':
                self.stack_status = status
                
                # Track start time
                if status.endswith('IN_PROGRESS') and self.start_time is None:
                    self.start_time = event.get('Timestamp')
                
                # Track end time
                if self._is_terminal_status(status):
                    self.end_time = event.get('Timestamp')
    
    def get_stack_summary(self) -> Dict:
        """
        Get summary of current stack deployment state.
        
        Returns:
            Dictionary with stack status, resource counts, and progress
        """
        total_resources = len(self.resource_statuses)
        
        # Count resources by status
        completed = 0
        in_progress = 0
        failed = 0
        updated = 0
        
        for resource in self.resource_statuses.values():
            status = resource['status']
            
            if status.endswith('_COMPLETE'):
                completed += 1
                # Count UPDATE_COMPLETE separately
                if status.startswith('UPDATE'):
                    updated += 1
            elif status.endswith('_IN_PROGRESS'):
                in_progress += 1
            elif status.endswith('_FAILED'):
                failed += 1
        
        # Calculate progress percentage
        progress = 0
        if total_resources > 0:
            # Count completed and failed as "done"
            done_count = completed + failed
            progress = int((done_count / total_resources) * 100)
        
        return {
            'name': self.stack_name,
            'status': self.stack_status or 'UNKNOWN',
            'totalResources': total_resources,
            'completedResources': completed,
            'updatedResources': updated,
            'inProgressResources': in_progress,
            'failedResources': failed,
            'progress': progress
        }
    
    def get_all_resources(self) -> List[Dict]:
        """
        Get current status of all tracked resources.
        
        Returns:
            List of resource status dictionaries
        """
        return list(self.resource_statuses.values())
    
    def is_deployment_complete(self) -> bool:
        """
        Check if the stack deployment has reached a terminal state.
        
        Returns:
            True if deployment is complete (success or failure), False otherwise
        """
        if not self.stack_status:
            return False
        
        return self._is_terminal_status(self.stack_status)
    
    def _is_terminal_status(self, status: str) -> bool:
        """
        Check if a status is terminal (deployment finished).
        
        Args:
            status: CloudFormation status string
            
        Returns:
            True if status is terminal, False otherwise
        """
        terminal_statuses = [
            'CREATE_COMPLETE',
            'CREATE_FAILED',
            'UPDATE_COMPLETE',
            'UPDATE_FAILED',
            'DELETE_COMPLETE',
            'DELETE_FAILED',
            'ROLLBACK_COMPLETE',
            'ROLLBACK_FAILED',
            'UPDATE_ROLLBACK_COMPLETE',
            'UPDATE_ROLLBACK_FAILED'
        ]
        return status in terminal_statuses
    
    def get_stack_outputs(self) -> List[Dict]:
        """
        Get CloudFormation stack outputs (when deployment is complete).
        
        Returns:
            List of output dictionaries with keys 'key', 'value', 'description'
        """
        try:
            response = self.cf_client.describe_stacks(StackName=self.stack_name)
            stack = response['Stacks'][0]
            
            outputs = []
            for output in stack.get('Outputs', []):
                outputs.append({
                    'key': output.get('OutputKey', ''),
                    'value': output.get('OutputValue', ''),
                    'description': output.get('Description', '')
                })
            
            return outputs
            
        except ClientError:
            return []
    
    def get_deployment_duration(self) -> Optional[str]:
        """
        Calculate deployment duration in human-readable format.
        
        Returns:
            Duration string like "4m 15s" or None if not available
        """
        if not self.start_time:
            return None
        
        end = self.end_time or datetime.now(self.start_time.tzinfo)
        duration = end - self.start_time
        
        total_seconds = int(duration.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        
        if minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
