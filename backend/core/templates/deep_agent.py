# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Pre-configured DeepAgent Templates for LangConfig.

These are specialized DeepAgent templates that leverage the full capabilities
of the DeepAgents framework including planning, subagents, and context management.
"""

from typing import List
from models.deep_agent import (
    DeepAgentConfig,
    SubAgentConfig,
    MiddlewareConfig,
    BackendConfig,
    GuardrailsConfig,
    create_default_middleware_config,
    create_default_backend_config,
    create_default_guardrails_config
)
from models.enums import SubAgentType, MiddlewareType


# =============================================================================
# DeepAgent Template Configurations
# =============================================================================

def create_deep_code_researcher() -> DeepAgentConfig:
    """
    DEEP_CODE_RESEARCHER: Advanced code analysis with file exploration.

    Use Case: Deep code analysis, architectural reviews, security audits
    Features:
    - Filesystem access for code exploration
    - Planning with task breakdown
    - Subagent delegation for specialized analysis
    """
    return DeepAgentConfig(
        model="claude-sonnet-4-5-20250929",
        temperature=0.3,  # Lower for precise analysis
        system_prompt="""You are an expert code researcher with deep analytical capabilities.

Your expertise includes:
- Code architecture analysis and design pattern identification
- Security vulnerability detection
- Performance optimization recommendations
- Technical debt assessment

Use your planning tools to break down complex analysis tasks.
Spawn subagents for specialized deep-dives (security, performance, etc.).
Use filesystem tools to explore codebases systematically.

Always provide:
1. Executive summary
2. Detailed findings with code references
3. Prioritized recommendations
4. Action items
""",
        native_tools=["file_read", "file_write", "file_list"],
        cli_tools=[],
        use_deepagents=True,
        middleware=[
            MiddlewareConfig(
                type=MiddlewareType.TODO_LIST,
                enabled=True,
                config={"auto_track": True}
            ),
            MiddlewareConfig(
                type=MiddlewareType.FILESYSTEM,
                enabled=True,
                config={
                    "auto_eviction": True,
                    "eviction_threshold_bytes": 500000  # 500KB
                }
            ),
            MiddlewareConfig(
                type=MiddlewareType.SUBAGENT,
                enabled=True,
                config={"max_depth": 2, "max_concurrent": 3}
            )
        ],
        subagents=[
            SubAgentConfig(
                name="security_analyst",
                description="Specialized in security vulnerability analysis",
                system_prompt="You are a security expert. Analyze code for vulnerabilities, injection risks, and security best practices.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            ),
            SubAgentConfig(
                name="performance_analyst",
                description="Specialized in performance optimization",
                system_prompt="You are a performance expert. Identify bottlenecks, inefficient algorithms, and optimization opportunities.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            )
        ],
        backend=create_default_backend_config(),
        guardrails=create_default_guardrails_config()
    )


def create_deep_architect() -> DeepAgentConfig:
    """
    DEEP_ARCHITECT: System design with subagent delegation.

    Use Case: Architectural planning, system design, technical specifications
    Features:
    - Planning with multi-phase approach
    - Subagent delegation for different architectural aspects
    - Documentation generation
    """
    return DeepAgentConfig(
        model="claude-sonnet-4-5-20250929",
        temperature=0.7,
        system_prompt="""You are a senior software architect with expertise in system design.

Your responsibilities:
- Design scalable, maintainable architectures
- Create technical specifications
- Evaluate trade-offs between different approaches
- Document architectural decisions (ADRs)

Use planning tools to structure your design process:
1. Requirements analysis
2. Architecture proposal
3. Trade-off evaluation
4. Implementation roadmap

Delegate to specialized subagents for:
- Database schema design
- API design
- Infrastructure planning
- Security architecture

