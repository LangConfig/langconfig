# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Export Service for DeepAgents.

Generates standalone code and LangConfig import/export formats.
"""

import logging
import json
import os
import zipfile
import base64
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

from models.deep_agent import DeepAgentConfig, DeepAgentTemplate

logger = logging.getLogger(__name__)


class ExportService:
    """Service for exporting DeepAgent configurations as code or interchange format."""

    @staticmethod
    async def export_standalone(
        agent: DeepAgentTemplate,
        config: DeepAgentConfig,
        output_dir: Optional[str] = None
    ) -> str:
        """
        Export agent as standalone repository with all code and dependencies.

        Args:
            agent: DeepAgent template from database
            config: DeepAgent configuration
            output_dir: Optional output directory (default: temp)

        Returns:
            Path to generated .zip file
        """
        logger.info(f"Exporting agent '{agent.name}' as standalone repository")

        # Create output directory
        if output_dir is None:
            output_dir = f"/tmp/deepagent_exports/{agent.id}"

        os.makedirs(output_dir, exist_ok=True)

        # Generate all files
        files = {}

        # 1. README.md
        files["README.md"] = ExportService._generate_readme(agent, config)

        # 2. requirements.txt
        files["requirements.txt"] = ExportService._generate_requirements(config)

        # 3. .env.example
        files[".env.example"] = ExportService._generate_env_example(config)

        # 4. agent_config.json
        files["agent_config.json"] = ExportService._generate_agent_config_json(config)

        # 5. main.py (CLI chat interface)
        files["main.py"] = ExportService._generate_main_py(config)

        # 6. api_server.py (FastAPI server)
        files["api_server.py"] = ExportService._generate_api_server(config)

        # 7. agent/agent.py (DeepAgent initialization)
        files["agent/__init__.py"] = ""
        files["agent/agent.py"] = ExportService._generate_agent_py(config)

        # 8. agent/tools/custom_tools.py (Tool implementations)
        files["agent/tools/__init__.py"] = ""
        files["agent/tools/custom_tools.py"] = ExportService._generate_custom_tools(config)

        # 9. agent/prompts/system_prompt.txt
        files["agent/prompts/system_prompt.txt"] = config.system_prompt

        # 10. tests/test_agent.py
        files["tests/__init__.py"] = ""
        files["tests/test_agent.py"] = ExportService._generate_tests(config)

        # Optional: Docker support
        if config.include_docker:
            files["Dockerfile"] = ExportService._generate_dockerfile(config)
            files["docker-compose.yml"] = ExportService._generate_docker_compose(config)

        # Optional: Chat UI
        if config.include_chat_ui:
            files["ui/index.html"] = ExportService._generate_chat_html(agent, config)
            files["ui/chat.js"] = ExportService._generate_chat_js(config)
            files["ui/styles.css"] = ExportService._generate_chat_css()

        # Write all files
        for file_path, content in files.items():
            full_path = os.path.join(output_dir, file_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)

        # Create zip file
        zip_path = f"{output_dir}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in files.keys():
                full_path = os.path.join(output_dir, file_path)
                zipf.write(full_path, file_path)

        logger.info(f"✓ Standalone export created: {zip_path}")
        return zip_path

    @staticmethod
    async def export_langconfig(
        agent: DeepAgentTemplate,
        config: DeepAgentConfig
    ) -> str:
        """
        Export agent as .langconfig format for import/export between instances.

        Args:
            agent: DeepAgent template from database
            config: DeepAgent configuration

        Returns:
            JSON string in .langconfig format
        """
        logger.info(f"Exporting agent '{agent.name}' as .langconfig format")

        langconfig = {
            "version": "1.0",
            "export_type": "deepagent",
            "exported_at": datetime.utcnow().isoformat(),
            "agent": {
                "id": str(agent.id),
                "name": agent.name,
                "description": agent.description,
                "category": agent.category,
                "model": config.model,
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
                "system_prompt": config.system_prompt,
                "tools": config.tools,
                "native_tools": config.native_tools,
                "cli_tools": config.cli_tools,
                "custom_tools": config.custom_tools,
                "middleware": [m.dict() for m in config.middleware],
                "subagents": [s.dict() for s in config.subagents],
                "backend": config.backend.dict(),
                "guardrails": config.guardrails.dict(),
            },
            "workflow_integration": {
                "can_use_in_workflow": True,
                "recommended_strategies": ["DEEP_RESEARCH_DEEPAGENTS"]
            }
        }

        return json.dumps(langconfig, indent=2)

    # =============================================================================
    # File Generation Methods
    # =============================================================================

    @staticmethod
    def _generate_readme(agent: DeepAgentTemplate, config: DeepAgentConfig) -> str:
        """Generate README.md with setup instructions."""
        return f"""# {agent.name}

