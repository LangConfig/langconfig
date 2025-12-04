# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Dynamic Prompts for Context-Aware Agents (LangGraph v1.0)

Uses the @dynamic_prompt decorator to create system prompts that adapt to:
- User preferences from long-term memory
- Task classification
- Conversation length
- Project context
- Model capabilities

Example Usage:
    from core.utils.dynamic_prompts import (
        personalized_system_prompt,
        classification_based_prompt,
        conversation_aware_prompt
    )

    agent = create_agent(
        model="gpt-4o",
        tools=tools,
        middleware=[
            personalized_system_prompt,  # Adapts to user preferences
            classification_based_prompt,  # Adapts to task type
            conversation_aware_prompt,    # Adapts to conversation length
            TimestampMiddleware(),
            # ... other middleware
        ]
    )
"""

import logging
from typing import Dict, Any
from langchain.agents.middleware import dynamic_prompt, ModelRequest

logger = logging.getLogger(__name__)


# =============================================================================
# Personalized System Prompts
# =============================================================================

@dynamic_prompt
def personalized_system_prompt(request: ModelRequest) -> str:
    """
    Generate personalized system prompt based on user preferences.

    Accesses:
    - runtime.context.user_id: To identify the user
    - runtime.store: To load user preferences from long-term memory
    - request.state: To check conversation state

    Returns:
        Personalized system prompt string

    Example:
        For a user who prefers "concise" style:
        "You are LangConfig. Be concise and direct in your responses."

        For a user who prefers "detailed" style:
        "You are LangConfig. Provide detailed explanations with examples."
    """
    # Check if context is available
    if not hasattr(request.runtime, 'context') or request.runtime.context is None:
        # Return base prompt if no context available
        return "You are LangConfig, an AI software development assistant."

    # ✅ Access runtime context
    user_id = request.runtime.context.user_id if hasattr(request.runtime.context, 'user_id') else None
    project_id = request.runtime.context.project_id if hasattr(request.runtime.context, 'project_id') else None

    # ✅ Access long-term memory (store)
    store = request.runtime.store if hasattr(request.runtime, 'store') else None

    # If no user_id or store, return base prompt
    if not user_id or not store:
        return "You are LangConfig, an AI software development assistant."

    # Load user preferences
    user_prefs = store.get(("users", "preferences"), f"user_{user_id}")

    # Base prompt
    base = "You are LangConfig, an AI software development assistant."

    # Personalize based on user preferences
    if user_prefs and user_prefs.value:
        prefs = user_prefs.value

        # Communication style
        style = prefs.get("communication_style", "balanced")
        if style == "concise":
            base += "\n\n**Communication Style**: Be concise and direct. Get straight to the point without unnecessary explanations."
        elif style == "detailed":
            base += "\n\n**Communication Style**: Provide detailed explanations with examples. Break down complex concepts."
        elif style == "beginner":
            base += "\n\n**Communication Style**: Explain concepts simply, as if to a beginner. Avoid jargon when possible."
        elif style == "expert":
            base += "\n\n**Communication Style**: Assume expert knowledge. Use technical terminology freely."

        # Code style preferences
        code_style = prefs.get("code_style")
        if code_style:
            base += f"\n\n**Code Style**: Follow {code_style} conventions."

        # Language preferences
        preferred_language = prefs.get("language", "en")
        if preferred_language != "en":
            base += f"\n\n**Language**: Respond in {preferred_language}."

    # Add project-specific context
    project_info = store.get(("projects", "info"), f"project_{project_id}")
    if project_info and project_info.value:
        project_data = project_info.value
        tech_stack = project_data.get("tech_stack", [])
        if tech_stack:
            base += f"\n\n**Project Tech Stack**: {', '.join(tech_stack)}"

        architecture = project_data.get("architecture")
        if architecture:
            base += f"\n\n**Project Architecture**: {architecture}"

    logger.debug(f"Generated personalized prompt for user {user_id}")

    return base


@dynamic_prompt
def classification_based_prompt(request: ModelRequest) -> str:
    """
    Adapt system prompt based on task classification.

    Different prompts for:
    - BACKEND tasks
    - FRONTEND tasks
    - DEVOPS_IAC tasks
    - DATABASE tasks
    - etc.

    Returns:
        Classification-specific system prompt
    """
    # ✅ Access state to get classification
    if not hasattr(request, 'state') or request.state is None:
        return ""  # Return empty string if no state available

    classification = request.state.get("classification")

    prompts = {
        "BACKEND": """You are an expert backend engineer specializing in:
- RESTful API design and implementation
- Database optimization and query performance
- Authentication and authorization (OAuth, JWT, RBAC)
- Microservices architecture
- Server-side business logic
- API documentation (OpenAPI/Swagger)

Focus on security, performance, and maintainability.""",

        "FRONTEND": """You are an expert frontend engineer specializing in:
- Modern component-based frameworks (React, Vue, Angular)
- Responsive design and mobile-first development
- Accessibility (WCAG compliance)
- State management (Redux, Zustand, Context API)
- Performance optimization (lazy loading, code splitting)
- User experience and interaction design

Focus on user experience, accessibility, and performance.""",

        "DEVOPS_IAC": """You are a DevOps expert specializing in:
- Infrastructure as Code (Terraform, CloudFormation, Pulumi)
- Container orchestration (Kubernetes, Docker Swarm)
- CI/CD pipelines (GitHub Actions, GitLab CI, Jenkins)
- Cloud platforms (AWS, Azure, GCP)
- Monitoring and observability (Prometheus, Grafana, DataDog)
- Security and compliance automation

Focus on reliability, automation, and security.""",

        "DATABASE": """You are a database expert specializing in:
