# Live CloudFormation Tracking - Exact Connection Flow

## High-Level Architecture

```
┌─────────────┐         ┌──────────────────────┐         ┌──────────────┐
│   Frontend  │         │   FastAPI Backend    │         │     AWS      │
│  (Browser)  │◄───────►│  (WebSocket Server)  │◄───────►│ CloudForm.   │
│             │         │                      │         │              │
└─────────────┘         └──────────────────────┘         └──────────────┘
      ▲                           ▲                             ▲
      │                           │                             │
      │ WebSocket                 │ Polling Task                │ describe_stack_events
      │ Connection                │ (Every 3 sec)              │ API Call
      │ to live                   │                             │
      │ updates                   │ Formatters                  │
      │                           │ Broadcast                   │
      └───────────────────────────────────────────────────────┘
           Real-time deployment tracking
```

---

## Exact Step-by-Step Connection Flow

### **Phase 1: Frontend Initiates Connection**

```
Frontend (Browser)
    │
    ├─ User deploys infrastructure
    │
    └─► API Call: POST /canvas/deploy
        Response: {
          stackName: "foundry-stack-12345678",
          keyPairs: {...},
          ...
        }
```

### **Phase 2: Frontend Opens WebSocket**

```javascript
// Frontend code
const socket = new WebSocket(
  `ws://localhost:8000/canvas/deploy/track/foundry-stack-12345678`
);

socket.onmessage = (event) => {
  const update = JSON.parse(event.data);
  // Update UI with live status
};
```

### **Phase 3: Backend Accepts WebSocket**

```
1. WebSocket arrives at: /canvas/deploy/track/{stack_name}
   
   @router.websocket("/deploy/track/{stack_name}")
   async def track_deployment(websocket: WebSocket, stack_name: str):
       await deployment_ws_manager.connect(websocket, stack_name, region)

2. WebSocketManager.connect() called
   ├─ await websocket.accept()  ← Accept the connection
   └─ Start polling task if not already running
```

### **Phase 4: Polling Task Starts**

```python
async def _poll_and_broadcast(stack_name, region):
    # Create tracker for this specific stack
    tracker = DeploymentEventTracker(stack_name, region)
    
    # Keep polling until deployment finishes
    while not tracker.is_deployment_complete():
        
        # EVERY 3 SECONDS:
        new_events = tracker.get_new_events()
        
        for event in new_events:
            # Format event for frontend
            formatted = format_resource_event(event, ...)
            
            # Send to ALL connected clients for this stack
            await self._broadcast_to_stack(stack_name, formatted)
        
        await asyncio.sleep(3)  # Wait 3 seconds, then poll again
```

---

## How Events Are Polled from AWS

### **The Core: `DeploymentEventTracker.get_new_events()`**

```python
def get_new_events(self) -> List[Dict]:
    """
    Called every 3 seconds by the polling task.
    
    Flow:
    1. Call AWS CloudFormation API
    2. Get all stack events
    3. Filter out duplicates (track by EventId)
    4. Return only NEW events
    """
    
    # STEP 1: Call AWS API
    response = self.cf_client.describe_stack_events(
        StackName=self.stack_name
    )
    # AWS returns newest events FIRST
    all_events = response['StackEvents']
    
    # STEP 2: Filter duplicates
    new_events = []
    for event in all_events:
        event_id = event['EventId']
        
        # Have we seen this event before?
        if event_id not in self.seen_event_ids:
            self.seen_event_ids.add(event_id)  # Remember it
            new_events.append(event)  # Add to new list
    
    # STEP 3: Return in chronological order (oldest → newest)
    new_events.reverse()
    return new_events
