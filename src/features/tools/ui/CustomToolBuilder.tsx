/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import { useState, useEffect } from 'react';
import { AlertCircle, Play, Save, X, Settings, FileCode, TestTube, Eye, ArrowLeft, Check } from 'lucide-react';
import apiClient from "../../../lib/api-client";
import CollapsibleSection from '../../../components/ui/CollapsibleSection';
import ToolTemplateGallery from './ToolTemplateGallery';

interface ToolTemplate {
  template_id: string;
  name: string;
  description: string;
  category: string;
  tool_type: string;
  icon: string;
  priority?: number;
  is_featured?: boolean;
  config_template?: any;
  input_schema_template?: any;
  required_user_fields: string[];
  setup_instructions?: string;
  example_use_cases: string[];
  tags: string[];
}

interface CustomToolBuilderProps {
  onClose: () => void;
  onBack?: () => void;
  existingToolId?: string;
  skipTemplateStep?: boolean;
  initialTemplate?: {
    toolType: string;
    name: string;
    description: string;
    category: string;
    tags: string[];
    implementationConfig: any;
    inputSchema: any;
  };
}

const CustomToolBuilder = ({ onClose, onBack, existingToolId, skipTemplateStep = false, initialTemplate }: CustomToolBuilderProps) => {
  // Show template gallery first, unless editing or skipTemplateStep
  const [showingTemplateGallery, setShowingTemplateGallery] = useState(!existingToolId && !skipTemplateStep && !initialTemplate);
  const [selectedTemplate, setSelectedTemplate] = useState<ToolTemplate | null>(null);
  const [advancedMode, setAdvancedMode] = useState(skipTemplateStep);
  const [showInfoPanel, setShowInfoPanel] = useState(false);

  // Section expansion state
  const [expandedSections] = useState({
    basic: true,      // always expanded
    config: true,     // default expanded
    schema: true,     // default expanded
    test: false,      // default collapsed
    review: false     // default collapsed
  });

  // Form state
  const [toolId, setToolId] = useState('');
  const [toolName, setToolName] = useState('');
  const [description, setDescription] = useState('');
  const [category, setCategory] = useState('');
  const [tags, setTags] = useState<string[]>([]);

  // Implementation config (varies by tool type)
  const [implementationConfig, setImplementationConfig] = useState<any>({});

  // Input schema
  const [inputSchema, setInputSchema] = useState<any>({
    type: 'object',
    properties: {},
    required: []
  });

  // Testing
  const [testInput, setTestInput] = useState<any>({});
  const [testResult, setTestResult] = useState<{ success: boolean; output?: string; error?: string } | null>(null);
  const [testing, setTesting] = useState(false);

  // Validation & Saving
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const abortController = new AbortController();

    if (existingToolId) {
      // Load existing tool for editing
      loadExistingTool(existingToolId, abortController.signal);
    } else if (initialTemplate) {
      // Apply initial template
      setToolName(initialTemplate.name);
      setDescription(initialTemplate.description);
      setCategory(initialTemplate.category);
      setTags(initialTemplate.tags);
      setImplementationConfig(initialTemplate.implementationConfig);
      setInputSchema(initialTemplate.inputSchema);
      // Set a dummy template object so the form knows what type it is
      setSelectedTemplate({
        template_id: initialTemplate.toolType,
        name: initialTemplate.name,
        description: initialTemplate.description,
        category: initialTemplate.category,
        tool_type: initialTemplate.toolType,
        icon: '',
        config_template: initialTemplate.implementationConfig,
        input_schema_template: initialTemplate.inputSchema,
        required_user_fields: [],
        setup_instructions: '',
        example_use_cases: [],
        tags: initialTemplate.tags
      });
    }

    return () => {
      abortController.abort();
    };
  }, [existingToolId, initialTemplate]);

  const loadExistingTool = async (id: string, signal?: AbortSignal) => {
    try {
      const response = await apiClient.getCustomTool(id, signal ? { signal } : undefined);
      const tool = response.data;
      setToolId(tool.tool_id);
      setToolName(tool.name);
      setDescription(tool.description);
      setCategory(tool.category || '');
      setTags(tool.tags || []);
      setImplementationConfig(tool.implementation_config || {});
      setInputSchema(tool.input_schema || { type: 'object', properties: {}, required: [] });
      setAdvancedMode(tool.is_advanced_mode || false);

      // Reconstruct the selectedTemplate so the UI knows what type of tool this is
      // This is critical for rendering the correct configuration fields
      setSelectedTemplate({
        template_id: tool.template_type || tool.tool_type,
        name: tool.name,
        description: tool.description,
        category: tool.category || tool.tool_type,
        tool_type: tool.tool_type, // e.g., 'notification', 'api', 'image_video'
        icon: '',
        config_template: tool.implementation_config,
        input_schema_template: tool.input_schema,
        required_user_fields: [],
        setup_instructions: '',
        example_use_cases: [],
        tags: tool.tags || []
      });
    } catch (error) {
      // Ignore abort errors
      if (error instanceof Error && (error.name === 'AbortError' || error.name === 'CanceledError')) {
        return;
      }
      console.error('Failed to load tool:', error);
    }
  };

  const validateAllSections = (): boolean => {
    const errors: string[] = [];

    // Validate basic section
    if (!toolId.trim()) errors.push('Tool ID is required');
    if (!/^[a-zA-Z0-9_]+$/.test(toolId)) errors.push('Tool ID must contain only letters, numbers, and underscores');
    if (!toolName.trim()) errors.push('Tool name is required');
    if (!description.trim()) errors.push('Description is required (helps LLM understand the tool)');

    // Validate config section based on tool type
    if (selectedTemplate?.tool_type === 'notification') {
      if (!implementationConfig.webhook_url?.trim()) errors.push('Webhook URL is required');
    } else if (selectedTemplate?.tool_type === 'api') {
      if (!implementationConfig.url?.trim()) errors.push('API URL is required');
      if (!implementationConfig.method) errors.push('HTTP method is required');
    } else if (selectedTemplate?.tool_type === 'image_video') {
      // API key is now managed in Settings, not required here
      if (!implementationConfig.provider?.trim()) errors.push('Provider is required');
      if (!implementationConfig.model?.trim()) errors.push('Model is required');
    }

    // Validate schema section
    if (!inputSchema.properties || Object.keys(inputSchema.properties).length === 0) {
      errors.push('At least one input parameter is required');
    }

    setValidationErrors(errors);
    return errors.length === 0;
  };

  const handleTest = async () => {
    setTesting(true);
    try {
      // First, create/update the tool temporarily
      const toolData = {
        tool_id: toolId,
        name: toolName,
        description,
        tool_type: selectedTemplate?.tool_type || 'api',
        template_type: selectedTemplate?.template_id || null,
        implementation_config: implementationConfig,
        input_schema: inputSchema,
        output_format: 'string',
        is_template_based: !advancedMode,
        is_advanced_mode: advancedMode,
        category,
        tags
      };

      // Save tool first (will update if exists)
      try {
        if (existingToolId) {
          await apiClient.updateCustomTool(toolId, toolData);
        } else {
          // Try to create, if it already exists, update it instead
          await apiClient.createCustomTool(toolData);
        }
      } catch (createError: any) {
        // If tool already exists (409 or 400 with "already exists"), try updating it
        const detail = createError.response?.data?.detail;
        const detailStr = typeof detail === 'string' ? detail : '';

        if (createError.response?.status === 409 ||
          (createError.response?.status === 400 && detailStr.includes('already exists'))) {
          await apiClient.updateCustomTool(toolId, toolData);
        } else {
          throw createError;
        }
      }

      // Then test it
      const response = await apiClient.testCustomTool(toolId, testInput);

      setTestResult(response.data);
    } catch (error: any) {
      // Extract error message from various possible error structures
      let errorMessage = 'Unknown error occurred';

      if (error.response?.data) {
        const data = error.response.data;
        // Handle different error response formats
        if (typeof data === 'string') {
          errorMessage = data;
        } else if (data.detail) {
          errorMessage = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        } else if (data.message) {
          errorMessage = data.message;
          // Include validation errors if present
          if (data.errors && Array.isArray(data.errors) && data.errors.length > 0) {
            errorMessage += '\n\nValidation errors:\n' + data.errors.map((e: any) => `- ${typeof e === 'string' ? e : JSON.stringify(e)}`).join('\n');
          }
        } else {
          errorMessage = JSON.stringify(data);
        }
      } else if (error.message) {
        errorMessage = error.message;
      }

      setTestResult({
        success: false,
        error: errorMessage
      });
    } finally {
      setTesting(false);
    }
  };

  const handleTemplateSelect = async (template: ToolTemplate) => {
    setSelectedTemplate(template);
    setShowingTemplateGallery(false);

    // Pre-fill form with template data
    const templateDetails = await apiClient.getToolTemplate(template.template_id);
    const templateData = templateDetails.data;

    setToolName(templateData.name);
    setDescription(templateData.description);
    setCategory(templateData.category);
    setTags(templateData.tags || []);
    setImplementationConfig(templateData.config_template?.implementation_config || {});
    setInputSchema(templateData.input_schema_template || {
      type: 'object',
      properties: {},
      required: []
    });
  };

  const handleStartFromScratch = () => {
    setAdvancedMode(true);
    setShowingTemplateGallery(false);
  };

  const handleSave = async () => {
    // Clear previous errors before validating again
    setValidationErrors([]);

    const isValid = validateAllSections();

    if (!isValid) {
      alert('Please fix validation errors before saving');
      // Scroll to top to show errors
      window.scrollTo({ top: 0, behavior: 'smooth' });
      return;
    }

    setSaving(true);
    try {
      const toolData = {
        tool_id: toolId,
        name: toolName,
        description,
        tool_type: selectedTemplate?.tool_type || 'api',
        template_type: selectedTemplate?.template_id || null,
        implementation_config: implementationConfig,
        input_schema: inputSchema,
        output_format: 'string',
        is_template_based: !advancedMode,
        is_advanced_mode: advancedMode,
        category,
        tags
      };


      if (existingToolId) {
        await apiClient.updateCustomTool(toolId, toolData);
      } else {
        await apiClient.createCustomTool(toolData);
      }

      alert(`✓ Tool "${toolName}" saved successfully!`);
      onClose();
    } catch (error: any) {
      console.error('[CustomToolBuilder] Save failed with error:', error);

      // Extract error message from various possible error structures
      let errorMsg = 'Unknown error occurred';
      const errors: string[] = [];

      if (error.response?.data) {
        console.error('[CustomToolBuilder] Error response data:', error.response.data);
        const data = error.response.data;
        if (typeof data === 'string') {
          errorMsg = data;
        } else if (data.detail) {
          errorMsg = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
        } else if (data.message) {
          errorMsg = data.message;
          // Include validation errors if present
          if (data.errors && Array.isArray(data.errors)) {
            errors.push(...data.errors.map((e: any) => typeof e === 'string' ? e : JSON.stringify(e)));
          }
        } else {
          errorMsg = JSON.stringify(data);
        }
      } else if (error.message) {
        errorMsg = error.message;
      }

      console.error('[CustomToolBuilder] Parsed error message:', errorMsg);
      const allErrors = [`Failed to save: ${errorMsg}`, ...errors];
      setValidationErrors(allErrors);
      alert(`❌ Save failed: ${errorMsg}`);
      // Scroll to top to show error
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } finally {
      setSaving(false);
    }
  };


  const renderAllSections = () => {
    return (
      <div className="space-y-4">
        {/* Basic Information - Always Expanded */}
        <CollapsibleSection
          title="Basic Information"
          defaultExpanded={true}
          alwaysExpanded={true}
          hasError={validationErrors.some(e =>
            e.includes('Tool ID') || e.includes('Tool name') || e.includes('Description')
          )}
        >
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Tool ID <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={toolId}
                onChange={(e) => setToolId(e.target.value)}
                placeholder="my_custom_tool"
                disabled={!!existingToolId}
                className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                style={{
                  backgroundColor: existingToolId ? 'var(--color-background-dark)' : 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
                onFocus={(e) => !existingToolId && (e.currentTarget.style.borderColor = 'var(--color-primary)')}
                onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
              />
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                Unique identifier (letters, numbers, underscores only)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Tool Name <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={toolName}
                onChange={(e) => setToolName(e.target.value)}
                placeholder="My Custom Tool"
                className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
              />
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                Display name shown in the UI (can be different from Tool ID)
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Description <span className="text-red-500">*</span>
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Describe what this tool does... (This helps the LLM understand when to use it)"
                rows={4}
                className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
              />
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                Be specific - this description is shown to the LLM to help it decide when to use the tool
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Category (Optional)
              </label>
              <input
                type="text"
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                placeholder="e.g., notifications, integrations"
                className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
              />
            </div>

            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Tags (comma-separated)
              </label>
              <input
                type="text"
                value={tags.join(', ')}
                onChange={(e) => setTags(e.target.value.split(',').map(t => t.trim()).filter(Boolean))}
                placeholder="slack, notification, alerts"
                className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
              />
            </div>
          </div>
        </CollapsibleSection>

        {/* Configuration Section */}
        <CollapsibleSection
          title="Tool Configuration"
          icon={<Settings className="w-5 h-5" />}
          defaultExpanded={expandedSections.config}
          hasError={validationErrors.some(e =>
            e.includes('Webhook') || e.includes('API URL') || e.includes('API key') || e.includes('Provider') || e.includes('Model') || e.includes('HTTP method')
          )}
        >
          {renderConfigStep()}
        </CollapsibleSection>

        {/* Input Schema Section */}
        <CollapsibleSection
          title="Input Schema"
          icon={<FileCode className="w-5 h-5" />}
          defaultExpanded={expandedSections.schema}
          hasError={validationErrors.some(e => e.includes('input parameter'))}
        >
          {renderSchemaStep()}
        </CollapsibleSection>

        {/* Test Section */}
        <CollapsibleSection
          title="Test Tool"
          icon={<TestTube className="w-5 h-5" />}
          defaultExpanded={expandedSections.test}
        >
          {renderTestStep()}
        </CollapsibleSection>

        {/* Review Section */}
        <CollapsibleSection
          title="Review & Summary"
          icon={<Eye className="w-5 h-5" />}
          defaultExpanded={expandedSections.review}
        >
          {renderReviewStep()}
        </CollapsibleSection>
      </div>
    );
  };

  const renderConfigStep = () => {
    const toolType = selectedTemplate?.tool_type || 'api';

    return (
      <div className="space-y-4">
        <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
          Configure the specific settings for your {toolType} tool
        </p>

        {/* Notification Tool Config */}
        {toolType === 'notification' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Provider <span className="text-red-500">*</span>
              </label>
              <select
                value={implementationConfig.provider || 'discord'}
                onChange={(e) => setImplementationConfig({ ...implementationConfig, provider: e.target.value })}
                className="w-full px-4 py-2 rounded-lg border text-sm"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
              >
                <option value="slack">Slack</option>
                <option value="discord">Discord</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Webhook URL <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                value={implementationConfig.webhook_url || ''}
                onChange={(e) => setImplementationConfig({ ...implementationConfig, webhook_url: e.target.value })}
                placeholder="https://hooks.slack.com/services/..."
                className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
              />
              <div className="mt-2 p-3 rounded-lg text-sm" style={{ backgroundColor: 'rgba(59, 130, 246, 0.1)', borderColor: 'rgba(59, 130, 246, 0.3)', color: 'var(--color-text-primary)' }}>
                <strong>How to get webhook URL:</strong><br />
                {implementationConfig.provider === 'slack'
                  ? '1. Go to https://api.slack.com/messaging/webhooks\n2. Create Incoming Webhook\n3. Copy the URL'
                  : '1. Go to Server Settings → Integrations → Webhooks\n2. Create New Webhook\n3. Copy the URL'}
              </div>
            </div>

            {implementationConfig.provider === 'slack' && (
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                  Default Channel
                </label>
                <input
                  type="text"
                  value={implementationConfig.channel || '#general'}
                  onChange={(e) => setImplementationConfig({ ...implementationConfig, channel: e.target.value })}
                  placeholder="#general"
                  className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                  style={{
                    backgroundColor: 'var(--color-input-background)',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)'
                  }}
                  onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                  onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                />
              </div>
            )}

            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Message Template
              </label>
              <textarea
                value={implementationConfig.message_template || '{message}'}
                onChange={(e) => setImplementationConfig({ ...implementationConfig, message_template: e.target.value })}
                placeholder="{message}"
                rows={3}
                className="w-full px-4 py-2 rounded-lg border text-sm font-mono transition-all"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
              />
              <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                Use {'{variable}'} syntax for dynamic values
              </p>
            </div>
          </div>
        )}

        {/* API Tool Config */}
        {toolType === 'api' && (
          <div className="space-y-4">
            {/* Twitter-specific configuration */}
            {implementationConfig.provider === 'twitter' && (
              <>
                <div className="p-4 rounded-lg border-l-4" style={{
                  backgroundColor: 'rgba(59, 130, 246, 0.1)',
                  borderLeftColor: 'var(--color-primary)',
                  borderWidth: '0 0 0 4px'
                }}>
                  <div className="flex items-start justify-between mb-2">
                    <p className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>
                      Twitter API Setup Required
                    </p>
                    <button
                      onClick={() => setShowInfoPanel(true)}
                      className="flex items-center gap-1 px-2 py-1 text-xs rounded transition-colors"
                      style={{
                        backgroundColor: 'var(--color-primary)',
                        color: 'white'
                      }}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: '16px' }}>info</span>
                      View Rate Limits
                    </button>
                  </div>
                  <p className="text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
                    Get your API credentials from the Twitter Developer Portal:
                  </p>
                  <ol className="text-xs space-y-1 mb-3" style={{ color: 'var(--color-text-muted)', paddingLeft: '1.5rem' }}>
                    <li>Go to <a href="https://developer.twitter.com/en/portal/dashboard" target="_blank" rel="noopener noreferrer" className="underline" style={{ color: 'var(--color-primary)' }}>Twitter Developer Portal</a></li>
                    <li>Create a new App (or use existing)</li>
                    <li>Navigate to "Keys and tokens" section</li>
                    <li>Generate and copy your API credentials below</li>
                  </ol>
                  <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    <strong>Free tier limits:</strong> 1,500 tweets/month (post), 500,000 tweets/month (read)
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    API Key (Consumer Key) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="password"
                    value={implementationConfig.api_key || ''}
                    onChange={(e) => setImplementationConfig({ ...implementationConfig, api_key: e.target.value })}
                    placeholder="Your Twitter API Key"
                    className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                    onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                    onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                  />
                  <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    Find in Developer Portal → Your App → Keys and tokens → Consumer Keys
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    API Secret (Consumer Secret) <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="password"
                    value={implementationConfig.api_secret || ''}
                    onChange={(e) => setImplementationConfig({ ...implementationConfig, api_secret: e.target.value })}
                    placeholder="Your Twitter API Secret"
                    className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                    onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                    onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                  />
                  <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    Find in Developer Portal → Your App → Keys and tokens → Consumer Keys
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    Access Token <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="password"
                    value={implementationConfig.access_token || ''}
                    onChange={(e) => setImplementationConfig({ ...implementationConfig, access_token: e.target.value })}
                    placeholder="Your Twitter Access Token"
                    className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                    onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                    onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                  />
                  <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    Find in Developer Portal → Your App → Keys and tokens → Authentication Tokens
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    Access Token Secret <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="password"
                    value={implementationConfig.access_token_secret || ''}
                    onChange={(e) => setImplementationConfig({ ...implementationConfig, access_token_secret: e.target.value })}
                    placeholder="Your Twitter Access Token Secret"
                    className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                    onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                    onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                  />
                  <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    Find in Developer Portal → Your App → Keys and tokens → Authentication Tokens
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    Bearer Token (Optional - for read-only)
                  </label>
                  <input
                    type="password"
                    value={implementationConfig.bearer_token || ''}
                    onChange={(e) => setImplementationConfig({ ...implementationConfig, bearer_token: e.target.value })}
                    placeholder="Bearer Token (alternative to OAuth)"
                    className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                    onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                    onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                  />
                  <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    Use Bearer Token for read-only operations (timeline, search). Not required if using OAuth tokens above.
                  </p>
                </div>

                <div className="p-3 rounded-lg" style={{ backgroundColor: 'rgba(234, 179, 8, 0.1)', borderColor: 'rgba(234, 179, 8, 0.3)' }}>
                  <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                    <strong>⚠️ Important:</strong> Your API credentials are encrypted and stored securely. Never share them publicly.
                    For posting tweets, you need Read + Write permissions in your Twitter App settings.
                  </p>
                </div>
              </>
            )}

            {/* Generic API configuration (for non-Twitter APIs) */}
            {implementationConfig.provider !== 'twitter' && (
              <>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    HTTP Method <span className="text-red-500">*</span>
                  </label>
                  <select
                    value={implementationConfig.method || 'GET'}
                    onChange={(e) => setImplementationConfig({ ...implementationConfig, method: e.target.value })}
                    className="w-full px-4 py-2 rounded-lg border text-sm"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                  >
                    <option value="GET">GET</option>
                    <option value="POST">POST</option>
                    <option value="PUT">PUT</option>
                    <option value="DELETE">DELETE</option>
                    <option value="PATCH">PATCH</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    URL <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={implementationConfig.url || ''}
                    onChange={(e) => setImplementationConfig({ ...implementationConfig, url: e.target.value })}
                    placeholder="https://api.example.com/{endpoint}"
                    className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                    onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                    onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                  />
                  <p className="text-xs mt-1" style={{ color: 'var(--color-text-muted)' }}>
                    Use {'{variable}'} for dynamic path parameters
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    Timeout (seconds)
                  </label>
                  <input
                    type="number"
                    value={implementationConfig.timeout || 30}
                    onChange={(e) => setImplementationConfig({ ...implementationConfig, timeout: parseInt(e.target.value) })}
                    className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                    onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                    onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
                  />
                </div>
              </>
            )}
          </div>
        )}

        {/* Image/Video Tool Config */}
        {toolType === 'image_video' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Provider <span className="text-red-500">*</span>
              </label>
              <select
                value={implementationConfig.provider || 'google'}
                onChange={(e) => {
                  const newProvider = e.target.value;
                  // Auto-select default model for each provider
                  const defaultModel = newProvider === 'google' ? 'gemini-2.5-flash-image' : 'dall-e-3';
                  setImplementationConfig({
                    ...implementationConfig,
                    provider: newProvider,
                    model: defaultModel
                  });
                }}
                className="w-full px-4 py-2 rounded-lg border text-sm"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
              >
                <option value="google">Google (Nano Banana, Imagen 3, Veo 3)</option>
                <option value="openai">OpenAI (GPT-Image-1.5, DALL-E 3, Sora)</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                Model <span className="text-red-500">*</span>
              </label>
              <select
                value={implementationConfig.model || (implementationConfig.provider === 'google' ? 'gemini-2.5-flash-image' : 'dall-e-3')}
                onChange={(e) => setImplementationConfig({ ...implementationConfig, model: e.target.value })}
                className="w-full px-4 py-2 rounded-lg border text-sm"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
              >
                {implementationConfig.provider === 'openai' ? (
                  <>
                    <option value="gpt-image-1.5">GPT-Image-1.5 (Image)</option>
                    <option value="dall-e-3">DALL-E 3 (Image)</option>
                    <option value="sora">Sora (Video)</option>
                  </>
                ) : (
                  <>
                    <option value="gemini-2.5-flash-image">🍌 Nano Banana (Gemini 2.5 Flash) - RECOMMENDED</option>
                    <option value="imagen-3">Imagen 3 (Image)</option>
                    <option value="veo-3">Veo 3 (Video)</option>
                    <option value="veo-3.1">Veo 3.1 (Video)</option>
                  </>
                )}
              </select>
            </div>

            {/* API Key Configuration Note */}
            <div className="p-3 rounded-lg" style={{
              backgroundColor: 'rgba(99, 102, 241, 0.1)',
              border: '1px solid rgba(99, 102, 241, 0.2)'
            }}>
              <p className="text-xs font-medium mb-1" style={{ color: 'var(--color-primary)' }}>
                🔑 API Key Configuration
              </p>
              <p className="text-xs" style={{ color: 'var(--color-text-muted)' }}>
                API keys are managed in Settings → API Keys. Your <strong>GEMINI_API_KEY</strong> and <strong>OPENAI_API_KEY</strong> are automatically used for Google and OpenAI models.
              </p>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Schema editing state - track property names being edited locally
  const [editingPropNames, setEditingPropNames] = useState<Record<string, string>>({});

  const renderSchemaStep = () => {
    const properties = inputSchema.properties || {};
    const required = inputSchema.required || [];

    const addProperty = () => {
      const newProp = `param_${Object.keys(properties).length + 1}`;
      setInputSchema({
        ...inputSchema,
        properties: {
          ...properties,
          [newProp]: {
            type: 'string',
            description: ''
          }
        }
      });
    };

    const removeProperty = (propName: string) => {
      const newProps = { ...properties };
      delete newProps[propName];
      // Also clean up editing state
      const newEditingNames = { ...editingPropNames };
      delete newEditingNames[propName];
      setEditingPropNames(newEditingNames);
      setInputSchema({
        ...inputSchema,
        properties: newProps,
        required: required.filter((r: string) => r !== propName)
      });
    };

    const updatePropertyName = (oldName: string, newName: string) => {
      if (oldName === newName) return;
      if (properties[newName]) {
        alert('Property name already exists');
        // Reset the editing state to the original name
        setEditingPropNames(prev => ({ ...prev, [oldName]: oldName }));
        return;
      }

      const newProps = { ...properties };
      const propData = newProps[oldName];
      delete newProps[oldName];
      newProps[newName] = propData;

      // Clean up editing state
      const newEditingNames = { ...editingPropNames };
      delete newEditingNames[oldName];
      setEditingPropNames(newEditingNames);

      setInputSchema({
        ...inputSchema,
        properties: newProps,
        required: required.map((r: string) => r === oldName ? newName : r)
      });
    };

    const updatePropertyData = (propName: string, updates: any) => {
      setInputSchema({
        ...inputSchema,
        properties: {
          ...properties,
          [propName]: { ...properties[propName], ...updates }
        }
      });
    };

    const toggleRequired = (propName: string) => {
      const newRequired = required.includes(propName)
        ? required.filter((r: string) => r !== propName)
        : [...required, propName];

      setInputSchema({ ...inputSchema, required: newRequired });
    };

    // Get property entries with stable indices
    const propertyEntries = Object.entries(properties);

    return (
      <div className="space-y-4">
        <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
          Define what parameters your tool accepts
        </p>

        <div className="space-y-4">
          {propertyEntries.map(([propName, prop]: [string, any], index) => {
            // Use local editing state for the name input, fall back to actual propName
            const displayName = editingPropNames[propName] ?? propName;

            return (
              <div key={`prop-${index}`} className="p-4 rounded-lg border" style={{ borderColor: 'var(--color-border-dark)', backgroundColor: 'var(--color-panel-dark)' }}>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                      Parameter Name
                    </label>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => {
                        // Update local editing state only - don't modify schema yet
                        setEditingPropNames(prev => ({ ...prev, [propName]: e.target.value }));
                      }}
                      onBlur={(e) => {
                        // Commit the name change when input loses focus
                        const newName = e.target.value.trim();
                        if (newName && newName !== propName) {
                          updatePropertyName(propName, newName);
                        } else if (!newName) {
                          // Reset to original if empty
                          setEditingPropNames(prev => {
                            const next = { ...prev };
                            delete next[propName];
                            return next;
                          });
                        }
                      }}
                      onKeyDown={(e) => {
                        // Also commit on Enter key
                        if (e.key === 'Enter') {
                          e.currentTarget.blur();
                        }
                      }}
                      className="w-full px-3 py-2 rounded-lg border text-sm"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)'
                      }}
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                      Type
                    </label>
                    <select
                      value={prop.type || 'string'}
                      onChange={(e) => updatePropertyData(propName, { type: e.target.value })}
                      className="w-full px-3 py-2 rounded-lg border text-sm"
                      style={{
                        backgroundColor: 'var(--color-input-background)',
                        borderColor: 'var(--color-border-dark)',
                        color: 'var(--color-text-primary)'
                      }}
                    >
                      <option value="string">String</option>
                      <option value="integer">Integer</option>
                      <option value="number">Number</option>
                      <option value="boolean">Boolean</option>
                    </select>
                  </div>
                </div>

                <div className="mt-3">
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                    Description
                  </label>
                  <input
                    type="text"
                    value={prop.description || ''}
                    onChange={(e) => updatePropertyData(propName, { description: e.target.value })}
                    placeholder="What is this parameter for?"
                    className="w-full px-3 py-2 rounded-lg border text-sm"
                    style={{
                      backgroundColor: 'var(--color-input-background)',
                      borderColor: 'var(--color-border-dark)',
                      color: 'var(--color-text-primary)'
                    }}
                  />
                </div>

                <div className="mt-3 flex items-center justify-between">
                  <label className="flex items-center gap-2 text-sm">
                    <input
                      type="checkbox"
                      checked={required.includes(propName)}
                      onChange={() => toggleRequired(propName)}
                      className="rounded border-gray-300 focus:ring-2"
                      style={{ accentColor: 'var(--color-primary)' }}
                    />
                    <span style={{ color: 'var(--color-text-primary)' }}>Required parameter</span>
                  </label>

                  <button
                    onClick={() => removeProperty(propName)}
                    className="text-red-600 hover:text-red-700 text-sm font-medium"
                  >
                    Remove
                  </button>
                </div>
              </div>
            );
          })}

          <button
            onClick={addProperty}
            className="w-full p-3 border-2 border-dashed rounded-lg font-medium transition-colors"
            style={{
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-muted)'
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-primary)';
              e.currentTarget.style.color = 'var(--color-primary)';
              e.currentTarget.style.backgroundColor = 'var(--color-background-dark)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--color-border-dark)';
              e.currentTarget.style.color = 'var(--color-text-muted)';
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            + Add Parameter
          </button>
        </div>
      </div>
    );
  };

  // Initialize test input when schema changes
  useEffect(() => {
    const properties = inputSchema.properties || {};
    const initialInput: any = {};
    Object.keys(properties).forEach(key => {
      initialInput[key] = testInput[key] || '';
    });
    setTestInput(initialInput);
  }, [inputSchema]);

  const renderTestStep = () => {
    const properties = inputSchema.properties || {};

    return (
      <div className="space-y-4">
        <p className="text-sm mb-4" style={{ color: 'var(--color-text-muted)' }}>
          Test the tool with sample input to make sure it works
        </p>

        {/* Test Input Form */}
        <div className="space-y-4 mb-6">
          <h4 className="font-medium" style={{ color: 'var(--color-text-primary)' }}>Test Input</h4>
          {Object.entries(properties).map(([propName, prop]: [string, any]) => (
            <div key={propName}>
              <label className="block text-sm font-medium mb-1" style={{ color: 'var(--color-text-primary)' }}>
                {propName}
                {inputSchema.required?.includes(propName) && (
                  <span className="text-red-500 ml-1">*</span>
                )}
              </label>
              <input
                type={prop.type === 'integer' || prop.type === 'number' ? 'number' : 'text'}
                value={testInput[propName] || ''}
                onChange={(e) => setTestInput({ ...testInput, [propName]: e.target.value })}
                placeholder={prop.description || `Enter ${propName}`}
                className="w-full px-4 py-2 rounded-lg border text-sm transition-all"
                style={{
                  backgroundColor: 'var(--color-input-background)',
                  borderColor: 'var(--color-border-dark)',
                  color: 'var(--color-text-primary)'
                }}
                onFocus={(e) => e.currentTarget.style.borderColor = 'var(--color-primary)'}
                onBlur={(e) => e.currentTarget.style.borderColor = 'var(--color-border-dark)'}
              />
            </div>
          ))}
        </div>

        {/* Test Button */}
        <button
          onClick={handleTest}
          disabled={testing}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          style={{ backgroundColor: 'var(--color-primary)' }}
        >
          {testing ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Testing...
            </>
          ) : (
            <>
              <Play className="w-4 h-4" />
              Run Test
            </>
          )}
        </button>

        {/* Test Results */}
        {testResult && (
          <div className={`mt-4 p-4 rounded-lg`} style={{
            backgroundColor: testResult.success ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            borderWidth: '1px',
            borderStyle: 'solid',
            borderColor: testResult.success ? 'rgba(16, 185, 129, 0.3)' : 'rgba(239, 68, 68, 0.3)'
          }}>
            <div className="flex items-start gap-2">
              {testResult.success ? (
                <Check className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
              ) : (
                <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              )}
              <div className="flex-1">
                <h4 className={`font-semibold ${testResult.success ? 'text-green-900' : 'text-red-900'}`}>
                  {testResult.success ? 'Test Successful!' : 'Test Failed'}
                </h4>
                {testResult.success ? (
                  <pre className="mt-2 text-sm text-green-800 whitespace-pre-wrap font-mono p-3 rounded border border-green-200 overflow-auto max-h-64" style={{ backgroundColor: '#ffffff' }}>
                    {testResult.output}
                  </pre>
                ) : (
                  <pre className="mt-2 text-sm text-red-800 whitespace-pre-wrap p-3 rounded border border-red-200 overflow-auto max-h-64" style={{ backgroundColor: '#ffffff' }}>
                    {testResult.error}
                  </pre>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  const generateToolCode = () => {
    const toolType = selectedTemplate?.tool_type || 'api';
    const properties = inputSchema.properties || {};
    const required = inputSchema.required || [];

    // Generate parameter type hints
    const paramDefs = Object.entries(properties).map(([name, prop]: [string, any]) => {
      const typeMap: Record<string, string> = {
        'string': 'str',
        'integer': 'int',
        'number': 'float',
        'boolean': 'bool'
      };
      const pyType = typeMap[prop.type] || 'str';
      const isRequired = required.includes(name);
      const defaultVal = !isRequired ? ' = None' : '';
      const optionalPrefix = !isRequired ? 'Optional[' : '';
      const optionalSuffix = !isRequired ? ']' : '';
      return `    ${name}: ${optionalPrefix}${pyType}${optionalSuffix}${defaultVal}`;
    }).join(',\n');

    // Generate tool implementation based on type
    let implementationCode = '';

    if (toolType === 'notification') {
      const provider = implementationConfig.provider || 'discord';
      const webhookUrl = implementationConfig.webhook_url || 'YOUR_WEBHOOK_URL';

      implementationCode = `async def ${toolId}(
${paramDefs}
) -> str:
    """${description}"""
    import httpx

    webhook_url = "${webhookUrl}"

    ${provider === 'discord' ? `# Discord webhook payload
    payload = {
        "username": "${implementationConfig.username || 'LangConfig Bot'}",
        "content": message,
    }

    # Add embeds if title is provided
    if title:
        payload["embeds"] = [{
            "title": title,
            "description": message,
            "color": int((color or "#5865F2").replace("#", ""), 16) if color else 0x5865F2
        }]
        payload["content"] = ""  # Clear content when using embeds` : `# Slack webhook payload
    payload = {
        "text": message,
        "channel": channel or "#general"
    }`}

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()
        return f"Message sent to ${provider} successfully"`;
    } else if (toolType === 'api') {
      const method = implementationConfig.method || 'GET';
      const url = implementationConfig.url || 'https://api.example.com/endpoint';

      implementationCode = `async def ${toolId}(
${paramDefs}
) -> str:
    """${description}"""
    import httpx

    url = "${url}"

    async with httpx.AsyncClient(timeout=${implementationConfig.timeout || 30}) as client:
        response = await client.${method.toLowerCase()}(
            url,
            ${method !== 'GET' ? 'json={k: v for k, v in locals().items() if k not in ["client", "response", "url"]},' : ''}
            headers={"Content-Type": "application/json"}
        )
        response.raise_for_status()
        return response.text`;
    } else {
      implementationCode = `async def ${toolId}(
${paramDefs}
) -> str:
    """${description}"""
    # TODO: Implement your custom tool logic here
    pass`;
    }

    return `from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import StructuredTool
from typing import Optional
import httpx

# Tool function
${implementationCode}

# Create the LangChain tool
${toolId}_tool = StructuredTool.from_function(
    coroutine=${toolId},
    name="${toolId}",
    description="${description}",
)

# Add to your agent
# agent = create_agent(
#     model="gpt-4o",
#     tools=[${toolId}_tool],
#     middleware=[...],
# )`;
  };

  const renderReviewStep = () => {
    const generatedCode = generateToolCode();

    return (
      <div className="space-y-4">
        <p className="text-sm mb-6" style={{ color: 'var(--color-text-muted)' }}>
          Review your tool configuration and copy the implementation code
        </p>

        <div className="space-y-4">
          {/* Basic Info */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
            <h4 className="font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>Basic Information</h4>
            <dl className="space-y-2">
              <div className="flex">
                <dt className="w-32 text-sm" style={{ color: 'var(--color-text-muted)' }}>Tool ID:</dt>
                <dd className="text-sm font-mono" style={{ color: 'var(--color-text-primary)' }}>{toolId}</dd>
              </div>
              <div className="flex">
                <dt className="w-32 text-sm" style={{ color: 'var(--color-text-muted)' }}>Name:</dt>
                <dd className="text-sm" style={{ color: 'var(--color-text-primary)' }}>{toolName}</dd>
              </div>
              <div className="flex">
                <dt className="w-32 text-sm" style={{ color: 'var(--color-text-muted)' }}>Type:</dt>
                <dd className="text-sm" style={{ color: 'var(--color-text-primary)' }}>{selectedTemplate?.tool_type || 'custom'}</dd>
              </div>
              <div className="flex">
                <dt className="w-32 text-sm" style={{ color: 'var(--color-text-muted)' }}>Description:</dt>
                <dd className="text-sm" style={{ color: 'var(--color-text-primary)' }}>{description}</dd>
              </div>
            </dl>
          </div>

          {/* Generated LangChain Code */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
            <div className="flex items-center justify-between mb-3">
              <h4 className="font-semibold" style={{ color: 'var(--color-text-primary)' }}>LangChain Implementation Code</h4>
              <button
                onClick={() => {
                  navigator.clipboard.writeText(generatedCode);
                }}
                className="px-3 py-1 text-xs rounded transition-colors"
                style={{
                  backgroundColor: 'var(--color-primary)',
                  color: 'white'
                }}
              >
                Copy Code
              </button>
            </div>
            <p className="text-xs mb-2" style={{ color: 'var(--color-text-muted)' }}>
              Use this code to integrate your custom tool into LangChain agents. Based on <a href="https://docs.langchain.com/oss/python/langchain/middleware/custom" target="_blank" rel="noopener noreferrer" className="underline" style={{ color: 'var(--color-primary)' }}>LangChain middleware documentation</a>.
            </p>
            <pre className="text-xs font-mono p-3 rounded border overflow-auto max-h-96" style={{
              backgroundColor: 'var(--color-input-background)',
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-primary)'
            }}>
              {generatedCode}
            </pre>
          </div>

          {/* Input Schema Summary */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
            <h4 className="font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>Input Parameters</h4>
            <div className="space-y-2">
              {Object.entries(inputSchema.properties || {}).map(([name, prop]: [string, any]) => (
                <div key={name} className="flex items-start gap-2 text-sm">
                  <span className="font-mono" style={{ color: 'var(--color-primary)' }}>{name}</span>
                  <span style={{ color: 'var(--color-text-muted)' }}>:</span>
                  <span style={{ color: 'var(--color-text-muted)' }}>{prop.type}</span>
                  {inputSchema.required?.includes(name) && (
                    <span className="text-red-500 text-xs">(required)</span>
                  )}
                  {prop.description && (
                    <span className="italic" style={{ color: 'var(--color-text-muted)' }}>- {prop.description}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Configuration Summary */}
          <div className="p-4 rounded-lg" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
            <h4 className="font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>Configuration JSON</h4>
            <pre className="text-xs font-mono p-3 rounded border overflow-auto max-h-48" style={{
              backgroundColor: 'var(--color-input-background)',
              borderColor: 'var(--color-border-dark)',
              color: 'var(--color-text-muted)'
            }}>
              {JSON.stringify(implementationConfig, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden" style={{ backgroundColor: 'var(--color-background-dark)' }}>
      {/* Fixed Header - Primary Color with White Text */}
      <div className="border-b p-6" style={{
        backgroundColor: 'var(--color-primary)',
        borderBottomColor: 'var(--color-border-dark)'
      }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3 flex-1">
              <button
                onClick={() => {
                  // If we're in the form view (not showing template gallery), go back to template selection
                  if (!showingTemplateGallery && !existingToolId) {
                    setShowingTemplateGallery(true);
                    setSelectedTemplate(null);
                    setAdvancedMode(false);
                    setValidationErrors([]);
                  } else {
                    // Otherwise, go back to parent (AgentLoadouts)
                    if (onBack) {
                      onBack();
                    } else {
                      onClose();
                    }
                  }
                }}
                className="p-2 transition-all text-white/90 hover:text-white hover:bg-white/15 rounded-lg"
                style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
                title="Back"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
              <div className="flex-1">
                <h2 className="text-2xl font-semibold text-white" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.25)' }}>
                  {existingToolId ? 'Edit Custom Tool' : 'Custom Tool Builder'}
                </h2>
                <p className="text-sm mt-1 text-white/90" style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}>
                  {selectedTemplate
                    ? `Using template: ${selectedTemplate.name}`
                    : 'Create a custom tool for your agents to use'
                  }
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="transition-all text-white/90 hover:text-white hover:bg-white/15 p-2 rounded-lg"
              style={{ textShadow: '0 1px 2px rgba(0, 0, 0, 0.15)' }}
            >
              <X className="w-6 h-6" />
            </button>
          </div>
        </div>
      </div>

      {/* Scrollable Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-5xl mx-auto px-6 py-6 space-y-6">
          {/* Show Template Gallery if not selected yet */}
          {showingTemplateGallery ? (
            <ToolTemplateGallery
              onSelectTemplate={handleTemplateSelect}
              onStartFromScratch={handleStartFromScratch}
            />
          ) : (
            <>
              {/* Validation Errors */}
              {validationErrors.length > 0 && (
                <div className="mb-4 p-4 rounded-lg border-2 shadow-lg" style={{
                  backgroundColor: '#fef2f2',
                  borderColor: '#dc2626'
                }}>
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-6 h-6 flex-shrink-0 mt-0.5" style={{ color: '#dc2626' }} />
                    <div className="flex-1">
                      <h4 className="font-bold text-base mb-2" style={{ color: '#991b1b' }}>
                        ⚠️ Cannot Save - Please Fix These Errors:
                      </h4>
                      <ul className="space-y-1.5">
                        {validationErrors.map((error, index) => (
                          <li key={index} className="text-sm font-medium flex items-start gap-2" style={{ color: '#991b1b' }}>
                            <span className="mt-0.5">•</span>
                            <span>{error}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              {/* All Sections */}
              {renderAllSections()}

              {/* Footer */}
              <div className="pt-6 border-t flex items-center justify-end gap-3" style={{ borderTopColor: 'var(--color-border-dark)' }}>
                <button
                  onClick={onClose}
                  className="px-6 py-2 rounded-lg text-sm font-medium transition-colors"
                  style={{
                    backgroundColor: 'transparent',
                    borderWidth: '1px',
                    borderStyle: 'solid',
                    borderColor: 'var(--color-border-dark)',
                    color: 'var(--color-text-primary)'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'var(--color-background-dark)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'transparent';
                  }}
                >
                  Cancel
                </button>

                <button
                  onClick={handleSave}
                  disabled={saving || validationErrors.length > 0}
                  className="flex items-center gap-2 px-6 py-2 rounded-lg text-white text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
                  style={{ backgroundColor: 'var(--color-primary)' }}
                >
                  {saving ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                      Saving...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4" />
                      Save Tool
                    </>
                  )}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      {/* Sliding Information Panel */}
      {showInfoPanel && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-40"
            style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)' }}
            onClick={() => setShowInfoPanel(false)}
          />

          {/* Sliding Panel */}
          <div
            className="fixed top-0 right-0 bottom-0 w-full max-w-3xl border-l z-50 flex flex-col shadow-2xl"
            style={{
              animation: 'slide-in-right 0.3s ease-out',
              backgroundColor: 'var(--color-panel-dark)',
              borderLeftColor: 'var(--color-border-dark)'
            }}
          >
            {/* Panel Header */}
            <div className="p-6 border-b" style={{
              backgroundColor: 'var(--color-primary)',
              borderBottomColor: 'var(--color-border-dark)'
            }}>
              <div className="flex items-center justify-between">
                <h3 className="text-xl font-semibold text-white">
                  Twitter API Rate Limits & Endpoints
                </h3>
                <button
                  onClick={() => setShowInfoPanel(false)}
                  className="p-2 hover:bg-white/10 rounded-lg transition-colors"
                >
                  <X className="w-5 h-5 text-white" />
                </button>
              </div>
              <p className="text-sm text-white/80 mt-2">
                Free tier rate limits for Twitter API v2 endpoints
              </p>
            </div>

            {/* Panel Content */}
            <div className="flex-1 overflow-y-auto p-6" style={{ backgroundColor: 'var(--color-panel-dark)' }}>
              <div className="space-y-6">
                {/* Tweets Section */}
                <div>
                  <h4 className="text-lg font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
                    Tweets
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm border" style={{ borderColor: 'var(--color-border-dark)' }}>
                      <thead style={{ backgroundColor: 'var(--color-background-dark)' }}>
                        <tr>
                          <th className="px-4 py-2 text-left font-semibold" style={{ color: 'var(--color-text-primary)' }}>Endpoint</th>
                          <th className="px-4 py-2 text-left font-semibold" style={{ color: 'var(--color-text-primary)' }}>Free Limit</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>POST /2/tweets</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>17 per 24 hours (per user & app)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>GET /2/tweets/:id</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>1 per 15 mins (per user & app)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>GET /2/tweets/search/recent</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>1 per 15 mins (per user & app)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>GET /2/users/:id/tweets</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>1 per 15 mins (per user & app)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>GET /2/users/:id/mentions</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>1 per 15 mins (per user & app)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>DELETE /2/tweets/:id</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>17 per 24 hours (per user & app)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>POST /2/users/:id/retweets</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>1 per 15 mins (per user)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>POST /2/users/:id/likes</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>200 per 24 hours (per user)</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Users Section */}
                <div>
                  <h4 className="text-lg font-semibold mb-3" style={{ color: 'var(--color-text-primary)' }}>
                    Users
                  </h4>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm border" style={{ borderColor: 'var(--color-border-dark)' }}>
                      <thead style={{ backgroundColor: 'var(--color-background-dark)' }}>
                        <tr>
                          <th className="px-4 py-2 text-left font-semibold" style={{ color: 'var(--color-text-primary)' }}>Endpoint</th>
                          <th className="px-4 py-2 text-left font-semibold" style={{ color: 'var(--color-text-primary)' }}>Free Limit</th>
                        </tr>
                      </thead>
                      <tbody>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>GET /2/users/:id</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>1 per 24 hours (per user & app)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>GET /2/users/by/username/:username</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>3 per 15 mins (per user & app)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>GET /2/users/me</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>25 per 24 hours (per user)</td>
                        </tr>
                        <tr className="border-t" style={{ borderColor: 'var(--color-border-dark)' }}>
                          <td className="px-4 py-2 font-mono text-xs" style={{ color: 'var(--color-text-muted)' }}>POST /2/users/:id/following</td>
                          <td className="px-4 py-2 text-xs" style={{ color: 'var(--color-text-muted)' }}>5 per 15 mins (per user)</td>
                        </tr>
                      </tbody>
                    </table>
                  </div>
                </div>

                {/* Important Notes */}
                <div className="p-4 rounded-lg border" style={{
                  backgroundColor: 'var(--color-background-dark)',
                  borderColor: 'var(--color-border-dark)'
                }}>
                  <h4 className="text-sm font-semibold mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    ⚠️ Important Notes
                  </h4>
                  <ul className="text-xs space-y-1" style={{ color: 'var(--color-text-muted)' }}>
                    <li>• Free tier limits are enforced per user AND per app</li>
                    <li>• Monthly post limit: 1,500 tweets total</li>
                    <li>• Rate limits reset based on the timeframe (15 mins or 24 hours)</li>
                    <li>• Exceeding limits returns 429 (Too Many Requests) error</li>
                    <li>• Consider upgrading to Basic ($100/month) or Pro ($5,000/month) for higher limits</li>
                  </ul>
                </div>

                {/* Documentation Link */}
                <div className="p-4 rounded-lg border" style={{
                  borderColor: 'var(--color-border-dark)',
                  backgroundColor: 'var(--color-background-dark)'
                }}>
                  <p className="text-sm mb-2" style={{ color: 'var(--color-text-primary)' }}>
                    <strong>Full Documentation:</strong>
                  </p>
                  <a
                    href="https://developer.x.com/en/docs/twitter-api/rate-limits"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm underline hover:opacity-80 transition-opacity"
                    style={{ color: 'var(--color-primary)' }}
                  >
                    View complete rate limits table on X Developer Portal →
                  </a>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default CustomToolBuilder;
