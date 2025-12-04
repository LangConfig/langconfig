# Chat API - DeepAgent Testing Interface

Complete chat system for testing DeepAgents before export, with automatic memory management and conversation persistence.

## Features

✅ **Token-by-Token Streaming** - Real-time response streaming using LangGraph `astream_events`
✅ **Dual Storage Architecture** - PostgreSQL JSON + LangGraph checkpointer for reliability
✅ **Automatic Cleanup** - TTL-based session cleanup (1 hour inactive timeout)
✅ **Checkpoint Management** - Automatic cleanup of LangGraph state on session end
✅ **Message Banking** - Mark important messages for guaranteed inclusion in context
✅ **Health Monitoring** - Built-in health checks and consistency validation
✅ **Memory Management** - Automatic summarization and eviction via guardrails

## Architecture

### Dual Storage System

The chat system uses **two storage mechanisms** working together:

| Storage | Purpose | Format | Access |
|---------|---------|--------|--------|
| **PostgreSQL JSON** | UI, history, context | `{role, content, timestamp, banked}` | Direct SQL queries |
| **LangGraph Checkpointer** | Agent memory, auto-compaction | Binary BaseMessage | Via thread_id |

**Why Dual Storage?**
- **Reliability**: If one fails, the other preserves history
- **Performance**: UI reads from fast JSON, agent uses optimized checkpointer
- **Features**: Banking, metrics, analytics require queryable storage
- **Compatibility**: Conversation context service needs structured data

### Session Lifecycle

```
┌──────────┐      ┌──────────┐      ┌──────────┐      ┌──────────┐
│  Start   │─────▶│  Active  │─────▶│   Idle   │─────▶│   End    │
│  Session │      │   Chat   │      │ (cached) │      │  Cleanup │
└──────────┘      └──────────┘      └──────────┘      └──────────┘
     │                 │                  │                  │
     ▼                 ▼                  ▼                  ▼
 Create DB      Cache agent        TTL cleanup       Delete checkpoints
 Assign UUID    Store messages     (5 min check)     Remove from cache
```

**Lifecycle States:**
1. **Start** - User opens chat → Create session, assign `thread_id`
2. **Active** - Messages flow through both storage systems
3. **Idle** - Session cached but inactive (removed after 1 hour)
4. **End** - User explicitly ends → Cleanup cache + checkpoints

### Memory Management

#### Session Manager

`ChatSessionManager` handles agent instance caching and automatic cleanup:

- **TTL**: 1 hour (configurable)
- **Cleanup Interval**: 5 minutes (background task)
- **Caching**: Agent instances cached per session_id
- **Metrics**: Active sessions, stale count, average age

```python
from services.chat_session_manager import get_session_manager

manager = get_session_manager()
stats = manager.get_stats()
# {
#   "active_sessions": 5,
#   "stale_sessions": 2,
#   "avg_session_age_seconds": 1200,
#   "ttl_seconds": 3600,
#   "is_running": True
# }
```

#### Checkpoint Cleanup

LangGraph creates checkpoint records for every message. These are cleaned up when:

1. **Session Ends** - User explicitly ends chat
2. **Scheduled Cleanup** - Old checkpoints removed periodically (30+ days)

```python
# Automatic cleanup on session end
await delete_thread_checkpoints(thread_id=session_id)
```

## API Endpoints

### Session Lifecycle

#### POST `/api/chat/start`

Start a new chat session.

