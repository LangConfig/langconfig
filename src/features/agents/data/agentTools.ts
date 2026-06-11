/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

/**
 * Complete tool list from backend/tools/native_tools.py with DeepAgents standard naming.
 * See: https://docs.langchain.com/oss/python/deepagents/harness
 */
export interface AgentTool {
  id: string;
  name: string;
  description: string;
  category: string;
  /**
   * When set, this tool is only available for models from the given provider
   * (e.g. server-side tools executed on Anthropic infrastructure). Gated tools
   * are persisted into `anthropic_server_tools`, NOT `native_tools`.
   */
  providerGate?: 'anthropic';
}

export const AVAILABLE_TOOLS: AgentTool[] = [
  { id: 'web_search', name: 'Web Search', description: 'Search the web (DuckDuckGo)', category: 'web' },
  { id: 'web_fetch', name: 'Web Fetch', description: 'Fetch webpage content', category: 'web' },
  // Anthropic server-side tools (executed on Anthropic infrastructure; Claude models only)
  { id: 'anthropic_web_search', name: 'Web Search (Anthropic)', description: 'Server-side web search run on Anthropic infrastructure with citations. Claude models only.', category: 'web', providerGate: 'anthropic' },
  { id: 'anthropic_web_fetch', name: 'Web Fetch (Anthropic)', description: 'Server-side URL fetch run on Anthropic infrastructure. Claude models only.', category: 'web', providerGate: 'anthropic' },
  { id: 'browser', name: 'Browser Automation', description: 'Advanced web interaction (Playwright)', category: 'web' },
  // Image generation (OpenAI Images 2.0 — gpt-image-2)
  { id: 'generate_image', name: 'Generate Image', description: 'Generate images with OpenAI Images 2.0 (gpt-image-2). Instant or Thinking mode, up to 8 variants with character continuity, 2K output.', category: 'media' },
  // DeepAgents standard filesystem tools
  { id: 'read_file', name: 'Read File', description: 'Read file contents with line numbers', category: 'files' },
  { id: 'write_file', name: 'Write File', description: 'Create new files', category: 'files' },
  { id: 'ls', name: 'List Directory', description: 'List directory contents with metadata', category: 'files' },
  { id: 'edit_file', name: 'Edit File', description: 'Exact string replacements in files', category: 'files' },
  { id: 'glob', name: 'Glob', description: 'Find files matching patterns', category: 'files' },
  { id: 'grep', name: 'Grep', description: 'Search file contents with regex', category: 'files' },
  { id: 'enable_memory', name: 'Enable Memory', description: 'Capability flag: enables long‑term memory for this agent (persisted via project/workflow store). Not a tool by itself; pair with Store/Recall Memory.', category: 'memory' },
  { id: 'memory_store', name: 'Store Memory', description: 'Save information to the agent\'s long‑term memory store', category: 'memory' },
  { id: 'memory_recall', name: 'Recall Memory', description: 'Retrieve previously stored information from memory', category: 'memory' },
  { id: 'enable_rag', name: 'Enable RAG', description: 'Capability flag: enables retrieval from the project\'s vector store (documents/KB). Not a tool by itself.', category: 'memory' },
  { id: 'reasoning_chain', name: 'Reasoning Chain', description: 'Multi-step reasoning', category: 'reasoning' },
  // PII / Privacy tools
  { id: 'pii_redact', name: 'PII Redact', description: 'Detect and redact PII in text (email, phone, SSN, credit cards, etc.)', category: 'security' },
  { id: 'pii_detect', name: 'PII Detect', description: 'Scan text for PII without modifying it', category: 'security' },
  // Audio tools
  { id: 'audio_transcribe', name: 'Audio Transcribe', description: 'Local speech-to-text transcription (Whisper, on-device)', category: 'audio' },
];