Always provide visual diagrams (mermaid syntax) and clear documentation.
""",
        native_tools=["file_read", "file_write", "file_list"],
        cli_tools=[],
        use_deepagents=True,
        middleware=create_default_middleware_config(),
        subagents=[
            SubAgentConfig(
                name="database_architect",
                description="Database schema and optimization expert",
                system_prompt="You design database schemas, optimize queries, and plan data models.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            ),
            SubAgentConfig(
                name="api_designer",
                description="API design and REST/GraphQL expert",
                system_prompt="You design APIs following best practices, RESTful principles, and modern patterns.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            ),
            SubAgentConfig(
                name="infrastructure_planner",
                description="Cloud infrastructure and DevOps expert",
                system_prompt="You plan cloud infrastructure, CI/CD pipelines, and deployment strategies.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            )
        ],
        backend=create_default_backend_config(),
        guardrails=create_default_guardrails_config()
    )


def create_deep_debugger() -> DeepAgentConfig:
    """
    DEEP_DEBUGGER: Multi-step debugging with systematic investigation.

    Use Case: Complex bug investigation, root cause analysis
    Features:
    - Systematic debugging workflow
    - Tool spawning for testing
    - Hypothesis tracking
    """
    return DeepAgentConfig(
        model="claude-sonnet-4-5-20250929",
        temperature=0.2,  # Very precise for debugging
        system_prompt="""You are an expert debugger with systematic investigation skills.

Your debugging process:
1. Understand the problem and gather context
2. Form hypotheses about potential causes
3. Test each hypothesis systematically
4. Isolate the root cause
5. Propose and validate fixes

Use planning tools to track:
- List of hypotheses
- Tests performed
- Findings from each test
- Progress toward root cause

Use filesystem tools to:
- Read relevant code files
- Check logs and error messages
- Analyze stack traces
- Review recent changes

Always provide:
- Clear problem statement
- Root cause analysis
- Proposed fix with explanation
- Prevention recommendations
""",
        native_tools=["file_read", "file_write", "file_list"],
        cli_tools=[],
        use_deepagents=True,
        middleware=create_default_middleware_config(),
        subagents=[
            SubAgentConfig(
                name="test_runner",
                description="Specialized in running and analyzing tests",
                system_prompt="You run tests, analyze failures, and provide detailed test reports.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            )
        ],
        backend=create_default_backend_config(),
        guardrails=GuardrailsConfig(
            interrupts={},
            token_limits={
                "max_total_tokens": 150000,  # Higher for deep debugging
                "eviction_threshold": 100000,
                "summarization_threshold": 70000
            },
            enable_auto_eviction=True,
            enable_summarization=True
        )
    )


def create_deep_document_writer() -> DeepAgentConfig:
    """
    DEEP_DOCUMENT_WRITER: Long-form documentation with research.

    Use Case: Technical documentation, user guides, API docs
    Features:
    - Research-driven writing
    - Multi-section planning
    - Context management for long documents
    """
    return DeepAgentConfig(
        model="claude-sonnet-4-5-20250929",
        temperature=0.7,
        system_prompt="""You are a technical writer specializing in clear, comprehensive documentation.

Your writing process:
1. Research the topic thoroughly
2. Create a detailed outline
3. Write each section with clarity
4. Include examples and code snippets
5. Review and refine

Use planning tools to:
- Break documentation into sections
- Track completion of each section
- Manage research tasks

Use filesystem tools to:
- Read code for accurate examples
- Extract API signatures
- Review existing documentation

Writing principles:
- Clear and concise language
- Practical examples
- Logical structure
- Consistent formatting
- Helpful diagrams (mermaid syntax)

