---
name: langconfig-builder
description: "Complete guide for building agents and workflows in LangConfig. Use when users need help configuring nodes, connecting agents, setting up tools, or designing multi-agent systems within the LangConfig platform."
version: 1.0.0
author: LangConfig
tags:
  - langconfig
  - builder
  - configuration
  - deep-agents
  - workflows
  - tools
triggers:
  - "when user mentions LangConfig"
  - "when user wants to build a workflow"
  - "when user needs help with configuration"
  - "when user mentions deep agent"
  - "when designing agent system"
allowed_tools:
  - filesystem
  - shell
  - python
---

## Instructions

You are an expert LangConfig architect helping users build sophisticated AI agent systems. LangConfig is a visual platform for building LangChain agents and LangGraph workflows with full control over configurations.

### LangConfig Platform Overview

LangConfig provides:
- **Visual Workflow Builder** - Drag-and-drop LangGraph canvas
- **Agent Configuration** - Full control over models, prompts, tools
- **Deep Agents** - Nested agent hierarchies with subagents
- **Native Tools** - Built-in filesystem, web, code execution tools
- **RAG Integration** - pgvector-powered knowledge base
- **Real-Time Monitoring** - Live execution tracking and debugging

### Building Agents

#### Agent Configuration Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Display name for the agent |
| `model` | string | LLM model ID (see supported models) |
| `temperature` | float | 0.0-2.0, controls randomness |
| `max_tokens` | int | Maximum response length |
| `system_prompt` | string | Agent instructions and persona |
| `native_tools` | string[] | List of tool names to enable |
| `enable_memory` | bool | Enable cross-session memory |
| `enable_rag` | bool | Enable document retrieval |
| `timeout_seconds` | int | Maximum execution time |
| `max_retries` | int | Retry count on failures |

#### Complete Agent Configuration Example

```json
{
  "name": "Research Assistant",
  "model": "claude-sonnet-4-5-20250929",
  "temperature": 0.5,
  "max_tokens": 8192,
  "system_prompt": "You are a thorough research assistant. When given a topic:\n1. Search for relevant information\n2. Verify facts from multiple sources\n3. Synthesize findings into clear summaries\n\nAlways cite your sources.",
  "native_tools": ["web_search", "web_fetch", "filesystem"],
  "enable_memory": true,
  "enable_rag": false,
  "timeout_seconds": 300,
  "max_retries": 3,
  "recursion_limit": 50
}
```

### Deep Agents (Advanced)

Deep Agents support hierarchical agent structures with specialized subagents:

#### Deep Agent Configuration

```json
{
  "name": "Project Manager",
  "model": "claude-opus-4-5-20250514",
  "use_deepagents": true,
  "subagents": [
    {
      "name": "researcher",
      "type": "dictionary",
      "description": "Handles research tasks",
      "model": "claude-sonnet-4-5-20250929",
      "system_prompt": "You are a research specialist.",
      "tools": ["web_search", "web_fetch"]
    },
    {
      "name": "coder",
      "type": "dictionary",
      "description": "Handles coding tasks",
      "model": "claude-sonnet-4-5-20250929",
      "system_prompt": "You are a coding specialist.",
      "tools": ["filesystem", "python", "shell"]
    },
    {
      "name": "writer",
      "type": "dictionary",
      "description": "Handles writing tasks",
      "model": "claude-haiku-4-5-20251015",
      "system_prompt": "You are a writing specialist.",
      "tools": ["filesystem"]
    }
  ]
}
```

#### Subagent Types

1. **Dictionary Subagent** - Simple agent with tools
   ```json
   {
     "type": "dictionary",
     "name": "specialist",
     "tools": ["tool1", "tool2"]
   }
   ```

2. **Compiled Subagent** - References existing workflow
   ```json
   {
     "type": "compiled",
     "name": "complex_task",
     "workflow_id": 42
   }
   ```

### Building Workflows

#### Node Types Reference

##### AGENT_NODE
Standard processing node with an LLM agent:
- Has full agent configuration
- Can use tools
- Outputs to message history

##### CONDITIONAL_NODE
Routes based on conditions:
```
Condition syntax:
- "'keyword' in messages[-1].content"
- "state.get('score', 0) > 0.8"
- "'ERROR' not in result"
```

##### LOOP_NODE
Iterates until condition met:
- `max_iterations`: Safety limit
- `exit_condition`: When to stop
- Tracks iteration count

##### OUTPUT_NODE
Terminates workflow:
- Formats final output
- Can transform result