- Schema design and normalization
- Query optimization and indexing
- Migration strategies
- Replication and high availability
- Performance tuning
- SQL and NoSQL databases

Focus on data integrity, performance, and scalability.""",

        "API": """You are an API design expert specializing in:
- RESTful API best practices
- GraphQL schema design
- API versioning strategies
- Rate limiting and throttling
- API documentation and SDKs
- Authentication patterns

Focus on developer experience, consistency, and documentation.""",

        "TESTING": """You are a testing expert specializing in:
- Test-driven development (TDD)
- Unit, integration, and end-to-end testing
- Test automation frameworks
- Code coverage and quality metrics
- Performance and load testing
- Security testing

Focus on test coverage, maintainability, and reliability.""",

        "DOCUMENTATION": """You are a technical documentation expert specializing in:
- Clear, concise technical writing
- API documentation (OpenAPI, Swagger)
- User guides and tutorials
- Architecture documentation
- Code comments and docstrings
- Markdown and documentation tools

Focus on clarity, completeness, and accessibility."""
    }

    prompt = prompts.get(classification, "You are a full-stack software engineer.")

    logger.debug(f"Generated prompt for classification: {classification}")

    return prompt


@dynamic_prompt
def conversation_aware_prompt(request: ModelRequest) -> str:
    """
    Adapt prompt based on conversation length.

    For long conversations:
    - Encourage conciseness to save context
    - Reference earlier messages explicitly
    - Summarize key points

    For short conversations:
    - Can be more verbose
    - Provide detailed explanations

    Returns:
        Conversation-adapted prompt
    """
    # ✅ Access messages from state
    if not hasattr(request, 'state') or request.state is None:
        return ""  # Return empty string if no state available

    messages = request.state.get("messages", [])
    message_count = len(messages)

    # Calculate approximate token usage
    total_chars = sum(len(getattr(m, 'content', '')) for m in messages)
    estimated_tokens = total_chars // 4  # Rough estimate

    base = ""

    if message_count > 20 or estimated_tokens > 10000:
        base = """**Context Management**: This is a long conversation.
- Be extra concise to preserve context window
- Reference specific earlier points by number if needed
- Prioritize actionable information
- Avoid repeating information already discussed"""

    elif message_count > 10:
        base = """**Context Management**: Moderate conversation length.
- Balance detail with conciseness
- Reference key earlier points when relevant"""

    # Check if approaching context limit
    max_tokens = 128000  # Default
    if hasattr(request.runtime, 'context') and request.runtime.context is not None:
        max_tokens = getattr(request.runtime.context, 'max_tokens', 128000) or 128000

    if estimated_tokens > max_tokens * 0.7:
        base += "\n\n**WARNING**: Approaching context limit. Be very concise."

    if base:
        logger.debug(f"Generated conversation-aware prompt (messages: {message_count}, tokens: ~{estimated_tokens})")

    return base


@dynamic_prompt
def model_aware_prompt(request: ModelRequest) -> str:
    """
    Adapt prompt based on model capabilities.

    Different models have different strengths:
    - GPT-4o: Balanced, good at coding
    - Claude: Excellent at reasoning, analysis
    - GPT-4o-mini: Fast but simpler
    - o1: Deep reasoning, mathematical

    Returns:
        Model-adapted prompt
    """
    # Check if context is available
    if not hasattr(request.runtime, 'context') or request.runtime.context is None:
        return ""  # Return empty if no context

    model_name = getattr(request.runtime.context, 'model_name', '').lower()

    model_instructions = {}

    if "o1" in model_name:
        model_instructions = {
            "strength": "deep reasoning and mathematical analysis",
            "instruction": "Take time to reason through complex problems step by step. Show your reasoning process."
        }
    elif "claude" in model_name:
        model_instructions = {
            "strength": "detailed analysis and explanation",
            "instruction": "Provide thorough analysis and consider multiple perspectives."
        }
    elif "mini" in model_name:
        model_instructions = {
            "strength": "speed and efficiency",
            "instruction": "Focus on clear, direct solutions. Avoid over-complication."
        }
    elif "gpt-4" in model_name or "gpt-5" in model_name:
        model_instructions = {
            "strength": "balanced performance across tasks",
            "instruction": "Provide well-rounded solutions with good code quality."
        }

    if model_instructions:
        return f"""**Model**: Using {model_name}
**Strength**: {model_instructions['strength']}
**Approach**: {model_instructions['instruction']}"""

    return ""


# =============================================================================
# Combined Prompt (uses all strategies)
# =============================================================================

@dynamic_prompt
def comprehensive_dynamic_prompt(request: ModelRequest) -> str:
    """
    Comprehensive dynamic prompt combining all strategies.

    This single prompt function:
    - Personalizes based on user preferences
    - Adapts to task classification
    - Adjusts for conversation length
    - Considers model capabilities

    Use this for a complete adaptive prompt system.
    """
    parts = []

    # 1. Personalization
    personalized = personalized_system_prompt(request)
    if personalized:
        parts.append(personalized)

    # 2. Classification
    classification = classification_based_prompt(request)
    if classification:
        parts.append(classification)

    # 3. Conversation awareness
    conversation = conversation_aware_prompt(request)
    if conversation:
        parts.append(conversation)

    # 4. Model awareness
    model = model_aware_prompt(request)
    if model:
        parts.append(model)

    return "\n\n---\n\n".join(parts)


# =============================================================================
# Prompt List for Easy Import
# =============================================================================

DYNAMIC_PROMPTS = [
    personalized_system_prompt,
    classification_based_prompt,
    conversation_aware_prompt,
    model_aware_prompt,
    comprehensive_dynamic_prompt
]