{agent.description}

## Overview

This is a DeepAgent exported from LangConfig. It includes:
- DeepAgent with planning capabilities
- Subagent delegation for complex tasks
- Filesystem tools for context management
- Ready-to-use chat interfaces (CLI and API)

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Run CLI Chat**
   ```bash
   python main.py
   ```

4. **Run API Server**
   ```bash
   python api_server.py
   # Access at http://localhost:8000
   ```

## Configuration

Agent configuration is stored in `agent_config.json`. You can modify:
- Model selection
- Temperature and other parameters
- Tools and middleware
- System prompt (in `agent/prompts/system_prompt.txt`)

## Usage

### CLI Chat
```bash
python main.py
```

### API Endpoint
```bash
curl -X POST http://localhost:8000/chat \\
  -H "Content-Type: application/json" \\
  -d '{{"message": "Hello, agent!"}}'
```

### Python Integration
```python
from agent.agent import create_agent

agent = create_agent()
result = agent.invoke({{"messages": [{{"role": "user", "content": "Your message"}}]}})
print(result)
```

## Middleware

This agent includes:
- **Todo List**: Task planning and progress tracking
- **Filesystem**: Context management with auto-eviction
- **Subagents**: Specialized agent delegation

## Testing

```bash
pytest tests/
```

## Customization

1. **Add Custom Tools**: Edit `agent/tools/custom_tools.py`
2. **Modify System Prompt**: Edit `agent/prompts/system_prompt.txt`
3. **Configure Middleware**: Edit `agent_config.json`

## Generated by

LangConfig - https://github.com/your-repo/langconfig

Agent exported on: {datetime.utcnow().isoformat()}
"""

    @staticmethod
    def _generate_requirements(config: DeepAgentConfig) -> str:
        """Generate requirements.txt."""
        return """# Core Dependencies
deepagents>=0.2.5
langchain>=0.3.0
langchain-core>=0.3.0
langchain-anthropic>=0.3.0
langchain-openai>=0.3.0
langgraph>=0.2.0
python-dotenv>=1.0.0

# API Server (optional)
fastapi>=0.115.0
uvicorn[standard]>=0.31.0
pydantic>=2.9.0

# Testing
pytest>=7.4.0
pytest-asyncio>=0.21.0

