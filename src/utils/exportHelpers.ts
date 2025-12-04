/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import jsPDF from 'jspdf';
import html2canvas from 'html2canvas-oklch';
import ReactDOM from 'react-dom/client';
import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeHighlight from 'rehype-highlight';
import rehypeKatex from 'rehype-katex';

/**
 * Export workflow results to PDF with proper formatting and page breaks
 * Uses html2canvas-oklch for modern color support
 */
export async function exportToPDF(
  content: string,
  workflowName: string,
  metadata?: {
    date?: string;
    duration?: number;
    tokens?: number;
    cost?: number;
  }
): Promise<void> {
  try {
    // Create a temporary container for rendering
    const container = document.createElement('div');
    container.style.cssText = `
      position: absolute;
      left: -9999px;
      top: 0;
      width: 170mm;
      background: white;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      color: #000;
      padding: 20px;
      box-sizing: border-box;
    `;
    document.body.appendChild(container);

    // Add title and metadata
    const header = document.createElement('div');
    header.style.cssText = `
      margin-bottom: 20px;
      padding-bottom: 15px;
      border-bottom: 2px solid #e5e7eb;
    `;

    const title = document.createElement('h1');
    title.textContent = workflowName || 'Workflow Results';
    title.style.cssText = `
      font-size: 28px;
      font-weight: bold;
      color: #000;
      margin: 0 0 15px 0;
    `;
    header.appendChild(title);

    if (metadata) {
      const metaDiv = document.createElement('div');
      metaDiv.style.cssText = `
        font-size: 11px;
        color: #666;
        line-height: 1.6;
      `;

      const metaItems = [];
      if (metadata.date) metaItems.push(`Date: ${metadata.date}`);
      if (metadata.duration !== undefined) {
        const duration =
          metadata.duration < 60
            ? `${Math.round(metadata.duration)}s`
            : `${Math.floor(metadata.duration / 60)}m ${Math.round(metadata.duration % 60)}s`;
        metaItems.push(`Duration: ${duration}`);
      }
      if (metadata.tokens !== undefined) metaItems.push(`Tokens: ${metadata.tokens.toLocaleString()}`);
      if (metadata.cost !== undefined) metaItems.push(`Cost: $${metadata.cost.toFixed(4)}`);

      metaDiv.innerHTML = metaItems.join('<br>');
      header.appendChild(metaDiv);
    }

    container.appendChild(header);

    // Create content container for markdown
    const contentDiv = document.createElement('div');
    contentDiv.style.cssText = `
      margin-top: 20px;
    `;
    container.appendChild(contentDiv);

    // Render markdown with proper styling
    const root = ReactDOM.createRoot(contentDiv);
    await new Promise<void>((resolve) => {
      root.render(
        React.createElement(ReactMarkdown, {
          remarkPlugins: [remarkGfm, remarkMath],
          rehypePlugins: [rehypeKatex, rehypeHighlight],
          components: {
            h1: ({ node, ...props }: any) =>
              React.createElement('h1', {
                style: {
                  fontSize: '22px',
                  fontWeight: 'bold',
                  marginTop: '25px',
                  marginBottom: '12px',
                  paddingBottom: '8px',
                  borderBottom: '1px solid #e5e7eb',
                  color: '#000'
                },
                ...props
              }),
            h2: ({ node, ...props }: any) =>
              React.createElement('h2', {
                style: {
                  fontSize: '18px',
                  fontWeight: 'bold',
                  marginTop: '20px',
                  marginBottom: '10px',
                  color: '#000'
                },
                ...props
              }),
            h3: ({ node, ...props }: any) =>
              React.createElement('h3', {
                style: {
                  fontSize: '16px',
                  fontWeight: '600',
                  marginTop: '18px',
                  marginBottom: '8px',
                  color: '#000'
                },
                ...props
              }),
            p: ({ node, ...props }: any) =>
              React.createElement('p', {
                style: {
                  fontSize: '12px',
                  lineHeight: '1.6',
                  marginBottom: '12px',
                  color: '#374151'
                },
                ...props
              }),
            ul: ({ node, ...props }: any) =>
              React.createElement('ul', {
                style: {
                  marginLeft: '20px',
                  marginBottom: '12px',
                  fontSize: '12px',
                  lineHeight: '1.6'
                },
                ...props
              }),
            ol: ({ node, ...props }: any) =>
              React.createElement('ol', {
                style: {
                  marginLeft: '20px',
                  marginBottom: '12px',
                  fontSize: '12px',
                  lineHeight: '1.6'
                },
                ...props
              }),
            li: ({ node, ...props }: any) =>
              React.createElement('li', {
                style: {
                  marginBottom: '6px',
                  color: '#374151'
                },
                ...props
              }),
            code: ({ node, inline, ...props }: any) =>
              inline
                ? React.createElement('code', {
                    style: {
                      backgroundColor: '#f3f4f6',
                      padding: '2px 5px',
                      borderRadius: '3px',
                      fontSize: '11px',
                      fontFamily: 'Consolas, Monaco, monospace',
                      color: '#dc2626'
                    },
                    ...props
                  })
                : React.createElement('code', {
                    style: {
                      display: 'block',
                      backgroundColor: '#1e293b',
                      padding: '12px',
                      borderRadius: '6px',
                      fontSize: '10px',
                      fontFamily: 'Consolas, Monaco, monospace',
                      color: '#e2e8f0',
                      overflowX: 'auto',
                      marginBottom: '12px',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word'
                    },
                    ...props
                  }),
            pre: ({ node, ...props }: any) =>
              React.createElement('pre', {
                style: {
                  margin: '0',
                  padding: '0',
                  background: 'transparent'
                },
                ...props
              }),
            blockquote: ({ node, ...props }: any) =>
              React.createElement('blockquote', {
                style: {
                  borderLeft: '3px solid #135bec',
                  paddingLeft: '15px',
                  marginLeft: '0',
                  marginBottom: '12px',
                  fontStyle: 'italic',
                  color: '#6b7280',
                  fontSize: '12px'
                },
                ...props
              }),
            table: ({ node, ...props }: any) =>
              React.createElement('table', {
                style: {
                  width: '100%',
                  borderCollapse: 'collapse',
                  marginBottom: '12px',
                  fontSize: '11px'
                },
                ...props
              }),
            th: ({ node, ...props }: any) =>
              React.createElement('th', {
                style: {
                  border: '1px solid #e5e7eb',
                  padding: '8px',
                  backgroundColor: '#f9fafb',
                  fontWeight: '600',
                  textAlign: 'left'
                },
                ...props
              }),
            td: ({ node, ...props }: any) =>
              React.createElement('td', {
                style: {
                  border: '1px solid #e5e7eb',
                  padding: '8px'
                },
                ...props
              }),
            img: ({ node, ...props }: any) =>
              React.createElement('img', {
                style: {
                  maxWidth: '100%',
                  maxHeight: '400px',
                  height: 'auto',
                  width: 'auto',
                  marginTop: '12px',
                  marginBottom: '12px',
                  marginLeft: 'auto',
                  marginRight: 'auto',
                  borderRadius: '6px',
                  display: 'block',
                  objectFit: 'contain'
                },
                ...props
              }),
            a: ({ node, ...props }: any) =>
              React.createElement('a', {
                style: {
                  color: '#2563eb',
                  textDecoration: 'underline',
                  wordBreak: 'break-all'
                },
                ...props
              }),
            hr: ({ node, ...props }: any) =>
              React.createElement('hr', {
                style: {
                  border: 'none',
                  borderTop: '1px solid #e5e7eb',
                  margin: '20px 0'
                },
                ...props
              }),
          },
          children: content
        })
      );
      // Wait for rendering to complete (including images)
      setTimeout(resolve, 1000);
    });

    // Convert to canvas using html2canvas-oklch
    const canvas = await html2canvas(container, {
      scale: 2,
      useCORS: true,
      logging: false,
      backgroundColor: '#ffffff'
    });

    // Clean up DOM
    root.unmount();
    document.body.removeChild(container);

    // Create PDF with proper margins
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'mm',
      format: 'a4'
    });

    const pageWidth = pdf.internal.pageSize.getWidth();
    const pageHeight = pdf.internal.pageSize.getHeight();
    const margin = 20; // 20mm margins on all sides
    const contentWidth = pageWidth - (2 * margin);
    const contentHeight = pageHeight - (2 * margin);

    // Calculate image dimensions
    const imgWidth = contentWidth;
    const imgHeight = (canvas.height * contentWidth) / canvas.width;

    // Add content with proper margins and page breaks
    let yOffset = 0;
    let pageNumber = 0;

    while (yOffset < imgHeight) {
      if (pageNumber > 0) {
        pdf.addPage();
      }

      const sourceY = (yOffset * canvas.width) / contentWidth;
      const sourceHeight = Math.min(
        (contentHeight * canvas.width) / contentWidth,
        canvas.height - sourceY
      );

      // Create a temporary canvas for this page
      const pageCanvas = document.createElement('canvas');
      pageCanvas.width = canvas.width;
      pageCanvas.height = sourceHeight;
      const ctx = pageCanvas.getContext('2d');

      if (ctx) {
        ctx.drawImage(
          canvas,
          0,
          sourceY,
          canvas.width,
          sourceHeight,
          0,
          0,
          canvas.width,
          sourceHeight
        );

        const pageImgData = pageCanvas.toDataURL('image/png');
        const pageImgHeight = (sourceHeight * contentWidth) / canvas.width;

        pdf.addImage(
          pageImgData,
          'PNG',
          margin,
          margin,
          contentWidth,
          pageImgHeight
        );
      }

      yOffset += contentHeight;
      pageNumber++;
    }

    // Save the PDF
    const fileName = `${workflowName.replace(/\s+/g, '_')}_${Date.now()}.pdf`;
    pdf.save(fileName);

  } catch (error) {
    console.error('Error exporting PDF:', error);
    throw error;
  }
}

/**
 * Export a DOM element to PDF
 */
export async function exportElementToPDF(
  element: HTMLElement,
  exportFileName: string
): Promise<void> {
  try {
    const textContent = element.textContent || '';
    const baseName = exportFileName.replace(/\.(pdf|doc|txt)$/i, '');
    await exportToPDF(textContent, baseName, {
      date: new Date().toLocaleString()
    });
  } catch (error) {
    console.error('Error exporting element to PDF:', error);
    throw error;
  }
}

/**
 * Export to Word document
 */
export function exportToWord(content: string, workflowName: string): void {
  const blob = new Blob([content], { type: 'application/msword' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${workflowName.replace(/\s+/g, '_')}_${Date.now()}.doc`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

/**
 * Export to plain text
 */
export function exportToText(content: string, workflowName: string): void {
  const blob = new Blob([content], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${workflowName.replace(/\s+/g, '_')}_${Date.now()}.txt`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}
