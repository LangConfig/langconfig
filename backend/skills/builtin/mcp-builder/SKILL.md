---
name: mcp-builder
description: "Comprehensive guide for creating Model Context Protocol (MCP) servers. Use when building MCP servers, integrating external APIs, or creating tool interfaces for LLMs."
version: 1.0.0
author: LangConfig
tags:
  - mcp
  - api
  - typescript
  - python
  - tools
  - integration
triggers:
  - "when user mentions MCP"
  - "when user mentions Model Context Protocol"
  - "when user wants to create tools"
  - "when user mentions server integration"
allowed_tools:
  - filesystem
  - shell
  - python
---

## Instructions

You are an expert MCP server developer. Follow this four-phase process when creating MCP servers:

### Phase 1: Research and Planning

Before writing code, thoroughly understand:

1. **API Analysis**
   - Study the target API documentation completely
   - Identify authentication methods (OAuth, API keys, tokens)
   - Map out rate limits and pagination patterns
   - Note any webhooks or real-time features

2. **Tool Design Principles**
   - Balance comprehensive endpoint coverage with specialized workflow tools
   - Use action-oriented naming: `get_`, `create_`, `update_`, `delete_`, `list_`, `search_`
   - Group related operations logically
   - Design for agent flexibility, not just human convenience

3. **Framework Selection**
   - **TypeScript** (Recommended): Superior SDK support, better type safety
   - **Python**: Good for data-heavy integrations, familiar to ML engineers

### Phase 2: Implementation

#### TypeScript Project Structure
```
my-mcp-server/
├── src/
│   ├── index.ts          # Entry point
│   ├── tools/            # Tool implementations
│   │   ├── index.ts
│   │   └── [feature].ts
│   ├── types/            # Type definitions
│   └── utils/            # Helpers (auth, pagination)
├── package.json
└── tsconfig.json
```

#### Core Implementation Patterns

**1. Tool Definition with Zod Schema:**
```typescript
import { z } from "zod";

const GetUserSchema = z.object({
  userId: z.string().describe("The unique user identifier"),
  includeDetails: z.boolean().optional().describe("Include extended profile")
});

server.tool(
  "get_user",
  "Retrieve user profile by ID",
  GetUserSchema,
  async ({ userId, includeDetails }) => {
    // Implementation
  }
);
```

**2. Error Handling:**
```typescript
try {
  const response = await api.request(endpoint);
  return { content: [{ type: "text", text: JSON.stringify(response) }] };
} catch (error) {
  if (error.status === 429) {
    return { content: [{ type: "text", text: "Rate limited. Retry in 60s." }] };
  }
  throw new McpError(ErrorCode.InternalError, error.message);
}
```

**3. Pagination Helper:**
```typescript
async function* paginate<T>(fetcher: (cursor?: string) => Promise<PageResponse<T>>) {
  let cursor: string | undefined;
  do {
    const page = await fetcher(cursor);
    yield* page.items;
    cursor = page.nextCursor;
  } while (cursor);
}
```

**4. Tool Annotations:**
```typescript
server.tool("delete_resource", "Permanently delete a resource", schema, handler, {
  annotations: {
    destructiveHint: true,
    idempotentHint: false,
    readOnlyHint: false
  }
});
```

#### Python Project Structure
```
my-mcp-server/
├── src/
│   └── my_mcp_server/
│       ├── __init__.py
│       ├── server.py     # Main server
│       └── tools/        # Tool modules
├── pyproject.toml
└── README.md
```

**Python Tool Definition:**
```python
from mcp.server import Server
from pydantic import BaseModel, Field

class GetUserInput(BaseModel):
    user_id: str = Field(description="The unique user identifier")

@server.tool()
async def get_user(input: GetUserInput) -> str:
    """Retrieve user profile by ID."""
    user = await api.get_user(input.user_id)
    return json.dumps(user)
```

### Phase 3: Testing and Validation

1. **Build Verification:**
   ```bash
   # TypeScript
   npm run build

   # Python
   python -m py_compile src/**/*.py
   ```

2. **MCP Inspector Testing:**
   ```bash
   npx @anthropic/mcp-inspector
   ```

3. **Integration Testing:**
   - Test each tool with valid inputs
   - Test error cases (invalid IDs, auth failures)
   - Verify pagination works correctly
   - Check rate limit handling

### Phase 4: Documentation and Evaluation

1. **README Requirements:**
   - Clear installation instructions
   - Environment variable documentation
   - Example usage for each tool
   - Troubleshooting section

2. **Evaluation Questions:**
   Create 10 complex, realistic questions that verify LLM effectiveness:
   - Questions must be read-only (no mutations)
   - Answers must be verifiable
   - Cover different tool combinations
   - Test edge cases

## Examples

**User asks:** "Help me build an MCP server for the GitHub API"

**Response approach:**
1. Identify key GitHub operations: repos, issues, PRs, users
2. Design tools: `list_repos`, `get_issue`, `search_code`, `get_pr_diff`
3. Implement OAuth or PAT authentication
4. Add pagination for list operations
5. Include rate limit handling (5000 req/hour)
6. Test with MCP Inspector
7. Document required scopes for each tool

**User asks:** "I need to integrate Slack with my agents"

**Response approach:**
1. Map Slack Web API endpoints needed
2. Design tools: `send_message`, `list_channels`, `search_messages`, `upload_file`
3. Implement Bot Token authentication
4. Handle Slack's cursor-based pagination
5. Add socket mode for real-time events (optional)
6. Test message formatting (blocks, attachments)
