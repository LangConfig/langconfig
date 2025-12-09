/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';

export default function BestPracticesTab() {
  const [expandedSection, setExpandedSection] = useState<string | null>('agent-design');

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>
            Best Practices & Code Examples
          </h2>
          <p className="text-base" style={{ color: 'var(--color-text-muted)' }}>
            Production-ready patterns for building reliable AI agents
          </p>
        </div>

        {/* Best Practice Sections */}
        <div className="space-y-3">
          {/* Section 1: Agent Design Principles */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('agent-design')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">folder_managed</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  Agent Design Principles
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'agent-design' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'agent-design' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Single Responsibility Principle
                  </h4>
                  <p className="leading-relaxed mb-3">
                    Each agent should have one clear responsibility. Don't create a "do everything" agent. Instead, compose specialized agents into workflows.
                  </p>

                  <div className="space-y-3">
                    <div>
                      <p className="text-xs font-semibold mb-1 text-red-600 dark:text-red-400">❌ Avoid:</p>
                      <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                        {`# One agent trying to do everything
agent = Agent(
    system_prompt="You are an AI that researches topics,
    writes code, deploys to production, monitors systems,
    handles customer support, and manages finances..."
)`}</pre>
                    </div>

                    <div>
                      <p className="text-xs font-semibold mb-1 text-green-600 dark:text-green-400">✓ Better:</p>
                      <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                        {`# Specialized agents with clear responsibilities
research_agent = Agent(
    name="Research Agent",
    system_prompt="You are a research specialist. Search for
    information, analyze sources, and summarize findings.",
    tools=["web_search", "web_fetch"]
)

code_agent = Agent(
    name="Code Agent",
    system_prompt="You are a Python developer. Write clean,
    tested code following best practices.",
    tools=["read_file", "write_file", "code_execution"]
)

# Combine in a workflow
workflow = StateGraph()
workflow.add_node("research", research_agent)
workflow.add_node("code", code_agent)
workflow.add_edge("research", "code")`}</pre>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Clear Naming Conventions
                  </h4>
                  <p className="leading-relaxed mb-3">
                    Use descriptive names that indicate the agent's purpose and scope.
                  </p>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`# Good naming examples
customer_support_agent        # Clear what it does
github_pr_reviewer           # Specific domain
data_quality_checker          # Precise responsibility
email_sentiment_analyzer      # Clear input and output

# Poor naming examples
agent1                        # No information
helper                        # Too generic
ai_bot                        # Vague purpose`}</pre>
                </div>
              </div>
            )}
          </div>

          {/* Section 2: System Prompt Patterns */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('prompts')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">description</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  System Prompt Patterns
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'prompts' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'prompts' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Structured System Prompt Template
                  </h4>
                  <p className="leading-relaxed mb-3">
                    Follow this template for consistent, effective system prompts:
                  </p>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`system_prompt = """
# ROLE
You are an expert [DOMAIN] specialist with [X] years of experience.

# TASK
Your job is to [PRIMARY RESPONSIBILITY]. Specifically:
1. [Sub-task 1]
2. [Sub-task 2]
3. [Sub-task 3]

# CONTEXT
- You have access to [AVAILABLE INFORMATION]
- The user is [USER CONTEXT]
- Current constraints: [LIMITATIONS]

# OUTPUT FORMAT
Respond in the following structure:
{
  "analysis": "Your analysis here",
  "recommendation": "Your recommendation",
  "confidence": "high|medium|low",
  "next_steps": ["step1", "step2"]
}

# CONSTRAINTS
- DO NOT [FORBIDDEN ACTION]
- ALWAYS [REQUIRED ACTION]
- If uncertain, [FALLBACK BEHAVIOR]

# EXAMPLES
Input: [Example input]
Output: [Example output]
"""
`}</pre>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Real Example: Code Review Agent
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`code_review_prompt = """
# ROLE
You are a senior software engineer specializing in Python code review.

# TASK
Review Python code for:
1. Code quality and maintainability
2. Performance issues
3. Security vulnerabilities
4. Best practice violations

# OUTPUT FORMAT
{
  "summary": "Brief overall assessment",
  "issues": [
    {"severity": "high|medium|low", "line": 42, "issue": "...", "fix": "..."}
  ],
  "suggestions": ["improvement 1", "improvement 2"],
  "rating": "1-10"
}

# CONSTRAINTS
- Focus on actionable feedback
- Cite specific line numbers
- Suggest concrete fixes, not just problems
- Be constructive, not harsh

# STANDARDS
- Follow PEP 8 style guide
- Prefer readability over cleverness
- Flag security issues (SQL injection, XSS, etc.)
- Check for proper error handling
"""`}</pre>
                </div>
              </div>
            )}
          </div>

          {/* Section 3: Error Handling & Retries */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('errors')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">error</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  Error Handling & Retries
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'errors' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'errors' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Retry Pattern with Exponential Backoff
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10)
)
def call_llm_with_retry(prompt: str):
    """
    Retry LLM calls with exponential backoff.
    Waits: 2s, 4s, 8s between retries
    """
    try:
        return llm.invoke(prompt)
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        raise  # Will trigger retry`}</pre>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Graceful Degradation
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`def get_weather(city: str) -> dict:
    """Get weather with fallback behavior."""
    try:
        # Try primary API
        return weather_api.get(city)
    except APIError:
        try:
            # Fallback to secondary API
            return backup_weather_api.get(city)
        except:
            # Return cached data or reasonable default
            return {
                "city": city,
                "status": "unavailable",
                "message": "Weather data temporarily unavailable"
            }`}</pre>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Tool Call Validation
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`def validate_tool_call(tool_name: str, args: dict) -> bool:
    """Validate tool arguments before execution."""

    # Check required fields
    required = TOOL_SCHEMAS[tool_name]["required"]
    if not all(field in args for field in required):
        raise ValueError(f"Missing required fields: {required}")

    # Validate types
    for field, value in args.items():
        expected_type = TOOL_SCHEMAS[tool_name]["properties"][field]["type"]
        if not isinstance(value, TYPE_MAP[expected_type]):
            raise TypeError(f"{field} must be {expected_type}")

    # Range checks
    if tool_name == "web_search" and args.get("max_results", 0) > 100:
        args["max_results"] = 100  # Cap at reasonable limit

    return True`}</pre>
                </div>
              </div>
            )}
          </div>

          {/* Section 4: Testing Strategies */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('testing')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">science</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  Testing Strategies
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'testing' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'testing' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Unit Test Example
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`import pytest
from unittest.mock import Mock, patch

def test_agent_with_mocked_llm():
    """Test agent behavior with mocked LLM responses."""

    # Mock the LLM
    mock_llm = Mock()
    mock_llm.invoke.return_value = "Paris is the capital of France"

    # Create agent with mocked LLM
    agent = Agent(llm=mock_llm, tools=[])

    # Test
    result = agent.run("What is the capital of France?")

    # Assertions
    assert "Paris" in result
    mock_llm.invoke.assert_called_once()
    assert "capital of France" in mock_llm.invoke.call_args[0][0]

def test_tool_call_parsing():
    """Test that agent correctly parses tool calls."""

    llm_response = '''
    I need to search for this information.
    Action: web_search
    Action Input: {"query": "LangChain documentation"}
    '''

    tool_call = parse_tool_call(llm_response)

    assert tool_call["tool"] == "web_search"
    assert tool_call["args"]["query"] == "LangChain documentation"`}</pre>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Integration Test with Real LLM
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`@pytest.mark.integration
def test_full_workflow():
    """Test complete workflow with real LLM (slower, more expensive)."""

    # Use cheaper model for testing
    test_agent = Agent(
        model="gpt-4o-mini",  # Cheaper for testing
        temperature=0,  # Deterministic
        tools=["calculator"]
    )

    result = test_agent.run("What is 15 * 23?")

    # Check result contains answer
    assert "345" in result

    # Check tool was called
    assert len(test_agent.tool_calls) == 1
    assert test_agent.tool_calls[0]["tool"] == "calculator"`}</pre>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Evaluation Dataset Pattern
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`# test_cases.json
test_cases = [
    {
        "input": "What's the weather in Tokyo?",
        "expected_tool": "weather_api",
        "expected_city": "Tokyo"
    },
    {
        "input": "Calculate 25% of 80",
        "expected_tool": "calculator",
        "expected_result": 20
    }
]

def evaluate_agent(agent, test_cases):
    """Run agent against evaluation dataset."""
    results = []

    for test in test_cases:
        try:
            output = agent.run(test["input"])
            passed = validate_output(output, test)
            results.append({"test": test["input"], "passed": passed})
        except Exception as e:
            results.append({"test": test["input"], "passed": False, "error": str(e)})

    # Calculate metrics
    accuracy = sum(r["passed"] for r in results) / len(results)
    return {"accuracy": accuracy, "results": results}`}</pre>
                </div>
              </div>
            )}
          </div>

          {/* Section 5: Production Deployment */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('production')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">rocket_launch</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  Production Deployment
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'production' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'production' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Environment Configuration
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`# config.py - Environment-based configuration
import os
from pydantic import BaseSettings

class Settings(BaseSettings):
    # API Keys (from environment variables)
    openai_api_key: str = os.getenv("OPENAI_API_KEY")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY")

    # Model selection by environment
    model: str = os.getenv(
        "LLM_MODEL",
        "gpt-4o-mini" if os.getenv("ENV") == "dev" else "gpt-4o"
    )

    # Rate limiting
    max_requests_per_minute: int = int(os.getenv("RATE_LIMIT", "60"))

    # Monitoring
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    enable_tracing: bool = os.getenv("EN ABLE_TRACING", "false") == "true"

    class Config:
        env_file = ".env"

settings = Settings()`}</pre>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Monitoring & Logging
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`import structlog
from datetime import datetime

logger = structlog.get_logger()

def run_agent_with_monitoring(agent, user_input: str):
    """Run agent with comprehensive monitoring."""
    start_time = datetime.now()

    try:
        # Log request
        logger.info(
            "agent_request",
            agent=agent.name,
            input_length=len(user_input),
            timestamp=start_time.isoformat()
        )

        # Execute
        result = agent.run(user_input)

        # Log success metrics
        duration = (datetime.now() - start_time).total_seconds()
        logger.info(
            "agent_success",
            agent=agent.name,
            duration_seconds=duration,
            output_length=len(result),
            tool_calls=len(agent.tool_calls),
            tokens_used=agent.last_run_tokens
        )

        return result

    except Exception as e:
        # Log failure
        logger.error(
            "agent_failure",
            agent=agent.name,
            error=str(e),
            error_type=type(e).__name__,
            duration=(datetime.now() - start_time).total_seconds()
        )
        raise`}</pre>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Cost Tracking
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`from dataclasses import dataclass
from typing import Dict

@dataclass
class CostTracker:
    """Track LLM costs across runs."""

    # Pricing per 1M tokens (as of 2024)
    PRICING: Dict[str, Dict[str, float]] = {
        "gpt-4o": {"input": 5.00, "output": 15.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        "claude-3-5-sonnet": {"input": 3.00, "output": 15.00}
    }

    total_cost: float = 0.0
    runs: int = 0

    def track_run(self, model: str, input_tokens: int, output_tokens: int):
        """Calculate and track cost of a run."""
        if model not in self.PRICING:
            logger.warning(f"Unknown model pricing: {model}")
            return

        input_cost = (input_tokens / 1_000_000) * self.PRICING[model]["input"]
        output_cost = (output_tokens / 1_000_000) * self.PRICING[model]["output"]
        run_cost = input_cost + output_cost

        self.total_cost += run_cost
        self.runs += 1

        logger.info(
            "cost_tracked",
            model=model,
            run_cost=round(run_cost, 4),
            total_cost=round(self.total_cost, 4),
            total_runs=self.runs
        )

        return run_cost

# Usage
cost_tracker = CostTracker()
cost = cost_tracker.track_run("gpt-4o", input_tokens=1000, output_tokens=500)`}</pre>
                </div>
              </div>
            )}
          </div>

          {/* Section 6: Performance Optimization */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('performance')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">speed</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  Performance Optimization
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'performance' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'performance' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Prompt Caching (Anthropic)
                  </h4>
                  <p className="leading-relaxed mb-3">
                    Cache frequently-used system prompts to reduce latency and costs by up to 90%.
                  </p>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`from anthropic import Anthropic

client = Anthropic()

# Mark blocks for caching with cache_control
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    system=[
        {
            "type": "text",
            "text": "You are an expert Python developer...",
            "cache_control": {"type": "ephemeral"}  # Cache this
        }
    ],
    messages=[{"role": "user", "content": "Write a function..."}]
)

# Subsequent calls reuse cached system prompt
# 90% cost reduction on cached tokens!`}</pre>
                  <a
                    href="https://docs.anthropic.com/claude/docs/prompt-caching"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline text-xs mt-2"
                  >
                    <span>Learn more about prompt caching</span>
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Parallel Tool Execution
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`import asyncio
from typing import List

async def execute_tools_parallel(tool_calls: List[dict]):
    """Execute multiple tool calls in parallel."""

    async def run_tool(tool_call):
        tool_name = tool_call["tool"]
        args = tool_call["args"]
        return await TOOLS[tool_name].arun(**args)

    # Run all tools concurrently
    results = await asyncio.gather(
        *[run_tool(tc) for tc in tool_calls],
        return_exceptions=True  # Don't fail if one tool errors
    )

    return results

# Example: Search multiple sources simultaneously
tool_calls = [
    {"tool": "web_search", "args": {"query": "LangChain"}},
    {"tool": "web_search", "args": {"query": "LangGraph"}},
    {"tool": "github_search", "args": {"query": "langchain"}}
]

results = await execute_tools_parallel(tool_calls)
# All 3 searches run concurrently instead of sequentially!`}</pre>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Streaming Responses
                  </h4>
                  <pre className="text-xs p-3 rounded bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark" style={{ color: 'var(--color-text-primary)' }}>
                    {`from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

# Enable streaming for better UX
llm = ChatOpenAI(
    model_name="gpt-4o",
    streaming=True,
    callbacks=[StreamingStdOutCallbackHandler()]
)

# For custom handling
class CustomStreamHandler(BaseCallbackHandler):
    def on_llm_new_token(self, token: str, **kwargs):
        # Send token to frontend via websocket
        websocket.send(token)

    def on_llm_end(self, response, **kwargs):
        websocket.send({"type": "complete"})

agent = Agent(llm=llm, callbacks=[CustomStreamHandler()])`}</pre>
                </div>
              </div>
            )}
          </div>

          {/* Section 7: Implementing Middleware */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('middleware')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">layers</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  7. Implementing Middleware
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'middleware' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'middleware' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <p className="leading-relaxed">
                  Middleware allows you to wrap agents or tools with additional logic. This example shows how to implement a logging middleware using LangChain's <code>RunnableBinding</code>.
                </p>

                <div className="relative group">
                  <div className="absolute right-2 top-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={() => navigator.clipboard.writeText(`from langchain_core.runnables import RunnableBinding
from langchain_core.messages import BaseMessage
import structlog

logger = structlog.get_logger()

class LoggingMiddleware(RunnableBinding):
    """Middleware to log input and output of any Runnable."""

    def __init__(self, bound):
        super().__init__(bound=bound)

    def invoke(self, input, config=None, **kwargs):
        # Log the input
        logger.info("middleware_input", input_type=type(input).__name__, input_preview=str(input)[:100])

        try:
            # Execute the bound runnable (agent/tool)
            output = self.bound.invoke(input, config, **kwargs)

            # Log the output
            logger.info("middleware_output", output_type=type(output).__name__)
            return output

        except Exception as e:
            # Log errors
            logger.error("middleware_error", error=str(e))
            raise e

# Usage: Wrap your agent with the middleware
# agent = create_react_agent(model, tools)
# agent_with_logging = LoggingMiddleware(bound=agent)

# Now invoke the wrapped agent
# result = agent_with_logging.invoke({"messages": [HumanMessage(content="Hello")]})`)}
                      className="p-1.5 rounded-md bg-gray-800 text-gray-400 hover:text-white hover:bg-gray-700 transition-colors"
                      title="Copy code"
                    >
                      <span className="material-symbols-outlined text-sm">content_copy</span>
                    </button>
                  </div>
                  <pre className="p-4 rounded-lg bg-gray-900 text-gray-100 overflow-x-auto font-mono text-xs leading-relaxed border border-gray-800">
                    <code>{`from langchain_core.runnables import RunnableBinding
from langchain_core.messages import BaseMessage
import structlog

logger = structlog.get_logger()

class LoggingMiddleware(RunnableBinding):
    """Middleware to log input and output of any Runnable."""

    def __init__(self, bound):
        super().__init__(bound=bound)

    def invoke(self, input, config=None, **kwargs):
        # Log the input
        logger.info("middleware_input", input_type=type(input).__name__, input_preview=str(input)[:100])

        try:
            # Execute the bound runnable (agent/tool)
            output = self.bound.invoke(input, config, **kwargs)

            # Log the output
            logger.info("middleware_output", output_type=type(output).__name__)
            return output

        except Exception as e:
            # Log errors
            logger.error("middleware_error", error=str(e))
            raise e

# Usage: Wrap your agent with the middleware
# agent = create_react_agent(model, tools)
# agent_with_logging = LoggingMiddleware(bound=agent)

# Now invoke the wrapped agent
# result = agent_with_logging.invoke({"messages": [HumanMessage(content="Hello")]})`}</code>
                  </pre>
                </div>

                <div className="p-3 rounded bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30">
                  <div className="flex gap-2">
                    <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 text-sm">lightbulb</span>
                    <p className="text-xs text-blue-800 dark:text-blue-300">
                      <strong>Tip:</strong> You can chain multiple middleware layers (e.g., Logging → Guardrails → RateLimit → Agent) to build robust pipelines.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Additional Tips */}
        <div className="mt-8 p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-gradient-to-br from-primary/5 to-transparent">
          <h3 className="font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
            Quick Reference
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
            <div>
              <h4 className="font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>Development</h4>
              <ul className="space-y-1" style={{ color: 'var(--color-text-muted)' }}>
                <li>• Use gpt-4o-mini for testing</li>
                <li>• Set temperature=0 for determinism</li>
                <li>• Mock LLMs in unit tests</li>
                <li>• Version your prompts</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-1" style={{ color: 'var(--color-text-primary)' }}>Production</h4>
              <ul className="space-y-1" style={{ color: 'var(--color-text-muted)' }}>
                <li>• Implement retry logic</li>
                <li>• Monitor token usage</li>
                <li>• Use prompt caching</li>
                <li>• Log all agent decisions</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
