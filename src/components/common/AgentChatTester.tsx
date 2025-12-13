/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect, useRef, memo } from 'react';
import {
  Send,
  X,
  Trash2,
  Download,
  Activity,
  CheckCircle,
  Circle,
  Zap,
  Users,
  Database,
  AlertCircle,
  Loader,
  Bookmark
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import apiClient from '@/lib/api-client';

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  banked?: boolean;
}

interface ToolCall {
  tool_name: string;
  arguments: Record<string, any>;
  result: string;
  timestamp: string;
}

interface SubAgentActivity {
  subagent_name: string;
  action: string;
  timestamp: string;
}

interface SessionMetrics {
  total_tokens: number;
  tool_calls: number;
  subagent_spawns: number;
  context_operations: number;
}

interface AgentChatTesterProps {
  agentId: number;
  agentName: string;
  onClose: () => void;
}

export default function AgentChatTester({
  agentId,
  agentName,
  onClose
}: AgentChatTesterProps) {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [toolCalls, setToolCalls] = useState<ToolCall[]>([]);
  const [subagentActivity, setSubagentActivity] = useState<SubAgentActivity[]>([]);
  const [metrics, setMetrics] = useState<SessionMetrics>({
    total_tokens: 0,
    tool_calls: 0,
    subagent_spawns: 0,
    context_operations: 0
  });
  const [todos, setTodos] = useState<Array<{ id: number; content: string; status: string }>>([]);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Start chat session on mount
  useEffect(() => {
    startSession();
    return () => {
      if (sessionId) {
        endSession();
      }
    };
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const startSession = async () => {
    try {
      const response = await apiClient.startChatSession(agentId);
      setSessionId(response.data.session_id);

      // Add system message
      setMessages([{
        role: 'system',
        content: `Chat session started with ${agentName}. Ask anything!`,
        timestamp: new Date().toISOString()
      }]);

    } catch (err) {
      setError('Failed to start chat session');
      console.error(err);
    }
  };

  const endSession = async () => {
    if (!sessionId) return;

    try {
      await apiClient.endChatSession(sessionId);
    } catch (err) {
      console.error('Failed to end session:', err);
    }
  };

  const sendMessage = async () => {
    if (!inputValue.trim() || !sessionId || isLoading) return;

    const userMessage = inputValue.trim();
    setInputValue('');
    setIsLoading(true);
    setError(null);

    // Add user message immediately
    const newUserMessage: ChatMessage = {
      role: 'user',
      content: userMessage,
      timestamp: new Date().toISOString()
    };
    setMessages(prev => [...prev, newUserMessage]);

    try {
      // Use streaming endpoint
      const response = await fetch(`${apiClient.baseURL}/api/chat/message/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessage
        })
      });

      if (!response.ok) throw new Error('Failed to send message');

      setIsStreaming(true);

      // Create placeholder for assistant message
      const assistantMessage: ChatMessage = {
        role: 'assistant',
        content: '',
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, assistantMessage]);

      // Read stream
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) throw new Error('No reader available');

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));

              if (data.type === 'chunk') {
                // Append to last message
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMsg = newMessages[newMessages.length - 1];
                  lastMsg.content += data.content;
                  return newMessages;
                });
              } else if (data.type === 'complete') {
                // Final message received
                setMessages(prev => {
                  const newMessages = [...prev];
                  const lastMsg = newMessages[newMessages.length - 1];
                  lastMsg.content = data.content;
                  return newMessages;
                });
              } else if (data.type === 'error') {
                setError(data.message);
              }
            } catch (e) {
              // Skip invalid JSON
            }
          }
        }
      }

      setIsStreaming(false);

      // Fetch updated metrics
      await fetchMetrics();

    } catch (err) {
      setError('Failed to send message');
      console.error(err);
      setIsStreaming(false);
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  };

  const fetchMetrics = async () => {
    if (!sessionId) return;

    try {
      const response = await apiClient.getChatMetrics(sessionId);
      const data = response.data;
      setMetrics(data.metrics);
      setToolCalls(data.tool_calls || []);
      setSubagentActivity(data.subagent_spawns || []);
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    }
  };

  const toggleBankMessage = async (messageIndex: number) => {
    if (!sessionId) return;

    const message = messages[messageIndex];
    if (message.role === 'system') return; // Don't allow banking system messages

    try {
      const isBanked = message.banked || false;

      if (isBanked) {
        // Unbank message
        await apiClient.apiFetch(`${apiClient.baseURL}/api/chat/${sessionId}/messages/${messageIndex}/bank`, {
          method: 'DELETE'
        });
      } else {
        // Bank message
        await apiClient.apiFetch(`${apiClient.baseURL}/api/chat/${sessionId}/messages/${messageIndex}/bank`, {
          method: 'POST'
        });
      }

      // Update local state
      setMessages(prev => {
        const newMessages = [...prev];
        newMessages[messageIndex] = {
          ...newMessages[messageIndex],
          banked: !isBanked
        };
        return newMessages;
      });
    } catch (err) {
      console.error('Failed to toggle bank message:', err);
      setError('Failed to update message banking status');
    }
  };

  const clearHistory = () => {
    setMessages([{
      role: 'system',
      content: 'Chat history cleared',
      timestamp: new Date().toISOString()
    }]);
    setToolCalls([]);
    setSubagentActivity([]);
    setTodos([]);
  };

  const downloadHistory = () => {
    const history = JSON.stringify({
      agent: agentName,
      session_id: sessionId,
      messages,
      tool_calls: toolCalls,
      subagent_activity: subagentActivity,
      metrics
    }, null, 2);

    const blob = new Blob([history], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat_history_${sessionId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-[#0a0a0a] border border-gray-800 rounded-xl w-full max-w-7xl h-[90vh] flex flex-col shadow-2xl">

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-800">
          <div>
            <h2 className="text-xl font-semibold text-white">Chat Tester - {agentName}</h2>
            <p className="text-sm text-gray-400 mt-1">
              Test your agent before exporting. Watch tools, subagents, and planning in action.
            </p>
          </div>

          <div className="flex gap-2">
            <button
              onClick={downloadHistory}
              className="p-2 text-gray-400 hover:text-white transition-colors"
              title="Download history"
            >
              <Download className="w-5 h-5" />
            </button>

            <button
              onClick={clearHistory}
              className="p-2 text-gray-400 hover:text-white transition-colors"
              title="Clear history"
            >
              <Trash2 className="w-5 h-5" />
            </button>

            <button
              onClick={onClose}
              className="p-2 text-gray-400 hover:text-white transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        <div className="flex flex-1 overflow-hidden">

          {/* Main Chat Area */}
          <div className="flex-1 flex flex-col">

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'} group`}
                >
                  <div className="flex items-start gap-2 max-w-[80%]">
                    {/* Bank button - Left side for assistant messages */}
                    {message.role === 'assistant' && (
                      <button
                        onClick={() => toggleBankMessage(index)}
                        className={`mt-1 p-1.5 rounded transition-all opacity-0 group-hover:opacity-100 ${message.banked
                          ? 'text-yellow-400 hover:text-yellow-500'
                          : 'text-gray-500 hover:text-yellow-400'
                          }`}
                        title={message.banked ? 'Unbank message' : 'Bank for future context'}
                      >
                        <Bookmark className={`w-4 h-4 ${message.banked ? 'fill-current' : ''}`} />
                      </button>
                    )}

                    <div
                      className={`flex-1 rounded-lg p-3 ${message.role === 'user'
                        ? 'bg-blue-600 text-white'
                        : message.role === 'assistant'
                          ? 'bg-gray-800 text-gray-100'
                          : 'bg-gray-700 text-gray-300'
                        }`}
                    >
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                      <div className="text-xs opacity-70 mt-1 flex items-center gap-2">
                        {new Date(message.timestamp).toLocaleTimeString()}
                        {message.banked && (
                          <span className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400">
                            <Bookmark className="w-3 h-3 fill-current" />
                            <span className="text-[10px] font-medium">Banked</span>
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Bank button - Right side for user messages */}
                    {message.role === 'user' && (
                      <button
                        onClick={() => toggleBankMessage(index)}
                        className={`mt-1 p-1.5 rounded transition-all opacity-0 group-hover:opacity-100 ${message.banked
                          ? 'text-yellow-400 hover:text-yellow-500'
                          : 'text-gray-400 hover:text-yellow-400'
                          }`}
                        title={message.banked ? 'Unbank message' : 'Bank for future context'}
                      >
                        <Bookmark className={`w-4 h-4 ${message.banked ? 'fill-current' : ''}`} />
                      </button>
                    )}
                  </div>
                </div>
              ))}

              {isStreaming && (
                <div className="flex justify-start">
                  <div className="bg-gray-800 rounded-lg p-3">
                    <div className="flex items-center gap-2 text-gray-400">
                      <Activity className="w-4 h-4 animate-pulse" />
                      <span className="text-sm">Agent is thinking...</span>
                    </div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Error Display */}
            {error && (
              <div className="mx-4 mb-2 p-3 bg-red-600/20 border border-red-600/50 rounded-lg flex items-center gap-2 text-red-400">
                <AlertCircle className="w-4 h-4" />
                <span className="text-sm">{error}</span>
                <button
                  onClick={() => setError(null)}
                  className="ml-auto text-red-400 hover:text-red-300"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}

            {/* Input */}
            <div className="p-4 border-t border-gray-800">
              <div className="flex gap-2">
                <input
                  ref={inputRef}
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  onKeyPress={handleKeyPress}
                  placeholder="Type your message..."
                  disabled={isLoading || !sessionId}
                  className="flex-1 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-white placeholder-gray-500"
                />

                <button
                  onClick={sendMessage}
                  disabled={isLoading || !inputValue.trim() || !sessionId}
                  className="px-6 py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-700 disabled:cursor-not-allowed rounded-lg transition-colors"
                >
                  <Send className="w-5 h-5" />
                </button>
              </div>
            </div>
          </div>

          {/* Sidebar - Metrics & Activity */}
          <div className="w-80 border-l border-gray-800 overflow-y-auto bg-gray-900/30">

            {/* Metrics */}
            <div className="p-4 border-b border-gray-800">
              <h3 className="text-sm font-semibold text-gray-400 mb-3">SESSION METRICS</h3>

              <div className="space-y-2">
                <MetricItem
                  icon={<Activity className="w-4 h-4" />}
                  label="Total Tokens"
                  value={metrics.total_tokens.toLocaleString()}
                />
                <MetricItem
                  icon={<Zap className="w-4 h-4" />}
                  label="Tool Calls"
                  value={metrics.tool_calls.toString()}
                />
                <MetricItem
                  icon={<Users className="w-4 h-4" />}
                  label="Subagent Spawns"
                  value={metrics.subagent_spawns.toString()}
                />
                <MetricItem
                  icon={<Database className="w-4 h-4" />}
                  label="Context Ops"
                  value={metrics.context_operations.toString()}
                />
              </div>
            </div>

            {/* Todo List */}
            {todos.length > 0 && (
              <div className="p-4 border-b border-gray-800">
                <h3 className="text-sm font-semibold text-gray-400 mb-3">TODO LIST</h3>
                <div className="space-y-2">
                  {todos.map((todo) => (
                    <div key={todo.id} className="flex items-center gap-2 text-sm">
                      {todo.status === 'completed' ? (
                        <CheckCircle className="w-4 h-4 text-green-500" />
                      ) : todo.status === 'in_progress' ? (
                        <Activity className="w-4 h-4 text-blue-500 animate-pulse" />
                      ) : (
                        <Circle className="w-4 h-4 text-gray-500" />
                      )}
                      <span className={todo.status === 'completed' ? 'line-through text-gray-500' : 'text-gray-300'}>
                        {todo.content}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Tool Calls */}
            {toolCalls.length > 0 && (
              <div className="p-4 border-b border-gray-800">
                <h3 className="text-sm font-semibold text-gray-400 mb-3">TOOL CALLS</h3>
                <div className="space-y-2">
                  {toolCalls.slice(-5).reverse().map((call, index) => (
                    <div key={index} className="p-2 bg-gray-800/50 rounded text-xs">
                      <div className="font-mono text-blue-400">{call.tool_name}</div>
                      <div className="text-gray-500 mt-1">{new Date(call.timestamp).toLocaleTimeString()}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Subagent Activity */}
            {subagentActivity.length > 0 && (
              <div className="p-4">
                <h3 className="text-sm font-semibold text-gray-400 mb-3">SUBAGENT ACTIVITY</h3>
                <div className="space-y-2">
                  {subagentActivity.slice(-5).reverse().map((activity, index) => (
                    <div key={index} className="p-2 bg-purple-600/10 border border-purple-600/30 rounded text-xs">
                      <div className="font-medium text-purple-400">{activity.subagent_name}</div>
                      <div className="text-gray-400 mt-1">{activity.action}</div>
                      <div className="text-gray-500 text-xs mt-1">
                        {new Date(activity.timestamp).toLocaleTimeString()}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

          </div>
        </div>
      </div>
    </div>
  );
}

function MetricItem({
  icon,
  label,
  value
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2 text-gray-400">
        {icon}
        <span className="text-sm">{label}</span>
      </div>
      <span className="text-sm font-semibold text-white">{value}</span>
    </div>
  );
}
