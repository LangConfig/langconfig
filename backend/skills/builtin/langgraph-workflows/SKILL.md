---
name: langgraph-workflows
description: "Expert guidance for designing LangGraph state machines and multi-agent workflows. Use when building workflows, connecting agents, or implementing complex control flow in LangConfig."
version: 1.0.0
author: LangConfig
tags:
  - langgraph
  - workflows
  - state-machine
  - multi-agent
  - orchestration
triggers:
  - "when user mentions LangGraph"
  - "when user mentions workflow"
  - "when user mentions state machine"
  - "when user mentions multi-agent"
  - "when connecting agents"
allowed_tools:
  - filesystem
  - shell
  - python
---

## Instructions

You are an expert LangGraph architect helping users design and build workflows in LangConfig. LangGraph enables stateful, cyclic, multi-agent workflows with automatic state management.

### LangGraph Core Concepts

Based on official LangGraph documentation:

#### StateGraph
A specialized graph that maintains and updates shared state throughout execution:
- Each node receives current state and returns updated state
- State is automatically passed between nodes
- Enables context-aware decision-making and persistent memory

#### Nodes
Represent processing steps in the workflow:
```python
# Each node is a function that takes state and returns updates
def research_node(state: WorkflowState) -> dict:
    # Process state
    result = do_research(state["query"])
    # Return state updates
    return {"research_results": result}
```

#### Edges
Define transitions between nodes:
- **Static edges**: Fixed transitions (A → B)
- **Conditional edges**: Dynamic routing based on state

### LangConfig Node Types

#### AGENT_NODE
Standard LLM agent that processes input and can use tools:
```json
{
  "id": "researcher",
  "type": "AGENT_NODE",
  "data": {
    "agentType": "AGENT_NODE",
    "name": "Research Agent",
    "model": "claude-sonnet-4-5-20250929",
    "system_prompt": "Research the given topic thoroughly.",
    "native_tools": ["web_search", "web_fetch"],
    "temperature": 0.5
  }
}
```

#### CONDITIONAL_NODE
Routes workflow based on evaluated conditions:
```json
{
  "id": "router",
  "type": "CONDITIONAL_NODE",
  "data": {
    "agentType": "CONDITIONAL_NODE",
    "condition": "'error' in messages[-1].content.lower()",
    "true_route": "error_handler",
    "false_route": "continue_processing"
  }
}
```

#### LOOP_NODE
Implements iteration with exit conditions:
```json
{
  "id": "refinement_loop",
  "type": "LOOP_NODE",
  "data": {
    "agentType": "LOOP_NODE",
    "max_iterations": 5,
    "exit_condition": "'APPROVED' in messages[-1].content"
  }
}
```

#### OUTPUT_NODE
Terminates workflow and formats final output:
```json
{
  "id": "output",
  "type": "OUTPUT_NODE",
  "data": {
    "agentType": "OUTPUT_NODE",
    "output_format": "markdown"
  }
}
```

#### CHECKPOINT_NODE
Saves workflow state for resumption:
```json
{
  "id": "checkpoint",
  "type": "CHECKPOINT_NODE",
  "data": {
    "agentType": "CHECKPOINT_NODE",
    "checkpoint_name": "after_research"
  }
}
```

#### APPROVAL_NODE
Human-in-the-loop checkpoint:
```json
{
  "id": "human_review",
  "type": "APPROVAL_NODE",
  "data": {
    "agentType": "APPROVAL_NODE",
    "approval_prompt": "Please review the generated content."
  }
}
```

### Workflow Patterns

#### 1. Sequential Pipeline
Simple linear flow of agents:
```
START → Agent A → Agent B → Agent C → END

Use case: Content generation pipeline
- Research → Outline → Write → Edit
```

#### 2. Conditional Branching
Route based on output:
```
START → Classifier → [Condition]
                        ├── Route A → Handler A → END
                        └── Route B → Handler B → END

Use case: Intent classification
- Classify query → Route to appropriate specialist
```

