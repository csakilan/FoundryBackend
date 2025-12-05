"""
Deployment Event Formatter

Formats CloudFormation events into JSON structures for WebSocket transmission.
"""

from typing import Dict, List, Optional
from datetime import datetime


def format_resource_event(event: Dict, stack_summary: Dict, progress: int) -> Dict:
    """
    Format a CloudFormation resource event for WebSocket transmission.
    
    Args:
        event: Raw CloudFormation event from AWS
        stack_summary: Current stack summary with counts
        progress: Overall progress percentage (0-100)
        
    Returns:
        Formatted event dictionary ready for JSON serialization
    """
    timestamp = event.get('Timestamp')
    if isinstance(timestamp, datetime):
        timestamp = timestamp.isoformat()
    
    return {
        'type': 'resource_update',
        'timestamp': timestamp,
        'resource': {
            'logicalId': event.get('LogicalResourceId', ''),
            'type': event.get('ResourceType', ''),
            'status': event.get('ResourceStatus', ''),
            'statusReason': event.get('ResourceStatusReason', ''),
            'physicalId': event.get('PhysicalResourceId', ''),
            'progress': progress
        },
        'stack': stack_summary
    }


def format_stack_complete(
    stack_name: str,
    stack_status: str,
    outputs: List[Dict],
    duration: Optional[str] = None
) -> Dict:
    """
    Format a stack completion event.
    
    Args:
        stack_name: Name of the CloudFormation stack
        stack_status: Final status (CREATE_COMPLETE, CREATE_FAILED, etc.)
        outputs: List of stack outputs
        duration: Human-readable duration string
        
    Returns:
        Formatted completion event dictionary
    """
    return {
        'type': 'stack_complete',
        'timestamp': datetime.now().isoformat(),
        'stack': {
            'name': stack_name,
            'status': stack_status,
            'outputs': outputs
        },
        'duration': duration or 'N/A'
    }


def format_error_event(
    message: str,
    resource_logical_id: Optional[str] = None,
    resource_type: Optional[str] = None
) -> Dict:
    """
    Format an error event.
    
    Args:
        message: Error message
        resource_logical_id: Logical ID of failed resource (optional)
        resource_type: AWS resource type (optional)
        
    Returns:
        Formatted error event dictionary
    """
    event = {
        'type': 'error',
        'timestamp': datetime.now().isoformat(),
        'message': message
    }
    
    if resource_logical_id and resource_type:
        event['resource'] = {
            'logicalId': resource_logical_id,
            'type': resource_type
        }
    
    return event


def format_initial_state(stack_summary: Dict, resources: List[Dict]) -> Dict:
    """
    Format the initial state message sent when client connects.
    Useful if deployment already started before WebSocket connection.
    
    Args:
        stack_summary: Current stack summary
        resources: List of all current resource statuses
        
    Returns:
        Formatted initial state dictionary
    """
    # Convert datetime objects to ISO strings
    formatted_resources = []
    for resource in resources:
        formatted_resource = resource.copy()
        if isinstance(formatted_resource.get('timestamp'), datetime):
            formatted_resource['timestamp'] = formatted_resource['timestamp'].isoformat()
        formatted_resources.append(formatted_resource)
    
    return {
        'type': 'initial_state',
        'timestamp': datetime.now().isoformat(),
        'stack': stack_summary,
        'resources': formatted_resources
    }