```

### **What Does AWS Return?**

CloudFormation provides events like:

```json
{
  "EventId": "12345-67890-abcdef",
  "LogicalResourceId": "MyEC2Instance",
  "ResourceType": "AWS::EC2::Instance",
  "ResourceStatus": "CREATE_IN_PROGRESS",
  "Timestamp": "2025-11-15T10:30:45Z",
  "ResourceStatusReason": "",
  "PhysicalResourceId": "i-1234567890abcdef"
}
```

---

## Event Flow Diagram

```
AWS CloudFormation                   Backend Event Tracker          WebSocket Clients
(Every 3 seconds)                    (Polling Task)                 (Frontend Browser)
       │                                    │                              │
       │                                    │                              │
  ┌────▼─────────────────┐                │                              │
  │ describe_stack_events │                │                              │
  │ (get latest events)   │                │                              │
  └────┬─────────────────┘                │                              │
       │                                    │                              │
       ├─ EC2 CREATE_IN_PROGRESS           │                              │
       ├─ EC2 CREATE_COMPLETE              │                              │
       ├─ S3 CREATE_IN_PROGRESS            │                              │
       ├─ S3 CREATE_COMPLETE               │                              │
       └─ Stack CREATE_IN_PROGRESS         │                              │
                                            │                              │
                    ┌───────────────────────┤                              │
                    │                       ▼                              │
                    │    get_new_events()   │                              │
                    │    (filter dups)      │                              │
                    │                       │                              │
                    │    Each event enters: │                              │
                    │    - _update_resource │                              │
                    │    - format_resource_ │                              │
                    │      event()          │                              │
                    │                       │                              │
                    │    Calculate:         │                              │
                    │    - Progress %       │                              │
                    │    - Resource counts  │                              │
                    │    - Status summary   │                              │
                    │                       │                              │
                    └───────────────────────┤                              │
                                            │                              │
                                ┌───────────┤                              │
                                │           ▼                              │
                                │  format_resource_event()                │
                                │                                          │
                                │  Returns JSON:                          │
                                │  {                                      │
                                │    type: "resource_update",            │
                                │    resource: {                         │
                                │      logicalId: "MyEC2Instance",       │
                                │      status: "CREATE_IN_PROGRESS",     │
                                │      progress: 33                      │
                                │    },                                  │
                                │    stack: {                            │
                                │      totalResources: 3,                │
                                │      completedResources: 1,            │
                                │      progress: 33                      │
                                │    }                                   │
                                │  }                                      │
                                │                                          │
                    ┌───────────┤                                          │
                    │           ▼                                          │
                    │  _broadcast_to_stack()                             │
                    │  (send to ALL connected clients)                   │
                    │                                          ┌──────────┤
                    │                                          │          ▼
                    │                                          │   socket.onmessage()
                    │                                          │   (Update UI)
                    │                                          │   - Show EC2 creating
                    │                                          │   - Update progress bar
                    │                                          │   - Mark resource done
                    └──────────────────────────────────────────┘
```

---

## Key Components & Their Roles

### **1. DeploymentEventTracker**
```python
tracker = DeploymentEventTracker(stack_name="foundry-stack-12345678", region="us-east-1")

# Every 3 seconds, calls:
new_events = tracker.get_new_events()

# AWS API Call Details:
# - Method: describe_stack_events
# - Parameters: StackName, limit to last 50 events
# - Response: List of all stack and resource events
# - Rate: Effectively unlimited (AWS charges per request)
```

**What it tracks internally:**
```python
self.seen_event_ids = set()  # Never send same event twice
self.resource_statuses = {}  # Current status of each resource
self.stack_status = None     # Overall stack state
self.start_time = None       # When deployment started
self.end_time = None         # When deployment finished
```

### **2. DeploymentWebSocketManager**
```python
manager = DeploymentWebSocketManager()

# Manages connections:
manager.active_connections = {
    "foundry-stack-12345678": {
        <websocket1>,  # Client 1 browser
        <websocket2>,  # Client 2 browser
        ...
    }
}

# Manages polling:
manager.polling_tasks = {
    "foundry-stack-12345678": <asyncio.Task>  # Polling coroutine
}
```

**Key methods:**
- `connect()` - Accept new WebSocket, start polling if needed
- `disconnect()` - Remove client, stop polling if no more clients
- `_poll_and_broadcast()` - The main polling loop
- `_broadcast_to_stack()` - Send to all clients for a stack

### **3. Event Formatters**
```python
# Input: Raw AWS event
{
  "LogicalResourceId": "MyEC2",
  "ResourceStatus": "CREATE_IN_PROGRESS",
  "PhysicalResourceId": "i-1234567890abcdef",
  ...
}

