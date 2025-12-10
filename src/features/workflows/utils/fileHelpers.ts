/**
 * File helper utilities for workflow file management
 */

// File type icons (emoji-based)
export const getFileIcon = (extension: string): string => {
  const ext = extension.toLowerCase().replace('.', '');
  const icons: Record<string, string> = {
    md: '📝',
    txt: '📄',
    json: '📊',
    csv: '📊',
    py: '🐍',
    js: '💛',
    ts: '💙',
    tsx: '💙',
    jsx: '💛',
    html: '🌐',
    css: '🎨',
    sql: '🗃️',
    yaml: '⚙️',
    yml: '⚙️',
    xml: '📋',
    log: '📜',
    pdf: '📕',
    png: '🖼️',
    jpg: '🖼️',
    jpeg: '🖼️',
    gif: '🖼️',
    svg: '🎨',
  };
  return icons[ext] || '📄';
};

// Get language for syntax highlighting (Prism)
export const getLanguage = (extension: string): string => {
  const ext = extension.toLowerCase().replace('.', '');
  const languages: Record<string, string> = {
    py: 'python',
    js: 'javascript',
    ts: 'typescript',
    tsx: 'tsx',
    jsx: 'jsx',
    json: 'json',
    html: 'html',
    css: 'css',
    sql: 'sql',
    yaml: 'yaml',
    yml: 'yaml',
    xml: 'xml',
    sh: 'bash',
    bash: 'bash',
    md: 'markdown',
  };
  return languages[ext] || 'text';
};

// Check if file extension supports syntax highlighting
export const isCodeFile = (extension: string): boolean => {
  const ext = extension.toLowerCase().replace('.', '');
  const codeExtensions = ['json', 'py', 'js', 'ts', 'tsx', 'jsx', 'html', 'css', 'sql', 'yaml', 'yml', 'xml', 'sh', 'bash'];
  return codeExtensions.includes(ext);
};

// Check if file is markdown
export const isMarkdownFile = (extension: string): boolean => {
  const ext = extension.toLowerCase().replace('.', '');
  return ext === 'md';
};
