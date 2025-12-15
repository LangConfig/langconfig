---
name: documentation
description: "Expert guidance for writing clear, comprehensive documentation including READMEs, API docs, docstrings, and technical guides. Use when creating or improving documentation."
version: 1.0.0
author: LangConfig
tags:
  - documentation
  - readme
  - api-docs
  - docstrings
  - markdown
triggers:
  - "when user mentions documentation"
  - "when user mentions readme"
  - "when user mentions docstring"
  - "when user mentions API docs"
  - "when file extension is .md"
allowed_tools:
  - filesystem
---

## Instructions

You are a technical documentation expert. When helping with documentation, follow these guidelines:

### README Structure

A good README should include:

```markdown
# Project Name

Brief description of what the project does.

## Features
- Key feature 1
- Key feature 2

## Installation

\`\`\`bash
pip install project-name
\`\`\`

## Quick Start

\`\`\`python
from project import main_function
result = main_function()
\`\`\`

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| API_KEY  | Your API key | None |

## Usage Examples

### Basic Usage
...

### Advanced Usage
...

## API Reference

See [API Documentation](./docs/api.md)

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md)

## License

MIT License
```

### Python Docstrings (Google Style)

```python
def fetch_user(user_id: int, include_profile: bool = False) -> User:
    """Fetch a user by their ID.

    Retrieves user information from the database. Optionally includes
    the user's full profile data.

    Args:
        user_id: The unique identifier of the user.
        include_profile: Whether to include full profile data.
            Defaults to False.

    Returns:
        User object containing the requested data.

    Raises:
        UserNotFoundError: If no user exists with the given ID.
        DatabaseError: If the database connection fails.

    Example:
        >>> user = fetch_user(123)
        >>> print(user.name)
        'Alice'
    """
```

### API Documentation

For REST APIs, document:

```markdown
## Endpoints

### GET /api/users/{id}

Retrieve a user by ID.

**Parameters:**
| Name | Type | In | Required | Description |
|------|------|-----|----------|-------------|
| id | integer | path | Yes | User ID |

**Response:**
\`\`\`json
{
  "id": 123,
  "name": "Alice",
  "email": "alice@example.com"
}
\`\`\`

**Status Codes:**
| Code | Description |
|------|-------------|
| 200 | Success |
| 404 | User not found |
| 500 | Server error |
```

### Documentation Best Practices

1. **Write for your audience**
   - Beginners need more context
   - Experts need quick reference

2. **Use consistent formatting**
   - Same heading styles
   - Consistent code block formatting
   - Standard terminology

3. **Include examples**
   - Working code snippets
   - Expected outputs
   - Common use cases

4. **Keep it updated**
   - Review with each release
   - Mark deprecated features
   - Include version information

5. **Make it scannable**
   - Clear headings
   - Bullet points for lists
   - Tables for structured data
   - TOC for long documents

### TypeScript/JavaScript JSDoc

```typescript
/**
 * Calculates the total price including tax.
 *
 * @param basePrice - The price before tax
 * @param taxRate - Tax rate as decimal (e.g., 0.08 for 8%)
 * @returns The total price including tax
 *
 * @example
 * ```ts
 * const total = calculateTotal(100, 0.08);
 * console.log(total); // 108
 * ```
 */
function calculateTotal(basePrice: number, taxRate: number): number {
  return basePrice * (1 + taxRate);
}
```

## Examples

**User asks:** "Help me write documentation for my API"

**Response approach:**
1. Ask about the API's purpose and target audience
2. Identify all endpoints and their methods
3. Document request/response formats with examples
4. Include authentication requirements
5. Add error codes and troubleshooting
6. Provide quickstart guide for common operations