**Request:**
```json
{
  "agent_id": 1,
  "user_id": 123  // optional
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "agent_id": 1,
  "agent_name": "Code Helper",
  "is_active": true,
  "message_count": 0,
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

#### POST `/api/chat/{session_id}/end`

End a chat session and cleanup resources.

**Response:**
```json
{
  "status": "success",
  "message": "Session ended",
  "agent_removed": true,
  "checkpoints_cleaned": true
}
```

---

### Messaging

#### POST `/api/chat/message`

Send a message (synchronous, full response).

**Request:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Hello, how are you?"
}
```

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Hello! I'm doing well, thank you for asking.",
  "tool_calls": [],
  "subagent_activity": [],
  "metrics": {
    "total_tokens": 42
  }
}
```

#### POST `/api/chat/message/stream`

Send a message (streaming, token-by-token).

**Request:** Same as `/message`

**Response:** Server-Sent Events (SSE)

```
data: {"type": "chunk", "content": "Hello"}
data: {"type": "chunk", "content": "!"}
data: {"type": "chunk", "content": " I'm"}
data: {"type": "chunk", "content": " doing"}
...
data: {"type": "complete", "content": "Hello! I'm doing well..."}
```

---

### Session Data

#### GET `/api/chat/{session_id}/history`

Get full conversation history.

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    {
      "role": "user",
      "content": "Hello"
    },
    {
      "role": "assistant",
      "content": "Hi there!"
    }
  ],
  "metrics": {
    "total_tokens": 42
  }
}
```

#### GET `/api/chat/{session_id}/metrics`

Get detailed session metrics.

**Response:**
```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "metrics": {
    "total_tokens": 1500,
    "tool_calls": 3,
    "subagent_spawns": 1
  },
  "tool_calls": [...],
  "subagent_spawns": [...],
  "context_operations": [...],
  "message_count": 10,
  "is_active": true,
  "duration_seconds": 3600
}
```

---

### Message Banking

#### POST `/api/chat/{session_id}/messages/{message_index}/bank`

Mark a message as important for future context.

**Response:**
```json
{
  "status": "success",
  "message": "Message banked successfully",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_index": 3
}
```

#### DELETE `/api/chat/{session_id}/messages/{message_index}/bank`

Unmark a banked message.

---

### Health & Monitoring

#### GET `/api/chat/health`

Get chat system health status.

**Response:**
```json
{
  "status": "healthy",
  "session_manager": {
    "active_sessions": 5,
    "stale_sessions": 0,
    "avg_session_age_seconds": 1200,
    "ttl_seconds": 3600,
    "is_running": true
  },
  "active_db_sessions": 5,
  "inconsistencies": [],
  "timestamp": "2025-01-15T10:30:00Z"
}
```

---

### List Sessions

#### GET `/api/chat/sessions`

List all chat sessions.

**Query Parameters:**
- `agent_id` (optional) - Filter by agent ID
- `active_only` (optional) - Show only active sessions

**Response:**
```json
[
  {
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_id": 1,
    "agent_name": "Code Helper",
    "is_active": true,
    "message_count": 10,
    "created_at": "2025-01-15T10:00:00Z",
    "updated_at": "2025-01-15T10:30:00Z"
  }
]
```

## Configuration

### Session Manager Settings

Edit `services/chat_session_manager.py`:

```python
ChatSessionManager(
    ttl_seconds=3600,      # 1 hour inactive timeout
    cleanup_interval=300   # Check every 5 minutes
)
```

### Guardrails Configuration

Token limits are configured per agent in `DeepAgentConfig`:

```json
{
  "guardrails": {
    "token_limits": {
      "max_total_tokens": 100000,
      "eviction_threshold": 80000,
      "summarization_threshold": 60000
    },
    "enable_auto_eviction": true,
    "enable_summarization": true
  }
}
```

## Database Schema

### ChatSession Model

```python
class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: int                                    # Primary key
    session_id: str                            # UUID, unique
    agent_id: int                              # FK to deep_agent_templates
    user_id: Optional[int]                     # Optional user tracking
    messages: List[Dict]                       # JSON: [{role, content, timestamp, banked}]
    metrics: Dict[str, Any]                    # JSON: {total_tokens, ...}
    tool_calls: List[Dict]                     # JSON: Tool invocation history
    subagent_spawns: List[Dict]                # JSON: Subagent activity
    context_operations: List[Dict]             # JSON: Evictions, summarizations
    is_active: bool                            # Active status
    checkpoint_id: Optional[str]               # LangGraph checkpoint reference
    created_at: datetime
    updated_at: datetime
    ended_at: Optional[datetime]
```