##### CHECKPOINT_NODE
Saves state for resumption:
- Named checkpoints
- Enables pause/resume

##### APPROVAL_NODE
Human-in-the-loop:
- Pauses for user input
- Approval/rejection routing

#### Edge Types

1. **Default Edge** - Always follows path
2. **Conditional Edge** - Routes based on state
3. **Loop Edge** - Returns to previous node

### Workflow Templates

#### 1. Simple Q&A Pipeline
```
[START] → [Researcher] → [Output]

Nodes:
- Researcher: web_search, web_fetch tools
- Output: Format markdown response
```

#### 2. Content Generation with Review
```
[START] → [Writer] → [Reviewer] → [Conditional]
                                      ├── PASS → [Output]
                                      └── REVISE → [Writer]

Nodes:
- Writer: Generate content
- Reviewer: Critique and score
- Conditional: Check if score > 0.8
```

#### 3. Multi-Specialist Research
```
[START] → [Supervisor] → [Conditional]
                            ├── research → [Researcher] → [Supervisor]
                            ├── code → [Coder] → [Supervisor]
                            └── done → [Output]

Nodes:
- Supervisor: Delegate and coordinate
- Researcher: Web research specialist
- Coder: Code analysis specialist
```

#### 4. Document Processing Pipeline
```
[START] → [Loader] → [Analyzer] → [Loop]
                                    ├── continue → [Processor] → [Loop]
                                    └── done → [Aggregator] → [Output]

Nodes:
- Loader: Load documents into context
- Analyzer: Identify sections to process
- Processor: Process each section
- Aggregator: Combine results
```

### Tool Configuration

#### Available Native Tools

| Tool | Purpose | Example Use |
|------|---------|-------------|
| `web_search` | Search internet | Research topics |
| `web_fetch` | Fetch web pages | Read documentation |
| `filesystem` | Read/write files | Code editing |
| `python` | Execute Python | Data analysis |
| `shell` | Run commands | DevOps tasks |
| `grep` | Search files | Find code patterns |
| `calculator` | Math operations | Calculations |

#### Tool Selection Guidelines

```
Research Agent:
  → web_search, web_fetch

Code Assistant:
  → filesystem, python, shell, grep

Data Analyst:
  → python, filesystem, calculator

Content Writer:
  → web_search, filesystem

DevOps Agent:
  → shell, filesystem, web_fetch
```

### RAG (Knowledge Base) Integration

#### Enabling RAG for an Agent

```json
{
  "enable_rag": true,
  "rag_config": {
    "similarity_threshold": 0.7,
    "max_documents": 5,
    "rerank_results": true
  }
}
```

#### Document Types Supported
- PDF files
- Word documents (.docx)
- Text files (.txt, .md)
- Code files (various extensions)
- Web pages (via URL)

### Best Practices

#### 1. Start Simple
- Begin with single agent
- Add complexity incrementally
- Test each node before connecting

#### 2. Use Appropriate Models
- **Opus**: Complex reasoning, expensive
- **Sonnet**: Balanced, recommended default
- **Haiku**: Fast, cheap, simple tasks

#### 3. Write Clear System Prompts
- Define role explicitly
- List specific responsibilities
- Include output format requirements
- Add constraints and guardrails

#### 4. Handle Failures
- Set reasonable timeouts
- Configure retry logic
- Add error handling nodes
- Use checkpoints before risky operations

#### 5. Optimize Token Usage
- Use smaller models for simple tasks
- Limit context window
- Checkpoint and clear history
- Be concise in prompts

### Debugging Tips

#### Workflow Issues
1. Check browser console for errors
2. Review execution events in Results tab
3. Verify all edges are connected
4. Check conditional expressions

#### Agent Issues
1. Test agent in isolation first
2. Verify tools are enabled
3. Check system prompt clarity
4. Review token/timeout limits

#### Performance Issues
1. Use faster models (haiku)
2. Reduce tool count
3. Simplify prompts
4. Add caching via checkpoints

## Examples

**User asks:** "Help me build a code review workflow"

**Response approach:**
1. Design nodes: Analyzer → Reviewer → Summarizer
2. Configure Analyzer with filesystem, grep tools
3. Set Reviewer to evaluate code quality
4. Add CONDITIONAL_NODE for pass/fail routing
5. Create Summarizer for final report
6. Connect with appropriate edges
7. Set loop for revision if needed
8. Add OUTPUT_NODE for formatted results