Target audiences:
- Developers (technical depth)
- Users (practical focus)
- Stakeholders (high-level overview)
""",
        native_tools=["file_read", "file_write", "file_list"],
        cli_tools=[],
        use_deepagents=True,
        middleware=create_default_middleware_config(),
        subagents=[
            SubAgentConfig(
                name="code_example_generator",
                description="Specialized in creating code examples",
                system_prompt="You create clear, working code examples that demonstrate concepts effectively.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            ),
            SubAgentConfig(
                name="researcher",
                description="Researches topics and gathers information",
                system_prompt="You research topics thoroughly, gathering accurate information from code and documentation.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            )
        ],
        backend=create_default_backend_config(),
        guardrails=GuardrailsConfig(
            interrupts={},
            token_limits={
                "max_total_tokens": 200000,  # Higher for long documents
                "eviction_threshold": 140000,
                "summarization_threshold": 100000
            },
            enable_auto_eviction=True,
            enable_summarization=True
        )
    )


def create_deep_test_engineer() -> DeepAgentConfig:
    """
    DEEP_TEST_ENGINEER: Comprehensive test generation with coverage analysis.

    Use Case: Test suite creation, test coverage improvement, QA
    Features:
    - Systematic test planning
    - Multiple test type generation (unit, integration, e2e)
    - Coverage analysis
    """
    return DeepAgentConfig(
        model="claude-sonnet-4-5-20250929",
        temperature=0.4,
        system_prompt="""You are a test engineering expert focused on comprehensive test coverage.

Your testing approach:
1. Analyze code to understand functionality
2. Identify test scenarios (happy path, edge cases, errors)
3. Generate tests for multiple levels (unit, integration, e2e)
4. Ensure good coverage of critical paths
5. Include test data and fixtures

Use planning tools to:
- List all functions/classes to test
- Track test scenarios for each
- Monitor coverage progress

Test types you create:
- Unit tests: Isolated function/class testing
- Integration tests: Component interaction testing
- E2E tests: Full workflow testing
- Property-based tests: Fuzz testing critical logic

Testing best practices:
- Clear test names describing what's tested
- Arrange-Act-Assert pattern
- Independent, repeatable tests
- Good failure messages
- Appropriate mocking/stubbing