#### 3. Reflection/Critique Loop
Self-improvement cycle:
```
START → Generator → Critic → [Condition]
                               ├── PASS → END
                               └── REVISE → Generator (loop)

Use case: Code review, content quality
- Generate → Critique → Revise until approved
```

#### 4. Supervisor Pattern
Central coordinator managing specialists:
```
START → Supervisor → [Delegate]
                        ├── Specialist A → Supervisor
                        ├── Specialist B → Supervisor
                        └── Complete → END

Use case: Complex research tasks
- Supervisor assigns subtasks to specialists
```

#### 5. Map-Reduce
Parallel processing with aggregation:
```
START → Splitter → [Parallel]
                      ├── Worker A ─┐
                      ├── Worker B ─┼→ Aggregator → END
                      └── Worker C ─┘

Use case: Document analysis
- Split document → Analyze sections → Combine insights
```

### State Management

#### Workflow State Schema
```python
class WorkflowState(TypedDict):
    # Core identifiers
    workflow_id: int
    task_id: Optional[int]

    # Message history (accumulates via reducer)
    messages: Annotated[List[BaseMessage], operator.add]

    # User input
    query: str

    # RAG context
    context_documents: Optional[List[int]]

    # Execution tracking
    current_node: Optional[str]
    step_history: Annotated[List[Dict], operator.add]

    # Control flow
    conditional_route: Optional[str]
    loop_iterations: Optional[Dict[str, int]]

    # Results
    result: Optional[Dict[str, Any]]
    error_message: Optional[str]
```

#### State Reducers
Automatically combine state updates:
```python
# Messages accumulate (don't overwrite)
messages: Annotated[List[BaseMessage], operator.add]

# Step history accumulates
step_history: Annotated[List[Dict], operator.add]
```

### Edge Configuration

#### Static Edge
Always routes to specified node:
```json
{
  "source": "researcher",
  "target": "writer",
  "type": "default"
}
```

#### Conditional Edge
Routes based on state:
```json
{
  "source": "classifier",
  "target": "router",
  "type": "conditional",
  "data": {
    "condition": "state['intent']",
    "routes": {
      "question": "qa_agent",
      "task": "task_agent",
      "default": "general_agent"
    }
  }
}
```

### Best Practices

#### 1. Keep Nodes Focused
Each node should do ONE thing well:
- ❌ "Research and write and edit"
- ✅ "Research" → "Write" → "Edit"

#### 2. Use Checkpoints Strategically
Save state at expensive operations:
- After long LLM calls
- Before human approval
- At natural breakpoints

#### 3. Handle Errors Gracefully
Add error handling paths:
```
Agent → [Error?]
          ├── No → Continue
          └── Yes → Error Handler → Retry/Exit
```

#### 4. Limit Loop Iterations
Always set `max_iterations` to prevent infinite loops:
```json
{
  "max_iterations": 5,
  "exit_condition": "'DONE' in result"
}
```

#### 5. Design for Observability
Include meaningful names and step history:
- Name nodes descriptively
- Log state transitions
- Track timing metrics

### Debugging Workflows

#### Common Issues

1. **Workflow hangs**
   - Check for missing edges
   - Verify conditional logic
   - Look for infinite loops

2. **Wrong routing**
   - Debug condition expressions
   - Check state values
   - Verify edge labels match

3. **State not updating**
   - Ensure nodes return dict updates
   - Check reducer configuration
   - Verify key names match

4. **Memory issues**
   - Limit message history
   - Checkpoint and clear old state
   - Use streaming for large outputs

## Examples

**User asks:** "Build a workflow for writing blog posts"

**Response approach:**
1. Design pipeline: Research → Outline → Write → Edit → Review
2. Add CONDITIONAL_NODE after Review (PASS/REVISE)
3. Create loop back to Write if revision needed
4. Set max_iterations to prevent infinite loops
5. Add OUTPUT_NODE to format final post
6. Configure each agent with appropriate tools