# Utilities
aiofiles>=24.1.0
httpx>=0.27.0
"""

    @staticmethod
    def _generate_env_example(config: DeepAgentConfig) -> str:
        """Generate .env.example."""
        env_vars = []

        # Add API keys based on model
        if "gpt" in config.model or "openai" in config.model:
            env_vars.append("OPENAI_API_KEY=your_openai_api_key_here")
        if "claude" in config.model or "anthropic" in config.model:
            env_vars.append("ANTHROPIC_API_KEY=your_anthropic_api_key_here")
        if "gemini" in config.model or "google" in config.model:
            env_vars.append("GOOGLE_API_KEY=your_google_api_key_here")

        # Add optional observability
        env_vars.extend([
            "",
            "# Optional: Langfuse for observability",
            "LANGFUSE_PUBLIC_KEY=",
            "LANGFUSE_SECRET_KEY=",
            "LANGFUSE_HOST=https://cloud.langfuse.com"
        ])

        return "\n".join(env_vars) + "\n"

    @staticmethod
    def _generate_agent_config_json(config: DeepAgentConfig) -> str:
        """Generate agent_config.json."""
        return json.dumps(config.dict(), indent=2)

    @staticmethod
    def _generate_main_py(config: DeepAgentConfig) -> str:
        """Generate main.py (CLI chat interface)."""
        return '''#!/usr/bin/env python3
"""
CLI Chat Interface for DeepAgent.
"""

import asyncio
from agent.agent import create_agent


async def main():
    """Main CLI chat loop."""
    print("=" * 60)
    print("DeepAgent CLI Chat")
    print("=" * 60)
    print("Type 'exit' or 'quit' to end the conversation\\n")

    # Create agent
    agent = create_agent()

    # Chat loop
    conversation_history = []

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if not user_input:
                continue

            # Add to history
            conversation_history.append({
                "role": "user",
                "content": user_input
            })

            # Invoke agent
            print("\\nAgent: ", end="", flush=True)
            result = agent.invoke({
                "messages": conversation_history
            })

            # Extract response
            if hasattr(result, "messages") and result.messages:
                response = result.messages[-1].content
            elif isinstance(result, dict) and "messages" in result:
                response = result["messages"][-1].content
            else:
                response = str(result)

            print(response)
            print()

            # Add to history
            conversation_history.append({
                "role": "assistant",
                "content": response
            })

        except KeyboardInterrupt:
            print("\\n\\nGoodbye!")
            break
        except Exception as e:
            print(f"\\nError: {e}\\n")


if __name__ == "__main__":
    asyncio.run(main())
'''

    @staticmethod
    def _generate_api_server(config: DeepAgentConfig) -> str:
        """Generate api_server.py (FastAPI server)."""
        return '''"""
FastAPI Server for DeepAgent.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import uvicorn

from agent.agent import create_agent

app = FastAPI(title="DeepAgent API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize agent
agent = create_agent()


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    conversation_history: List[Dict[str, str]] = []


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    conversation_history: List[Dict[str, str]]


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Chat endpoint."""
    try:
        # Build messages
        messages = request.conversation_history + [
            {"role": "user", "content": request.message}
        ]

        # Invoke agent
        result = agent.invoke({"messages": messages})

        # Extract response
        if hasattr(result, "messages") and result.messages:
            response_text = result.messages[-1].content
        elif isinstance(result, dict) and "messages" in result:
            response_text = result["messages"][-1].content
        else:
            response_text = str(result)

        # Update history
        updated_history = messages + [
            {"role": "assistant", "content": response_text}
        ]

        return ChatResponse(
            response=response_text,
            conversation_history=updated_history
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

    @staticmethod
    def _generate_agent_py(config: DeepAgentConfig) -> str:
        """Generate agent/agent.py (DeepAgent initialization)."""
        return f'''"""
DeepAgent initialization and configuration.
"""

import os
import json
from pathlib import Path
from deepagents import create_deep_agent
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def load_config():
    """Load agent configuration from JSON."""
    config_path = Path(__file__).parent.parent / "agent_config.json"
    with open(config_path, 'r') as f:
        return json.load(f)


def load_system_prompt():
    """Load system prompt from file."""
    prompt_path = Path(__file__).parent / "prompts" / "system_prompt.txt"
    with open(prompt_path, 'r') as f:
        return f.read()


def create_agent():
    """Create and configure the DeepAgent."""
    # Load configuration
    config = load_config()

    # Load system prompt
    system_prompt = load_system_prompt()

    # Create agent
    agent = create_deep_agent(
        model=config["model"],
        system_prompt=system_prompt,
        # Additional configuration from config
    )

    return agent
'''

    @staticmethod
    def _generate_custom_tools(config: DeepAgentConfig) -> str:
        """Generate agent/tools/custom_tools.py."""
        return '''"""
Custom tools for the DeepAgent.

Add your own tools here.
"""

from langchain_core.tools import StructuredTool


def example_tool(query: str) -> str:
    """
    Example custom tool.

    Args:
        query: Input query

    Returns:
        Tool result
    """
    return f"Processed: {query}"


# Export tools
CUSTOM_TOOLS = [
    StructuredTool.from_function(
        func=example_tool,
        name="example_tool",
        description="An example custom tool"
    )
]
'''

    @staticmethod
    def _generate_tests(config: DeepAgentConfig) -> str:
        """Generate tests/test_agent.py."""
        return '''"""
Tests for DeepAgent.
"""

import pytest
from agent.agent import create_agent


def test_agent_creation():
    """Test that agent can be created."""
    agent = create_agent()
    assert agent is not None


def test_agent_basic_query():
    """Test basic agent query."""
    agent = create_agent()
    result = agent.invoke({
        "messages": [{"role": "user", "content": "Hello!"}]
    })
    assert result is not None
'''

    @staticmethod
    def _generate_dockerfile(config: DeepAgentConfig) -> str:
        """Generate Dockerfile."""
        return """FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "api_server.py"]
