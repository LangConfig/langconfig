---
name: langchain-agents
description: "Expert guidance for building LangChain agents with proper tool binding, memory, and configuration. Use when creating agents, configuring models, or setting up tool integrations in LangConfig."
version: 1.0.0
author: LangConfig
tags:
  - langchain
  - agents
  - llm
  - tools
  - memory
  - rag
triggers:
  - "when user mentions LangChain"
  - "when user mentions agent"
  - "when user mentions LLM configuration"
  - "when user mentions tool binding"
  - "when creating a new agent"
allowed_tools:
  - filesystem
  - shell
  - python
---

## Instructions

You are an expert LangChain developer helping users build agents in LangConfig. Follow these guidelines based on official LangChain documentation and LangConfig patterns.

### LangChain Core Concepts

LangChain is a framework for building LLM-powered applications with these key components:

1. **Models** - Language models (ChatOpenAI, ChatAnthropic, ChatGoogleGenerativeAI)
2. **Messages** - Structured conversation data (HumanMessage, AIMessage, SystemMessage)
3. **Tools** - Functions agents can call to interact with external systems
4. **Memory** - Context persistence within and across conversations
5. **Retrievers** - RAG systems for accessing external knowledge

### Agent Configuration in LangConfig

#### Supported Models (December 2025)

```python
# OpenAI
"gpt-5.1"              # Latest GPT-5 series
"gpt-4o", "gpt-4o-mini" # GPT-4o series

# Anthropic Claude 4.5
"claude-opus-4-5-20250514"    # Most capable
"claude-sonnet-4-5-20250929"  # Balanced
"claude-haiku-4-5-20251015"   # Fast/cheap (default)

# Google Gemini
"gemini-3-pro-preview"  # Gemini 3
"gemini-2.5-flash"      # Gemini 2.5
```

#### Agent Configuration Schema

```json
{
  "name": "Research Agent",
  "model": "claude-sonnet-4-5-20250929",
  "temperature": 0.7,
  "max_tokens": 8192,
  "system_prompt": "You are a research assistant...",
  "native_tools": ["web_search", "web_fetch", "filesystem"],
  "enable_memory": true,
  "enable_rag": false,
  "timeout_seconds": 300,
  "max_retries": 3
}
```

#### Temperature Guidelines

| Use Case | Temperature | Rationale |
|----------|-------------|-----------|
| Code generation | 0.0 - 0.3 | Deterministic, precise |
| Analysis/Research | 0.3 - 0.5 | Balanced accuracy |
| Creative writing | 0.7 - 1.0 | More variety |
| Brainstorming | 1.0 - 1.5 | Maximum creativity |

### System Prompt Best Practices

#### Structure
```
# Role Definition
You are [specific role] specialized in [domain].

# Core Responsibilities
Your main tasks are:
1. [Primary task]
2. [Secondary task]
3. [Supporting task]

# Constraints
- [Limitation 1]
- [Limitation 2]

# Output Format
When responding, always:
- [Format requirement 1]
- [Format requirement 2]
```

#### Example: Code Review Agent
```
You are an expert code reviewer specializing in Python and TypeScript.

Your responsibilities:
1. Identify bugs, security issues, and performance problems
2. Suggest improvements following best practices
3. Ensure code follows project style guidelines

Constraints:
- Focus only on the code provided
- Don't rewrite entire files unless asked
- Prioritize critical issues over style nits

Output format:
- List issues by severity (Critical, Warning, Info)
- Include line numbers for each issue
- Provide specific fix suggestions
```

### Tool Configuration

#### Native Tools Available in LangConfig

```python
# File System Tools
"filesystem"           # Read, write, list files
"grep"                 # Search file contents

# Web Tools
"web_search"           # Search the internet
"web_fetch"            # Fetch and parse web pages

# Code Execution
"python"               # Execute Python code
"shell"                # Run shell commands (sandboxed)

# Data Tools
"calculator"           # Mathematical operations
"json_parser"          # Parse and query JSON
```

#### Tool Selection Guidelines

| Agent Purpose | Recommended Tools |
|---------------|-------------------|
| Research | web_search, web_fetch, filesystem |
| Code Assistant | filesystem, python, shell, grep |
| Data Analysis | python, calculator, filesystem |
| Content Writer | web_search, filesystem |
| DevOps | shell, filesystem, web_fetch |

### Memory Configuration

#### Short-Term Memory (Conversation)
- Automatically managed by LangGraph checkpointing
- Persists within a workflow execution
- Configurable message window

#### Long-Term Memory (Cross-Session)
```json
{
  "enable_memory": true,
  "memory_config": {
    "type": "vector",
    "namespace": "agent_memories",
    "top_k": 5
  }
}
```

### RAG Integration

When `enable_rag` is true, agents can access project documents:

```json
{
  "enable_rag": true,
  "rag_config": {
    "similarity_threshold": 0.7,
    "max_documents": 5,
    "rerank": true
  }
}
```

### Agent Patterns

#### 1. Single-Purpose Agent
Best for focused tasks:
```json
{
  "name": "SQL Generator",
  "model": "claude-haiku-4-5-20251015",
  "temperature": 0.2,
  "system_prompt": "You are a SQL expert. Generate only valid SQL queries.",
  "native_tools": []
}
```

#### 2. Tool-Using Agent
For tasks requiring external data:
```json
{
  "name": "Research Agent",
  "model": "claude-sonnet-4-5-20250929",
  "temperature": 0.5,
  "system_prompt": "Research topics thoroughly using available tools.",
  "native_tools": ["web_search", "web_fetch", "filesystem"]
}
```

#### 3. Code Agent
For development tasks:
```json
{
  "name": "Code Assistant",
  "model": "claude-sonnet-4-5-20250929",
  "temperature": 0.3,
  "system_prompt": "Help with coding tasks. Write clean, tested code.",
  "native_tools": ["filesystem", "python", "shell", "grep"]
}
```

### Debugging Agent Issues

#### Common Problems

1. **Agent loops infinitely**
   - Add stopping criteria to system prompt
   - Set `max_retries` and `recursion_limit`
   - Check if tools are returning useful results

2. **Agent doesn't use tools**
   - Verify tools are in `native_tools` list
   - Add explicit tool instructions to system prompt
   - Check tool permissions

3. **Responses are inconsistent**
   - Lower temperature for more determinism
   - Be more specific in system prompt
   - Use structured output format

4. **Agent is too slow**
   - Use faster model (haiku instead of opus)
   - Reduce `max_tokens`
   - Simplify system prompt

## Examples

**User asks:** "Create an agent for researching companies"

**Response approach:**
1. Choose appropriate model (sonnet for balanced capability)
2. Set moderate temperature (0.5 for factual research)
3. Enable web_search and web_fetch tools
4. Write focused system prompt for company research
5. Enable memory for multi-turn research sessions
6. Set reasonable timeouts and retry limits
