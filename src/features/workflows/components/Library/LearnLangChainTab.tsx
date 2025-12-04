/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState } from 'react';

export default function LearnLangChainTab() {
  const [expandedSection, setExpandedSection] = useState<string | null>('agent-fundamentals');

  const toggleSection = (section: string) => {
    setExpandedSection(expandedSection === section ? null : section);
  };

  return (
    <div className="h-full overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="text-3xl font-bold mb-2" style={{ color: 'var(--color-text-primary)' }}>
            Learn LangChain & LangGraph
          </h2>
          <p className="text-base" style={{ color: 'var(--color-text-muted)' }}>
            Master the fundamentals of building production-ready AI agents
          </p>
        </div>

        {/* Official Documentation Link */}
        <a
          href="https://docs.langchain.com/oss/python/langchain/overview"
          target="_blank"
          rel="noopener noreferrer"
          className="block p-4 rounded-lg border border-primary/30 bg-primary/5 hover:bg-primary/10 transition-colors"
        >
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-2xl text-primary">menu_book</span>
            <div>
              <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                Official LangChain Documentation
              </h3>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                Comprehensive guides, API references, and tutorials
              </p>
            </div>
            <span className="material-symbols-outlined text-primary ml-auto">open_in_new</span>
          </div>
        </a>

        {/* Learning Sections */}
        <div className="space-y-3">
          {/* Section 1: Agent Fundamentals */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('agent-fundamentals')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">psychology</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  1. Agent Fundamentals
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'agent-fundamentals' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'agent-fundamentals' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    What is a LangChain Agent?
                  </h4>
                  <p className="leading-relaxed mb-3">
                    An agent uses a language model to determine which actions to take and in what order. Unlike chains where the sequence is hardcoded, agents use an LLM as a reasoning engine to decide the control flow.
                  </p>
                  <a
                    href="https://python.langchain.com/docs/modules/agents/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline text-xs"
                  >
                    <span>Read more in LangChain Agents docs</span>
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Agent Types
                  </h4>
                  <ul className="space-y-3 ml-4">
                    <li>
                      <strong style={{ color: 'var(--color-text-primary)' }}>Tool Calling Agents:</strong> The modern standard for most use cases. Leverages native tool calling capabilities of models (like OpenAI or Anthropic) for reliable, structured execution.
                      <a
                        href="https://python.langchain.com/docs/modules/agents/agent_types/tool_calling/"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 text-primary hover:underline text-xs"
                      >
                        Docs ↗
                      </a>
                    </li>
                    <li>
                      <strong style={{ color: 'var(--color-text-primary)' }}>Plan-and-Execute:</strong> First plans the full sequence of steps, then executes them. Better for complex tasks requiring upfront planning.
                      <a
                        href="https://python.langchain.com/docs/use_cases/plan_and_execute"
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 text-primary hover:underline text-xs"
                      >
                        Docs ↗
                      </a>
                    </li>
                    <li>
                      <strong style={{ color: 'var(--color-text-primary)' }}>Structured Output:</strong> Agents designed specifically to return structured data (JSON/Pydantic) rather than free text, ideal for data extraction tasks.
                    </li>
                  </ul>
                </div>

                <div className="p-3 rounded bg-blue-50 dark:bg-blue-500/10 border border-blue-200 dark:border-blue-500/30">
                  <div className="flex gap-2">
                    <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 text-sm">lightbulb</span>
                    <p className="text-xs text-blue-800 dark:text-blue-300">
                      <strong>Tip:</strong> Start with Tool Calling Agents. They are more reliable and faster than legacy ReAct agents because they use the model's fine-tuned tool capabilities.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Section 2: LangGraph State Machines */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('langgraph')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">account_tree</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  2. LangGraph State Machines
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'langgraph' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'langgraph' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    What is LangGraph?
                  </h4>
                  <p className="leading-relaxed mb-3">
                    LangGraph is a library for building stateful, multi-actor applications with LLMs. It extends LangChain with the ability to coordinate multiple chains (or actors) across multiple steps of computation in a cyclic manner.
                  </p>
                  <a
                    href="https://langchain-ai.github.io/langgraph/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline text-xs"
                  >
                    <span>LangGraph Official Documentation</span>
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Key Concepts
                  </h4>
                  <ul className="space-y-2 ml-4 list-disc">
                    <li><strong>State Graph:</strong> Defines nodes (agents/functions) and edges (transitions) between them</li>
                    <li><strong>State:</strong> Shared data structure passed between nodes</li>
                    <li><strong>Conditional Edges:</strong> Dynamic routing based on state or outputs</li>
                    <li><strong>Checkpointing:</strong> Save and resume execution state for long-running workflows</li>
                    <li><strong>Human-in-the-Loop:</strong> Pause execution for human review and intervention</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Why Use LangGraph?
                  </h4>
                  <ul className="space-y-1 ml-4 list-disc">
                    <li>Coordinate multiple agents in complex workflows</li>
                    <li>Implement cyclic logic (loops, retries, feedback)</li>
                    <li>Persist conversation state across sessions</li>
                    <li>Build production-ready multi-agent systems</li>
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Section 3: Tools & Function Calling */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('tools')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">build</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  3. Tools & Function Calling
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'tools' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'tools' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    What are Tools?
                  </h4>
                  <p className="leading-relaxed mb-3">
                    Tools are interfaces that an agent can use to interact with the world. They enable agents to perform actions like searching the web, querying databases, making API calls, or running code.
                  </p>
                  <a
                    href="https://python.langchain.com/docs/modules/tools/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline text-xs"
                  >
                    <span>LangChain Tools Documentation</span>
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Built-in Tools in LangConfig
                  </h4>
                  <ul className="space-y-2 ml-4">
                    <li><strong>Web Search:</strong> Search the internet for current information</li>
                    <li><strong>File Operations:</strong> Read/write files in your project</li>
                    <li><strong>Code Execution:</strong> Run Python code safely</li>
                    <li><strong>RAG (Retrieval):</strong> Search your knowledge base documents</li>
                    <li><strong>GitHub Integration:</strong> Interact with GitHub repositories</li>
                    <li><strong>Browser Automation:</strong> Control web browsers via Puppeteer</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Tool Selection Strategy
                  </h4>
                  <p className="leading-relaxed">
                    Give agents only the tools they need. Too many tools can confuse the model and increase costs. Start minimal and add tools as requirements emerge.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Section 4: RAG Implementation */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('rag')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">database</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  4. RAG (Retrieval Augmented Generation)
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'rag' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'rag' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    What is RAG?
                  </h4>
                  <p className="leading-relaxed mb-3">
                    RAG combines retrieval of relevant documents with generation. Instead of relying solely on the LLM's training data, RAG retrieves relevant information from your documents and provides it as context for generation.
                  </p>
                  <a
                    href="https://python.langchain.com/docs/use_cases/question_answering/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline text-xs"
                  >
                    <span>LangChain RAG Tutorial</span>
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    RAG Pipeline Steps
                  </h4>
                  <ol className="space-y-2 ml-4 list-decimal">
                    <li><strong>Indexing:</strong> Load documents, split into chunks, create embeddings, store in vector DB</li>
                    <li><strong>Retrieval:</strong> Embed user query, find similar chunks via vector search</li>
                    <li><strong>Generation:</strong> Pass retrieved context + query to LLM for answer</li>
                  </ol>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Using RAG in LangConfig
                  </h4>
                  <p className="leading-relaxed">
                    Upload documents to the Knowledge Base, then enable the RAG tool on your agent. The agent will automatically search your documents when relevant to the user's query.
                  </p>
                </div>

                <div className="p-3 rounded bg-purple-50 dark:bg-purple-500/10 border border-purple-200 dark:border-purple-500/30">
                  <div className="flex gap-2">
                    <span className="material-symbols-outlined text-purple-600 dark:text-purple-400 text-sm">tips_and_updates</span>
                    <p className="text-xs text-purple-800 dark:text-purple-300">
                      <strong>Pro Tip:</strong> Chunk your documents into 500-1000 token pieces for optimal retrieval performance.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Section 5: Prompt Engineering */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('prompts')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">edit_note</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  5. System Prompt Engineering
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
                    Effective System Prompts
                  </h4>
                  <p className="leading-relaxed mb-3">
                    System prompts define your agent's role, capabilities, constraints, and output format. A well-crafted system prompt is the foundation of reliable agent behavior.
                  </p>
                  <a
                    href="https://python.langchain.com/docs/modules/model_io/prompts/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline text-xs"
                  >
                    <span>Prompt Templates Documentation</span>
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Key Components
                  </h4>
                  <ul className="space-y-2 ml-4 list-disc">
                    <li><strong>Role:</strong> Define who the agent is (e.g., "You are an expert Python developer")</li>
                    <li><strong>Task:</strong> Clearly state what they should do</li>
                    <li><strong>Context:</strong> Provide relevant background information</li>
                    <li><strong>Constraints:</strong> Set boundaries (what NOT to do)</li>
                    <li><strong>Output Format:</strong> Specify how to structure responses</li>
                    <li><strong>Examples:</strong> Show desired input/output pairs (few-shot learning)</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Best Practices
                  </h4>
                  <ul className="space-y-1 ml-4 list-disc">
                    <li>Be specific and explicit - avoid ambiguity</li>
                    <li>Use clear, direct language</li>
                    <li>Provide examples when possible</li>
                    <li>Iterate based on agent behavior</li>
                    <li>Test with edge cases</li>
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Section 6: Multi-Agent Workflows */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('multi-agent')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">group_work</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  6. Multi-Agent Workflows
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'multi-agent' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'multi-agent' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    When to Use Multiple Agents
                  </h4>
                  <p className="leading-relaxed mb-3">
                    Break complex tasks into specialized agents when:
                  </p>
                  <ul className="space-y-1 ml-4 list-disc">
                    <li>Different subtasks require different expertise</li>
                    <li>You need separation of concerns</li>
                    <li>Parallel execution can speed up workflows</li>
                    <li>Different models are optimal for different steps</li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Common Patterns
                  </h4>
                  <ul className="space-y-3 ml-4">
                    <li>
                      <strong style={{ color: 'var(--color-text-primary)' }}>Sequential:</strong> Agent A → Agent B → Agent C. Output of one feeds into the next.
                    </li>
                    <li>
                      <strong style={{ color: 'var(--color-text-primary)' }}>Parallel:</strong> Multiple agents process the same input simultaneously, results combined at the end.
                    </li>
                    <li>
                      <strong style={{ color: 'var(--color-text-primary)' }}>Supervisor:</strong> One agent delegates tasks to specialized agents based on the request.
                    </li>
                    <li>
                      <strong style={{ color: 'var(--color-text-primary)' }}>Hierarchical:</strong> Agents organized in layers with higher-level agents coordinating lower-level ones.
                    </li>
                  </ul>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    State Management
                  </h4>
                  <p className="leading-relaxed">
                    LangGraph manages shared state across agents. Define your state schema carefully - it's how agents communicate. Use typed dictionaries for clarity and validation.
                  </p>
                </div>
              </div>
            )}
          </div>
          {/* Section 7: Deep Agents */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('deep-agents')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">psychology_alt</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  7. Deep Agents (LangGraph)
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'deep-agents' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'deep-agents' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    What is a Deep Agent?
                  </h4>
                  <p className="leading-relaxed mb-3">
                    Deep Agents are advanced, stateful agents built on LangGraph. Unlike regular agents that run a single chain of thought, Deep Agents maintain persistent state, support complex cyclic workflows, and can coordinate multiple sub-agents.
                  </p>
                  <a
                    href="https://langchain-ai.github.io/langgraph/concepts/agentic_patterns/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline text-xs"
                  >
                    <span>LangGraph Agent Patterns</span>
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Key Capabilities
                  </h4>
                  <ul className="space-y-2 ml-4 list-disc">
                    <li><strong>Subagents:</strong> Delegate tasks to specialized agents (e.g., a "Coder" agent delegates to a "Tester" agent).</li>
                    <li><strong>Compiled Workflows:</strong> Agents are compiled into efficient state graphs for production execution.</li>
                    <li><strong>Advanced Memory:</strong> Persist conversation history and state across sessions using checkpoints.</li>
                    <li><strong>Human-in-the-loop:</strong> Pause execution for approval before critical actions (like deploying code).</li>
                  </ul>
                </div>

                <div className="p-3 rounded bg-purple-50 dark:bg-purple-500/10 border border-purple-200 dark:border-purple-500/30">
                  <div className="flex gap-2">
                    <span className="material-symbols-outlined text-purple-600 dark:text-purple-400 text-sm">tips_and_updates</span>
                    <p className="text-xs text-purple-800 dark:text-purple-300">
                      <strong>When to use:</strong> Switch to Deep Agents when you need long-running workflows, human approval steps, or multi-agent coordination.
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Section 8: Middleware */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('middleware')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">layers</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  8. Middleware & Interceptors
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
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    What is Middleware?
                  </h4>
                  <p className="leading-relaxed mb-3">
                    Middleware allows you to intercept and modify the inputs and outputs of your agents or tools. It wraps the execution logic, enabling you to add cross-cutting concerns without changing the core agent logic.
                  </p>
                  <a
                    href="https://python.langchain.com/docs/expression_language/primitives/binding/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary hover:underline text-xs"
                  >
                    <span>RunnableBinding Documentation</span>
                    <span className="material-symbols-outlined text-sm">open_in_new</span>
                  </a>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Common Use Cases
                  </h4>
                  <ul className="space-y-2 ml-4 list-disc">
                    <li><strong>Logging & Tracing:</strong> Capture inputs/outputs for debugging or auditing.</li>
                    <li><strong>Guardrails:</strong> Validate inputs or outputs to ensure safety (e.g., PII filtering).</li>
                    <li><strong>Rate Limiting:</strong> Control the frequency of tool calls.</li>
                    <li><strong>Context Injection:</strong> Automatically add user context or metadata to prompts.</li>
                  </ul>
                </div>
              </div>
            )}
          </div>

          {/* Section 9: Action Presets & Tool Safety */}
          <div className="border border-gray-200 dark:border-border-dark rounded-lg overflow-hidden bg-white dark:bg-panel-dark">
            <button
              onClick={() => toggleSection('action-presets')}
              className="w-full flex items-center justify-between p-4 hover:bg-gray-50 dark:hover:bg-white/5 transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-primary">shield</span>
                <span className="font-semibold text-left" style={{ color: 'var(--color-text-primary)' }}>
                  9. Action Presets & Tool Safety
                </span>
              </div>
              <span
                className={`material-symbols-outlined transition-transform ${expandedSection === 'action-presets' ? 'rotate-180' : ''
                  }`}
                style={{ color: 'var(--color-text-muted)' }}
              >
                expand_more
              </span>
            </button>
            {expandedSection === 'action-presets' && (
              <div className="px-6 pb-6 space-y-4 text-sm" style={{ color: 'var(--color-text-muted)' }}>
                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    What are Action Presets?
                  </h4>
                  <p className="leading-relaxed mb-3">
                    Action Presets are backend safety mechanisms that automatically enforce execution constraints on tools. They provide automatic timeouts, retry logic, and human-in-the-loop (HITL) approval gates to ensure safe tool execution in production environments.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Automatic Timeouts
                  </h4>
                  <p className="leading-relaxed mb-2">
                    Tools are automatically wrapped with timeout constraints to prevent runaway processes:
                  </p>
                  <ul className="space-y-2 ml-4 list-disc">
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>Terminal Commands:</strong> 60-second timeout to prevent hanging processes</li>
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>Web Searches:</strong> 30-second timeout for API calls</li>
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>File Operations:</strong> 20-second timeout for I/O operations</li>
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>Retry Logic:</strong> Configurable max retries with exponential backoff</li>
                  </ul>
                  <p className="leading-relaxed mt-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    If a tool exceeds its timeout, execution is immediately terminated and the agent receives an error message.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Human-in-the-Loop (HITL) Approvals
                  </h4>
                  <p className="leading-relaxed mb-2">
                    High-risk tools require explicit human approval before execution:
                  </p>
                  <ul className="space-y-2 ml-4 list-disc">
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>Terminal Access:</strong> Any command line execution pauses for approval</li>
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>File System Writes:</strong> Creating, modifying, or deleting files</li>
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>External API Calls:</strong> POST/PUT/DELETE operations to external services</li>
                  </ul>
                  <p className="leading-relaxed mt-3">
                    When a tool requires approval, the workflow pauses and displays the tool details, inputs, and recommended actions. You can approve, reject, or modify the operation before it proceeds.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Recommended Middleware
                  </h4>
                  <p className="leading-relaxed mb-2">
                    Action Presets suggest middleware patterns for each tool category:
                  </p>
                  <ul className="space-y-2 ml-4 list-disc">
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>Logging:</strong> Capture all tool inputs/outputs for debugging and audit trails</li>
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>Cost Tracking:</strong> Monitor API usage and token consumption per tool</li>
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>PII Redaction:</strong> Automatically scrub sensitive data from logs</li>
                    <li><strong style={{ color: 'var(--color-text-primary)' }}>Rate Limiting:</strong> Control execution frequency to prevent API abuse</li>
                  </ul>
                  <p className="leading-relaxed mt-3 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    Middleware is optional but highly recommended for production deployments.
                  </p>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Example Configuration
                  </h4>
                  <pre className="text-xs p-4 rounded-lg bg-gray-50 dark:bg-black/20 overflow-x-auto border border-gray-200 dark:border-border-dark font-mono leading-relaxed" style={{ color: 'var(--color-text-primary)' }}>
{`{
  "preset_id": "terminal_access",
  "name": "Terminal Access",
  "requires_approval": true,
  "constraints": {
    "max_duration_seconds": 60,
    "max_retries": 0,
    "timeout_strategy": "kill",
    "exclusive": true
  },
  "recommended_middleware": [
    "logging",
    "cost_tracking"
  ],
  "best_practices": [
    "Always validate commands",
    "Use absolute paths",
    "Avoid interactive commands"
  ]
}`}
                  </pre>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    How It Works
                  </h4>
                  <p className="leading-relaxed mb-2">
                    When you enable a tool in your agent configuration, LangConfig automatically:
                  </p>
                  <ul className="space-y-2 ml-4 list-disc">
                    <li>Wraps the tool with execution constraints (timeouts, retries, exclusive locks)</li>
                    <li>Injects HITL approval gates for operations that require human review</li>
                    <li>Applies recommended middleware patterns if configured</li>
                    <li>Logs execution metrics and error traces for monitoring</li>
                  </ul>
                  <p className="leading-relaxed mt-3">
                    <strong style={{ color: 'var(--color-text-primary)' }}>Optional but recommended</strong> - Action Presets are disabled by default to give you full control during development. Enable them for production deployments to add automatic safety guardrails.
                  </p>
                </div>

                <div className="p-4 rounded border" style={{ backgroundColor: 'rgba(59, 130, 246, 0.05)', borderColor: 'rgba(59, 130, 246, 0.2)' }}>
                  <div className="flex gap-3">
                    <span className="material-symbols-outlined text-blue-600 dark:text-blue-400 flex-shrink-0">info</span>
                    <div>
                      <h4 className="text-sm font-semibold mb-1 text-blue-800 dark:text-blue-400">
                        Production Safety
                      </h4>
                      <p className="text-xs text-blue-700 dark:text-blue-400/80">
                        Action Presets are essential for production deployments. They prevent runaway processes, enforce approval workflows, and ensure tools execute within safe boundaries. All constraints are enforced at the backend level, independent of the frontend UI.
                      </p>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    Learn More
                  </h4>
                  <div className="space-y-2">
                    <a
                      href="https://python.langchain.com/docs/concepts/tools/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-primary hover:underline text-xs"
                    >
                      <span>LangChain Tools Documentation</span>
                      <span className="material-symbols-outlined text-sm">open_in_new</span>
                    </a>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Additional Resources */}
        <div className="mt-8 p-4 rounded-lg border border-gray-200 dark:border-border-dark bg-gradient-to-br from-primary/5 to-transparent">
          <h3 className="font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
            Additional Resources
          </h3>
          <div className="space-y-2 text-sm">
            <a
              href="https://python.langchain.com/docs/expression_language/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-primary hover:underline"
            >
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
              <span>LangChain Expression Language (LCEL)</span>
            </a>
            <a
              href="https://python.langchain.com/docs/modules/memory/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-primary hover:underline"
            >
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
              <span>Memory & Conversation Management</span>
            </a>
            <a
              href="https://python.langchain.com/docs/use_cases/"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-primary hover:underline"
            >
              <span className="material-symbols-outlined text-sm">arrow_forward</span>
              <span>Use Cases & Examples</span>
            </a>
          </div>
        </div>
      </div>
    </div >
  );
}
