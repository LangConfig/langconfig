# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Structured Output Schemas for LangConfig Agents

Implements type-safe Pydantic schemas for agent outputs using LangChain's
structured output generation. This ensures agents return well-formatted,
validated responses that can be directly used in code.

Benefits:
- Type safety (no parsing errors)
- Validation (ensures data quality)
- Consistency (same format every time)
- Integration (easy to use in downstream code)
- Documentation (self-documenting schemas)

Example:
    >>> from core.utils.structured_outputs import CodeReviewOutput
    >>> agent = create_agent_with_structured_output(
    ...     template_id="code_reviewer",
    ...     output_schema=CodeReviewOutput
    ... )
    >>> result = await agent.ainvoke({"messages": [HumanMessage(...)]})
    >>> review = result.parsed  # Type: CodeReviewOutput
    >>> print(review.severity)  # "high" | "medium" | "low"
"""

import logging
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# Jira Ticket Generation Outputs
# =============================================================================

class JiraRequirement(BaseModel):
    """A single requirement for the Jira ticket."""

    type: Literal["functional", "non-functional"] = Field(
        description="Type of requirement"
    )
    description: str = Field(
        description="Detailed requirement description"
    )


class JiraAcceptanceCriteria(BaseModel):
    """Acceptance criteria in Given/When/Then format."""

    scenario_name: str = Field(
        description="Name of the scenario being tested"
    )
    given: str = Field(
        description="Initial context or preconditions"
    )
    when: str = Field(
        description="Action or event that triggers behavior"
    )
    then: str = Field(
        description="Expected outcome or result"
    )


class JiraTestingNote(BaseModel):
    """Testing instructions for QA."""

    environment: str = Field(
        description="Testing environment URL or name"
    )
    steps: List[str] = Field(
        description="Verification steps for QA"
    )
    validation_points: List[str] = Field(
        default_factory=list,
        description="Key points to validate"
    )


class JiraDependency(BaseModel):
    """Related tickets or dependencies."""

    ticket_id: str = Field(
        description="Related ticket ID (e.g., BE-312, UI-208)"
    )
    relationship: Literal["depends_on", "related_to", "blocks", "blocked_by"] = Field(
        description="Type of relationship"
    )
    description: Optional[str] = Field(
        None,
        description="Optional description of the relationship"
    )


class JiraTechnicalNote(BaseModel):
    """Technical implementation notes for developers."""

    area: str = Field(
        description="Technical area (e.g., 'Frontend', 'Backend', 'Database')"
    )
    notes: List[str] = Field(
        description="Implementation notes and considerations"
    )


class JiraTicketOutput(BaseModel):
    """
    Structured output for Jira ticket generation workflow.

    Follows the standard Jira ticket format with all required sections
    for proper ticket creation and tracking.
    """

    # :compass: Title
    title: str = Field(
        description="Short, clear, action-based title (Example: Implement Reverse Bonding Curve toggle)"
    )

    # :memo: Description / Context
    problem_statement: str = Field(
        description="What problem are we solving?"
    )
    user_value: str = Field(
        description="Why does it matter? (user value / business value)"
    )
    feature_context: str = Field(
        description="Where does it fit? (feature, release, milestone, etc.)"
    )

    # :dart: Scope / Requirements
    functional_requirements: List[JiraRequirement] = Field(
        description="Functional requirements - what needs to be built"
    )
    non_functional_requirements: List[JiraRequirement] = Field(
        default_factory=list,
        description="Non-functional requirements (performance, reliability, etc.)"
    )

    # :white_check_mark: Acceptance Criteria
    acceptance_criteria: List[JiraAcceptanceCriteria] = Field(
        description="QA's playbook - Given/When/Then scenarios"
    )

    # :test_tube: Testing Notes
    testing_notes: JiraTestingNote = Field(
        description="How QA can verify correctness"
    )

    # :link: Dependencies / Related Tickets
    dependencies: List[JiraDependency] = Field(
        default_factory=list,
        description="Related work, blockers, or linked stories"
    )

    # :paperclip: Attachments / References
    attachments: List[str] = Field(
        default_factory=list,
        description="Supporting materials (Figma, docs, screenshots, etc.)"
    )

    # :brain: Technical Notes
    technical_notes: List[JiraTechnicalNote] = Field(
        default_factory=list,
        description="Implementation guidance for developers"
    )

    # Metadata
    priority: Literal["critical", "high", "medium", "low"] = Field(
        default="medium",
        description="Ticket priority level"
    )
    story_points: Optional[int] = Field(
        None,
        description="Estimated story points (1, 2, 3, 5, 8, 13, etc.)"
    )
    labels: List[str] = Field(
        default_factory=list,
        description="Jira labels for categorization"
    )


class JiraTicketBatchOutput(BaseModel):
    """Output for generating multiple Jira tickets at once."""

    tickets: List[JiraTicketOutput] = Field(
        description="List of generated Jira tickets"
    )
    summary: str = Field(
        description="Overall summary of the batch generation"
    )
    total_tickets: int = Field(
        description="Total number of tickets generated"
    )


# =============================================================================
# Code Review Agent Outputs
# =============================================================================

class CodeIssue(BaseModel):
    """A single code issue found during review."""

    severity: Literal["critical", "high", "medium", "low", "info"] = Field(
        description="Severity level of the issue"
    )
    category: Literal["bug", "security", "performance", "maintainability", "style", "documentation"] = Field(
        description="Category of the issue"
    )
    file_path: str = Field(description="Path to the file containing the issue")
    line_number: Optional[int] = Field(None, description="Line number where issue occurs")
    description: str = Field(description="Clear description of the issue")
    recommendation: str = Field(description="Recommended fix or improvement")
    code_snippet: Optional[str] = Field(None, description="Relevant code snippet")


class TestResults(BaseModel):
    """Results from running tests."""

    tests_run: int = Field(default=0, description="Total number of tests executed")
    tests_passed: int = Field(default=0, description="Number of tests that passed")
    tests_failed: int = Field(default=0, description="Number of tests that failed")
    tests_skipped: int = Field(default=0, description="Number of tests skipped")
    duration_seconds: float = Field(default=0.0, description="Total test execution time")
    framework: Optional[str] = Field(None, description="Test framework used (pytest, jest, etc.)")
    summary: str = Field(default="", description="Test execution summary")


class LintResults(BaseModel):
    """Results from running linters/static analyzers."""

    total_issues: int = Field(default=0, description="Total linting issues found")
    errors: int = Field(default=0, description="Number of errors")
    warnings: int = Field(default=0, description="Number of warnings")
    info: int = Field(default=0, description="Number of info messages")
    score: Optional[float] = Field(None, description="Linting score if available (e.g., pylint score)")
    tools_used: List[str] = Field(default_factory=list, description="Linters used (pylint, eslint, etc.)")
    summary: str = Field(default="", description="Linting summary")


class CodeReviewOutput(BaseModel):
    """Structured output for code review agent with automated verification results."""

    summary: str = Field(description="High-level summary of the review")
    overall_quality: Literal["excellent", "good", "fair", "poor"] = Field(
        description="Overall code quality assessment"
    )
    issues: List[CodeIssue] = Field(
        default_factory=list,
        description="List of issues found during review"
    )
    strengths: List[str] = Field(
        default_factory=list,
        description="Positive aspects of the code"
    )

    # Automated Verification Results (NEW)
    test_results: Optional[TestResults] = Field(
        None,
        description="Test execution results if tests were run"
    )
    lint_results: Optional[LintResults] = Field(
        None,
        description="Linting/static analysis results if linters were run"
    )

    metrics: Dict[str, Any] = Field(
        default_factory=dict,
        description="Code metrics (complexity, coverage, etc.)"
    )
    approved: bool = Field(description="Whether the code is approved for merge")
    next_steps: List[str] = Field(
        default_factory=list,
        description="Recommended next steps"
    )


# =============================================================================
# SQL Query Agent Outputs
# =============================================================================

class SQLQueryResult(BaseModel):
    """Structured output for SQL query agent."""

    query: str = Field(description="The SQL query that was executed")
    query_type: Literal["select", "count", "aggregate", "join", "subquery"] = Field(
        description="Type of SQL query"
    )
    tables_used: List[str] = Field(
        default_factory=list,
        description="Tables referenced in the query"
    )
    row_count: int = Field(description="Number of rows returned")
    columns: List[str] = Field(
        default_factory=list,
        description="Column names in the result"
    )
    results: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Query results (limited to first 100 rows)"
    )
    execution_time_ms: Optional[float] = Field(
        None,
        description="Query execution time in milliseconds"
    )
    insights: str = Field(description="Natural language insights about the results")
    suggestions: List[str] = Field(
        default_factory=list,
        description="Query optimization suggestions"
    )


# =============================================================================
# Data Analysis Agent Outputs
# =============================================================================

class DataSummary(BaseModel):
    """Summary statistics for a dataset."""

    row_count: int = Field(description="Number of rows")
    column_count: int = Field(description="Number of columns")
    missing_values: Dict[str, int] = Field(
        default_factory=dict,
        description="Missing value counts per column"
    )
    data_types: Dict[str, str] = Field(
        default_factory=dict,
        description="Data types per column"
    )
    memory_usage_mb: float = Field(description="Memory usage in megabytes")


class DataAnalysisOutput(BaseModel):
    """Structured output for data analysis agent."""

    summary: DataSummary = Field(description="Dataset summary statistics")
    key_findings: List[str] = Field(
        default_factory=list,
        description="Key insights and findings"
    )
    correlations: Dict[str, float] = Field(
        default_factory=dict,
        description="Significant correlations found (column pairs)"
    )
    outliers: Dict[str, List[Any]] = Field(
        default_factory=dict,
        description="Outliers detected per column"
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommended next analysis steps"
    )
    visualizations: List[str] = Field(
        default_factory=list,
        description="Suggested visualizations (descriptions)"
    )
    data_quality_score: Literal["excellent", "good", "fair", "poor"] = Field(
        description="Overall data quality assessment"
    )


# =============================================================================
# Jira Ticket Triage Outputs
# =============================================================================

class TicketClassification(BaseModel):
    """Classification details for a ticket."""

    severity: Literal["critical", "high", "medium", "low"] = Field(
        description="Severity level"
    )
    priority: Literal["urgent", "high", "medium", "low"] = Field(
        description="Priority level"
    )
    category: Literal["bug", "feature", "improvement", "task", "question"] = Field(
        description="Ticket category"
    )
    component: str = Field(description="Component/area affected (Frontend, Backend, API, etc.)")
    estimated_effort: Literal["small", "medium", "large", "xlarge"] = Field(
        description="Estimated effort to resolve"
    )


class JiraTriageOutput(BaseModel):
    """Structured output for Jira ticket triage agent."""

    ticket_id: str = Field(description="Jira ticket ID")
    classification: TicketClassification = Field(description="Ticket classification")
    summary: str = Field(description="Brief summary of the ticket")
    analysis: str = Field(description="Detailed analysis of the issue")
    root_cause: Optional[str] = Field(None, description="Suspected root cause")
    recommended_assignee: Optional[str] = Field(
        None,
        description="Recommended person/team to assign"
    )
    labels: List[str] = Field(
        default_factory=list,
        description="Recommended labels to add"
    )
    next_actions: List[str] = Field(
        default_factory=list,
        description="Recommended next actions"
    )
    related_tickets: List[str] = Field(
        default_factory=list,
        description="Related ticket IDs"
    )
    triage_confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence level of the triage analysis"
    )


# =============================================================================
# Task Planning Outputs (with MCGS)
# =============================================================================

class AlternativeApproach(BaseModel):
    """
    A single alternative approach explored during MCGS.

    MCGS (Monte Carlo Graph Search) requires exploring 2-3 approaches
    before selecting the best one for improved decision quality.
    """
    approach_id: str = Field(..., description="Unique identifier (e.g., 'approach_a', 'approach_b')")
    name: str = Field(..., description="Short descriptive name for this approach")
    description: str = Field(..., description="Detailed description of how this approach works")
    pros: List[str] = Field(..., description="Advantages and benefits of this approach")
    cons: List[str] = Field(..., description="Disadvantages, limitations, and risks")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0.0-1.0)")
    estimated_time_hours: float = Field(..., description="Estimated implementation time in hours")
    complexity: Literal["simple", "moderate", "complex"] = Field(..., description="Overall complexity level")
    dependencies: List[str] = Field(default_factory=list, description="Required dependencies or prerequisites")


class TaskStep(BaseModel):
    """A single step in a task plan."""

    step_number: int = Field(description="Step sequence number")
    title: str = Field(description="Step title")
    description: str = Field(description="Detailed step description")
    estimated_time_minutes: int = Field(description="Estimated time in minutes")
    dependencies: List[int] = Field(
        default_factory=list,
        description="Step numbers this depends on"
    )
    required_tools: List[str] = Field(
        default_factory=list,
        description="Tools/resources needed"
    )
    success_criteria: str = Field(description="How to verify step completion")


class TaskPlanOutput(BaseModel):
    """
    Structured output for task planning agent with MCGS approach exploration.

    This schema enforces the MCGS pattern: explore alternatives, then select best.
    """

    # Task Understanding
    goal: str = Field(description="Overall goal of the task")
    task_classification: Literal["feature", "bug_fix", "refactor", "research", "documentation"] = Field(
        description="Classification of the task type"
    )

    # MCGS: Approach Exploration (REQUIRED for complex tasks)
    approaches_explored: List[AlternativeApproach] = Field(
        default_factory=list,
        description="Alternative approaches explored (SHOULD explore 2-3 for complex tasks)"
    )

    # Selected Approach
    selected_approach: str = Field(description="High-level description of selected approach")
    selected_approach_id: Optional[str] = Field(
        None,
        description="ID of selected approach (if MCGS was used)"
    )
    selection_rationale: str = Field(
        description="Why this approach was chosen (especially if alternatives were considered)"
    )

    # Execution Plan (for selected approach)
    steps: List[TaskStep] = Field(
        default_factory=list,
        description="Ordered list of task steps for the selected approach"
    )

    # Assessment
    total_estimated_time_minutes: int = Field(
        description="Total estimated time for all steps"
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the plan (0.0-1.0)"
    )
    risks: List[str] = Field(
        default_factory=list,
        description="Potential risks and blockers"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Key assumptions made in the plan"
    )
    success_metrics: List[str] = Field(
        default_factory=list,
        description="Metrics to measure success"
    )


# =============================================================================
# Documentation Generation Outputs
# =============================================================================

class DocumentationSection(BaseModel):
    """A section in generated documentation."""

    title: str = Field(description="Section title")
    content: str = Field(description="Section content in Markdown")
    level: int = Field(description="Heading level (1-6)")
    order: int = Field(description="Display order")


class DocumentationOutput(BaseModel):
    """Structured output for documentation generation agent."""

    title: str = Field(description="Document title")
    summary: str = Field(description="Brief summary/description")
    sections: List[DocumentationSection] = Field(
        default_factory=list,
        description="Ordered list of documentation sections"
    )
    code_examples: List[str] = Field(
        default_factory=list,
        description="Code examples referenced in the documentation"
    )
    references: List[str] = Field(
        default_factory=list,
        description="External references and links"
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags/keywords for categorization"
    )
    last_updated: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        description="Last update timestamp"
    )
    completeness_score: Literal["complete", "mostly_complete", "partial", "draft"] = Field(
        description="Documentation completeness assessment"
    )


# =============================================================================
# Helper Functions
# =============================================================================

def get_schema_for_agent(template_id: str) -> Optional[type[BaseModel]]:
    """
    Get the structured output schema for an agent template.

    Args:
        template_id: Agent template ID

    Returns:
        Pydantic schema class or None

    Example:
        >>> schema = get_schema_for_agent("code_reviewer")
        >>> # Returns CodeReviewOutput class
    """

    schema_map = {
        "code_reviewer": CodeReviewOutput,
        "sql_database_agent": SQLQueryResult,
        "pandas_dataframe_agent": DataAnalysisOutput,
        "jira_qa_triager": JiraTriageOutput,
        "jira_ticket_generator": JiraTicketOutput,
        "jira_ticket_batch_generator": JiraTicketBatchOutput,
        "task_planner": TaskPlanOutput,
        "documentation_writer": DocumentationOutput,
    }

    return schema_map.get(template_id)


def create_agent_with_structured_output(
    agent_config: Dict[str, Any],
    output_schema: type[BaseModel]
):
    """
    Create an agent that returns structured outputs.

    This modifies the agent configuration to include structured output generation.

    Args:
        agent_config: Standard agent configuration
        output_schema: Pydantic model for output structure

    Returns:
        Modified agent config with structured output enabled

    Example:
        >>> config = {"model": "gpt-4o", "system_prompt": "..."}
        >>> config = create_agent_with_structured_output(
        ...     config,
        ...     CodeReviewOutput
        ... )
    """

    # Add structured output schema to config
    agent_config["output_schema"] = output_schema
    agent_config["enable_structured_output"] = True

    logger.info(f"Enabled structured output: {output_schema.__name__}")

    return agent_config


def validate_structured_output(output: Any, schema: type[BaseModel]) -> bool:
    """
    Validate that output conforms to schema.

    Args:
        output: Output to validate
        schema: Pydantic schema

    Returns:
        True if valid, False otherwise

    Example:
        >>> review = CodeReviewOutput(...)
        >>> is_valid = validate_structured_output(review, CodeReviewOutput)
    """

    try:
        if isinstance(output, schema):
            return True
        # Try to parse
        schema.model_validate(output)
        return True
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        return False


# =============================================================================
# Schema Registry
# =============================================================================

STRUCTURED_OUTPUT_SCHEMAS = {
    # Jira-related schemas
    "JiraTicketOutput": JiraTicketOutput,
    "JiraTicketBatchOutput": JiraTicketBatchOutput,
    "JiraTriageOutput": JiraTriageOutput,

    # Code analysis schemas
    "CodeReviewOutput": CodeReviewOutput,

    # Data schemas
    "SQLQueryResult": SQLQueryResult,
    "DataAnalysisOutput": DataAnalysisOutput,

    # Planning schemas
    "TaskPlanOutput": TaskPlanOutput,

    # Documentation schemas
    "DocumentationOutput": DocumentationOutput,
}


def list_available_schemas() -> Dict[str, str]:
    """
    List all available structured output schemas.

    Returns:
        Dictionary mapping schema names to descriptions

    Example:
        >>> schemas = list_available_schemas()
        >>> for name, desc in schemas.items():
        ...     print(f"{name}: {desc}")
    """

    return {
        name: schema.__doc__ or "No description"
        for name, schema in STRUCTURED_OUTPUT_SCHEMAS.items()
    }