"""

    @staticmethod
    def _generate_docker_compose(config: DeepAgentConfig) -> str:
        """Generate docker-compose.yml."""
        return """version: '3.8'

services:
  deepagent:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./agent:/app/agent
"""

    @staticmethod
    def _generate_chat_html(agent: DeepAgentTemplate, config: DeepAgentConfig) -> str:
        """Generate ui/index.html."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{agent.name} - Chat</title>
    <link rel="stylesheet" href="styles.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>{agent.name}</h1>
            <p>{agent.description}</p>
        </header>

        <div id="chat-container">
            <div id="messages"></div>
            <div class="input-container">
                <input type="text" id="message-input" placeholder="Type your message..." />
                <button id="send-button">Send</button>
            </div>
        </div>
    </div>

    <script src="chat.js"></script>
</body>
</html>
"""

    @staticmethod
    def _generate_chat_js(config: DeepAgentConfig) -> str:
        """Generate ui/chat.js."""
        return """const messagesDiv = document.getElementById('messages');
const messageInput = document.getElementById('message-input');
const sendButton = document.getElementById('send-button');

let conversationHistory = [];

function addMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    messageDiv.textContent = content;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

async function sendMessage() {
    const message = messageInput.value.trim();
    if (!message) return;

    addMessage('user', message);
    messageInput.value = '';
    sendButton.disabled = true;

    try {
        const response = await fetch('http://localhost:8000/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                message: message,
                conversation_history: conversationHistory
            })
        });

        const data = await response.json();
        addMessage('assistant', data.response);
        conversationHistory = data.conversation_history;
    } catch (error) {
        addMessage('error', 'Error: ' + error.message);
    } finally {
        sendButton.disabled = false;
        messageInput.focus();
    }
}

sendButton.addEventListener('click', sendMessage);
messageInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendMessage();
});
"""

    @staticmethod
    def _generate_chat_css() -> str:
        """Generate ui/styles.css."""
        return """* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background: #f5f5f5;
}

.container {
    max-width: 800px;
    margin: 0 auto;
    height: 100vh;
    display: flex;
    flex-direction: column;
}

header {
    background: white;
    padding: 20px;
    border-bottom: 1px solid #e0e0e0;
}

h1 {
    font-size: 24px;
    margin-bottom: 8px;
}

#chat-container {
    flex: 1;
    display: flex;
    flex-direction: column;
    background: white;
    overflow: hidden;
}

#messages {
    flex: 1;
    overflow-y: auto;
    padding: 20px;
}

.message {
    margin-bottom: 16px;
    padding: 12px;
    border-radius: 8px;
    max-width: 80%;
}

.message.user {
    background: #007bff;
    color: white;
    margin-left: auto;
}

.message.assistant {
    background: #f0f0f0;
    color: #333;
}

.message.error {
    background: #f44336;
    color: white;
}

.input-container {
    display: flex;
    padding: 20px;
    border-top: 1px solid #e0e0e0;
}

#message-input {
    flex: 1;
    padding: 12px;
    border: 1px solid #ddd;
    border-radius: 4px;
    font-size: 14px;
}

#send-button {
    margin-left: 12px;
    padding: 12px 24px;
    background: #007bff;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
}

#send-button:hover {
    background: #0056b3;
}

#send-button:disabled {
    background: #ccc;
    cursor: not-allowed;
}
"""