# Output: JSON for frontend
{
  "type": "resource_update",
  "resource": {
    "logicalId": "MyEC2",
    "status": "CREATE_IN_PROGRESS",
    "physicalId": "i-1234567890abcdef",
    "progress": 33
  },
  "stack": {
    "totalResources": 3,
    "completedResources": 1,
    "inProgressResources": 1,
    "progress": 33
  }
}
```

---

## Timing & Efficiency

### **Polling Strategy**

```
Time 0s:    Frontend connects
├─ Polling task starts
│
Time 1s:    await asyncio.sleep(3)
│
Time 3s:    Poll AWS
├─ describe_stack_events() call
├─ Parse new events
├─ Broadcast to clients
│
Time 4s:    await asyncio.sleep(3)
│
Time 7s:    Poll AWS again
├─ describe_stack_events() call
├─ Parse new events
├─ Broadcast to clients
│
... repeats every 3 seconds ...
│
Time 180s:  Stack complete
├─ is_deployment_complete() returns True
├─ Loop exits
├─ Send completion event
├─ Wait 2 seconds for UI update
└─ Connection stays open for manual close
```

### **Why Every 3 Seconds?**

- ✅ **Responsive enough**: Users see updates within 3 seconds
- ✅ **Not too frequent**: Doesn't hammer AWS API
- ✅ **AWS throttling safe**: Well within rate limits
- ✅ **Network efficient**: Only sends actual changes, not empty polls

---

## Multiple Clients - Same Stack

```
Client 1 (Browser A)
    │
    └─► ws://localhost:8000/canvas/deploy/track/foundry-stack-12345678
            │
            ├─ Polling task (single, shared)
            │
        ◄───┤ Every 3s: describe_stack_events()
            │
            ├─► format event ──┐
            │                  │
        ┌───┴──────────────────┤
        │                      │
        ▼                      │
   Send to Client 1          │
   Send to Client 2 ◄────────┘
   Send to Client 3
   Send to Client 4
        │
Client 2 (Browser B)
Client 3 (Browser C)
Client 4 (Browser D)
```

**Benefits:**
- One polling task per stack (not per client)
- All clients get same updates
- Reduces AWS API calls
- Efficient resource usage

---

## Error Handling

```
AWS describe_stack_events()
       │
       ├─ Success: Process events, continue
       │
       ├─ ValidationError: Stack doesn't exist yet, return []
       │     └─ Polling continues
       │
       └─ Network error: Caught, error event sent to clients
             └─ Polling stops gracefully
```

---

## Complete Request/Response Cycle (Per Poll)

```
1. EVENT_TRACKER.get_new_events()
   ├─ self.cf_client.describe_stack_events(StackName=stack_name)
   │  └─ AWS API Response: {"StackEvents": [event1, event2, ...]}
   │
   ├─ Filter by event_id (remove duplicates)
   │
   ├─ self._update_resource_status(event)
   │  └─ Update internal caches
   │
   └─ return new_events (in chronological order)

2. For each event:
   ├─ stack_summary = tracker.get_stack_summary()
   │  └─ Calculate: progress, total resources, completed, failed
   │
   ├─ formatted = format_resource_event(event, stack_summary, progress)
   │  └─ Create JSON for frontend
   │
   └─ await broadcast_to_stack(formatted)
      └─ Send JSON to all connected clients via WebSocket

3. Output to Frontend:
   {
     "type": "resource_update",
     "timestamp": "2025-11-15T10:30:45Z",
     "resource": {
       "logicalId": "MyEC2Instance",
       "type": "AWS::EC2::Instance",
       "status": "CREATE_COMPLETE",
       "physicalId": "i-1234567890abcdef",
       "progress": 66
     },
     "stack": {
       "name": "foundry-stack-12345678",
       "status": "CREATE_IN_PROGRESS",
       "totalResources": 3,
       "completedResources": 2,
       "inProgressResources": 1,
       "failedResources": 0,
       "progress": 66
     }
   }

4. Sleep 3 seconds, repeat
```

---

## Summary

**The Connection Flow:**

1. Frontend opens WebSocket to `/canvas/deploy/track/{stack_name}`
2. Backend accepts connection with `websocket.accept()`
3. Backend starts async polling task (if not already running)
4. Every 3 seconds:
   - AWS CloudFormation API: `describe_stack_events()`
   - Filter new events by EventId
   - Calculate progress and summaries
   - Format events as JSON
   - Broadcast to ALL connected clients
5. When stack reaches terminal state (CREATE_COMPLETE, CREATE_FAILED, etc.):
   - Send completion event with outputs
   - Close polling loop
   - Keep WebSocket connection open for manual cleanup

**Key Architecture Decisions:**

- ✅ **WebSocket**: Real-time, persistent connection
- ✅ **Polling + Dedup**: Reliable event capture without missing updates
- ✅ **Async**: Handles multiple clients efficiently
- ✅ **3-second interval**: Sweet spot between responsiveness and API efficiency
- ✅ **One polling task per stack**: Shared across all clients