**Index:**
- `idx_chat_sessions_agent_id_active` on `(agent_id, is_active)`

### Checkpointer Tables (LangGraph)

Created automatically by `setup_checkpointing()`:

- `checkpoints` - Conversation state snapshots
- `checkpoint_writes` - Write-ahead log
- `checkpoint_blobs` - Large state data

## Best Practices

### 1. Always Use flag_modified()

When updating JSON columns, tell SQLAlchemy the column changed:

```python
from sqlalchemy.orm.attributes import flag_modified

session.messages.append({"role": "user", "content": "Hello"})
flag_modified(session, "messages")  # Required!
db.commit()
```

### 2. Cache Agent Instances

Use the session manager helpers instead of direct dictionary access:

```python
# Good
agent = get_cached_agent(session_id)
cache_agent(session_id, agent_instance)

# Bad (legacy)
agent = active_agents.get(session_id)
active_agents[session_id] = agent_instance
```

### 3. Clean Up Resources

Always clean up when session ends:

```python
# Remove from cache
manager = get_session_manager()
manager.remove_session(session_id)

# Delete checkpoints
await delete_thread_checkpoints(thread_id=session_id)
```

### 4. Monitor Health

Regularly check system health:

```bash
curl http://localhost:8765/api/chat/health
```

Watch for:
- High `stale_sessions` count
- `inconsistencies` array not empty
- `status` not "healthy"

### 5. Handle Errors Gracefully

Checkpointer cleanup is optional - log warnings, don't fail:

```python
try:
    await delete_thread_checkpoints(thread_id=session_id)
except Exception as e:
    logger.warning(f"Checkpoint cleanup failed: {e}")
    # Continue - not critical
```

## Troubleshooting

### Sessions Not Cleaning Up

**Symptom:** Memory usage keeps growing

**Fix:** Check session manager is running:

```python
manager = get_session_manager()
stats = manager.get_stats()
print(stats["is_running"])  # Should be True
```

### Messages Not Persisting

**Symptom:** Conversation lost after refresh

**Fix:** Ensure `flag_modified()` is used:

```bash
# Check database
psql -d langconfig -c "SELECT session_id, array_length(messages, 1) as msg_count FROM chat_sessions WHERE is_active = true;"
```

### Checkpoints Accumulating

**Symptom:** Database growing rapidly

**Fix:** Verify cleanup on session end:

```sql
-- Check checkpoint count
SELECT COUNT(*) FROM checkpoints;

-- Checkpoints for specific thread
SELECT * FROM checkpoints WHERE thread_id = 'session-uuid' ORDER BY created_at DESC;
```

## Development

### Running Tests

```bash
# Unit tests
pytest backend/tests/test_chat_session_manager.py

# Integration tests
pytest backend/tests/integration/test_chat_api.py

# Health check
curl http://localhost:8765/api/chat/health
```

### Monitoring Logs

```bash
# Watch session manager activity
tail -f logs/app.log | grep "ChatSessionManager\|chat_session"

# Check cleanup activity
tail -f logs/app.log | grep "Cleaned up"
```

## Migration from Legacy Code

If upgrading from the old `active_agents` dictionary:

1. ✅ Session manager automatically wraps legacy code
2. ✅ Both systems work during transition
3. ✅ Cleanup happens via new manager
4. ⚠️ Eventually remove `active_agents` global

```python
# Transition complete when this is removed:
active_agents: Dict[str, Any] = {}  # Legacy: Will be removed
```

## Contributing

When modifying the chat system:

1. ✅ Update dual storage systems atomically
2. ✅ Use `flag_modified()` for JSON columns
3. ✅ Add logging for debugging
4. ✅ Update health checks if adding features
5. ✅ Test with session manager running
6. ✅ Document configuration changes

## License

Copyright (c) 2025 Cade Russell
Licensed under the MIT License