Use subagents for specialized testing:
- Performance testing
- Security testing
- Accessibility testing
""",
        native_tools=["file_read", "file_write", "file_list"],
        cli_tools=[],
        use_deepagents=True,
        middleware=create_default_middleware_config(),
        subagents=[
            SubAgentConfig(
                name="unit_test_specialist",
                description="Expert in unit test generation",
                system_prompt="You create thorough unit tests with excellent edge case coverage.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            ),
            SubAgentConfig(
                name="integration_test_specialist",
                description="Expert in integration test generation",
                system_prompt="You create integration tests that verify component interactions.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            ),
            SubAgentConfig(
                name="e2e_test_specialist",
                description="Expert in end-to-end test generation",
                system_prompt="You create end-to-end tests that validate complete user workflows.",
                tools=["file_read", "file_write", "file_list"],
                middleware=["filesystem"]
            )
        ],
        backend=create_default_backend_config(),
        guardrails=create_default_guardrails_config()
    )


# =============================================================================
# Template Registry
# =============================================================================

class DeepAgentTemplateRegistry:
    """Registry of pre-configured DeepAgent templates."""

    _templates = {
        "DEEP_CODE_RESEARCHER": {
            "name": "Deep Code Researcher",
            "description": "Advanced code analysis with file exploration and subagent delegation",
            "category": "research",
            "factory": create_deep_code_researcher,
            "capabilities": [
                "Code architecture analysis",
                "Security vulnerability detection",
                "Performance optimization",
                "Technical debt assessment",
                "Subagent delegation"
            ],
            "use_cases": [
                "Codebase reviews",
                "Security audits",
                "Technical due diligence",
                "Refactoring planning"
            ]
        },
        "DEEP_ARCHITECT": {
            "name": "Deep Architect",
            "description": "System design and architecture planning with specialized subagents",
            "category": "architecture",
            "factory": create_deep_architect,
            "capabilities": [
                "System design",
                "Technical specifications",
                "Architecture decision records",
                "Database schema design",
                "API design"
            ],
            "use_cases": [
                "New system design",
                "Architecture refactoring",
                "Technical planning",
                "ADR documentation"
            ]
        },
        "DEEP_DEBUGGER": {
            "name": "Deep Debugger",
            "description": "Systematic debugging with hypothesis tracking and root cause analysis",
            "category": "debugging",
            "factory": create_deep_debugger,
            "capabilities": [
                "Root cause analysis",
                "Hypothesis testing",
                "Log analysis",
                "Test execution",
                "Fix validation"
            ],
            "use_cases": [
                "Complex bug investigation",
                "Production issue debugging",
                "Test failure analysis",
                "Performance debugging"
            ]
        },
        "DEEP_DOCUMENT_WRITER": {
            "name": "Deep Document Writer",
            "description": "Long-form technical documentation with research and examples",
            "category": "documentation",
            "factory": create_deep_document_writer,
            "capabilities": [
                "Technical writing",
                "Code example generation",
                "API documentation",
                "User guides",
                "Tutorial creation"
            ],
            "use_cases": [
                "Product documentation",
                "API reference docs",
                "Developer guides",
                "Tutorial creation"
            ]
        },
        "DEEP_TEST_ENGINEER": {
            "name": "Deep Test Engineer",
            "description": "Comprehensive test generation with coverage analysis",
            "category": "testing",
            "factory": create_deep_test_engineer,
            "capabilities": [
                "Unit test generation",
                "Integration test generation",
                "E2E test generation",
                "Test coverage analysis",
                "Test data creation"
            ],
            "use_cases": [
                "Test suite creation",
                "Coverage improvement",
                "Legacy code testing",
                "Regression test generation"
            ]
        }
    }

    @classmethod
    def get_template(cls, template_id: str) -> DeepAgentConfig:
        """Get a DeepAgent configuration by template ID."""
        if template_id not in cls._templates:
            raise ValueError(f"Unknown template: {template_id}")

        template = cls._templates[template_id]
        return template["factory"]()

    @classmethod
    def list_all(cls) -> List[dict]:
        """List all available templates with metadata."""
        return [
            {
                "template_id": template_id,
                "name": template["name"],
                "description": template["description"],
                "category": template["category"],
                "capabilities": template["capabilities"],
                "use_cases": template["use_cases"]
            }
            for template_id, template in cls._templates.items()
        ]

    @classmethod
    def get_by_category(cls, category: str) -> List[dict]:
        """Get templates filtered by category."""
        return [
            {
                "template_id": template_id,
                "name": template["name"],
                "description": template["description"],
                "category": template["category"]
            }
            for template_id, template in cls._templates.items()
            if template["category"] == category
        ]


# =============================================================================
# Database Seeding Function
# =============================================================================

async def seed_deepagent_templates(db):
    """
    Seed the database with pre-configured DeepAgent templates.

    Call this during application startup to populate the template library.
    """
    from models.deep_agent import DeepAgentTemplate
    import logging

    logger = logging.getLogger(__name__)

    for template_id, template_meta in DeepAgentTemplateRegistry._templates.items():
        # Check if template already exists
        existing = db.query(DeepAgentTemplate).filter(
            DeepAgentTemplate.name == template_meta["name"]
        ).first()

        if existing:
            logger.info(f"Template '{template_meta['name']}' already exists, skipping")
            continue

        # Create configuration
        config = template_meta["factory"]()

        # Create database record
        template = DeepAgentTemplate(
            name=template_meta["name"],
            description=template_meta["description"],
            category=template_meta["category"],
            base_template_id=template_id,
            config=config.dict(),
            middleware_config=[m.dict() for m in config.middleware],
            subagents_config=[s.dict() for s in config.subagents],
            backend_config=config.backend.dict(),
            guardrails_config=config.guardrails.dict(),
            is_public=True,
            version="1.0.0"
        )

        db.add(template)
        logger.info(f"✓ Created template: {template_meta['name']}")

    db.commit()
    logger.info("DeepAgent templates seeded successfully")
