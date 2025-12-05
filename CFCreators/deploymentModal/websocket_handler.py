"""
WebSocket Handler for Deployment Tracking

Manages WebSocket connections and streams CloudFormation events to clients.
"""

import asyncio
import json
from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
from .event_tracker import DeploymentEventTracker
from .deployment_formatter import (
    format_resource_event,
    format_stack_complete,
    format_error_event,
    format_initial_state
)


class DeploymentWebSocketManager:
    """
    Manages WebSocket connections for real-time deployment tracking.
    Handles multiple concurrent connections to the same stack.
    """
    
    def __init__(self):
        """Initialize the WebSocket manager."""
        # Track active connections per stack
        # Format: {stack_name: {websocket1, websocket2, ...}}
        self.active_connections: dict[str, Set[WebSocket]] = {}
        
        # Track active polling tasks per stack
        # Format: {stack_name: asyncio.Task}
        self.polling_tasks: dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, stack_name: str, region: str = 'us-east-1'):
        """
        Accept a new WebSocket connection and start tracking deployment.
        
        Args:
            websocket: WebSocket connection
            stack_name: CloudFormation stack name to track
            region: AWS region
        """
        await websocket.accept()
        
        # Add to active connections
        if stack_name not in self.active_connections:
            self.active_connections[stack_name] = set()
        self.active_connections[stack_name].add(websocket)
        
        print(f"✓ WebSocket connected for stack: {stack_name} (Total: {len(self.active_connections[stack_name])})")
        
        # Start polling task if not already running
        if stack_name not in self.polling_tasks:
            task = asyncio.create_task(
                self._poll_and_broadcast(stack_name, region)
            )
            self.polling_tasks[stack_name] = task
    
    def disconnect(self, websocket: WebSocket, stack_name: str):
        """
        Remove a WebSocket connection.
        
        Args:
            websocket: WebSocket connection to remove
            stack_name: CloudFormation stack name
        """
        if stack_name in self.active_connections:
            self.active_connections[stack_name].discard(websocket)
            
            # Clean up if no more connections
            if not self.active_connections[stack_name]:
                del self.active_connections[stack_name]
                
                # Cancel polling task
                if stack_name in self.polling_tasks:
                    self.polling_tasks[stack_name].cancel()
                    del self.polling_tasks[stack_name]
                
                print(f"✓ All connections closed for stack: {stack_name}")
            else:
                print(f"✓ WebSocket disconnected from stack: {stack_name} (Remaining: {len(self.active_connections[stack_name])})")
    
    async def _poll_and_broadcast(self, stack_name: str, region: str):
        """
        Poll CloudFormation events and broadcast to all connected clients.
        
        Args:
            stack_name: CloudFormation stack name
            region: AWS region
        """
        try:
            tracker = DeploymentEventTracker(stack_name, region)
            
            print(f"🔍 Started polling CloudFormation events for: {stack_name}")
            
            # Send initial state to newly connected clients
            await self._send_initial_state(stack_name, tracker)
            
            # Poll for events until deployment completes
            while not tracker.is_deployment_complete():
                # Get new events
                new_events = tracker.get_new_events()
                
                # Broadcast each new event
                for event in new_events:
                    stack_summary = tracker.get_stack_summary()
                    progress = stack_summary['progress']
                    
                    # Format and send the event
                    formatted_event = format_resource_event(event, stack_summary, progress)
                    await self._broadcast_to_stack(stack_name, formatted_event)
                
                # Wait before next poll (3 seconds)
                await asyncio.sleep(3)
            
            # Deployment complete - send final message
            print(f"✅ Deployment complete for: {stack_name}")
            
            outputs = tracker.get_stack_outputs()
            duration = tracker.get_deployment_duration()
            
            completion_event = format_stack_complete(
                stack_name=stack_name,
                stack_status=tracker.stack_status,
                outputs=outputs,
                duration=duration
            )
            
            await self._broadcast_to_stack(stack_name, completion_event)
            
            # Keep connection open for a bit so clients can see final state
            await asyncio.sleep(2)
            
        except asyncio.CancelledError:
            print(f"🛑 Polling cancelled for stack: {stack_name}")
        except Exception as e:
            print(f"❌ Error polling stack {stack_name}: {str(e)}")
            
            # Send error to clients
            error_event = format_error_event(
                message=f"Error tracking deployment: {str(e)}"
            )
            await self._broadcast_to_stack(stack_name, error_event)
    
    async def _send_initial_state(self, stack_name: str, tracker: DeploymentEventTracker):
        """
        Send current deployment state to newly connected clients.
        
        Args:
            stack_name: CloudFormation stack name
            tracker: Event tracker instance
        """
        stack_summary = tracker.get_stack_summary()
        resources = tracker.get_all_resources()
        
        if resources:  # Only send if there's existing state
            initial_state = format_initial_state(stack_summary, resources)
            await self._broadcast_to_stack(stack_name, initial_state)
    
    async def _broadcast_to_stack(self, stack_name: str, message: dict):
        """
        Broadcast a message to all clients connected to a specific stack.
        
        Args:
            stack_name: CloudFormation stack name
            message: Dictionary to send (will be JSON serialized)
        """
        if stack_name not in self.active_connections:
            return
        
        # Create a copy of the set to avoid modification during iteration
        connections = self.active_connections[stack_name].copy()
        
        # Send to all connections
        disconnected = []
        for websocket in connections:
            try:
                await websocket.send_json(message)
            except Exception as e:
                print(f"⚠ Error sending to client: {e}")
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            self.disconnect(websocket, stack_name)


# Global instance
deployment_ws_manager = DeploymentWebSocketManager()
