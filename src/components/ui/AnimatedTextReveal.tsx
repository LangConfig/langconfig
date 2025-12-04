/**
 * Copyright (c) 2025 Cade Russell (Ghost Peony)
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

import React, { useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import { animate } from 'animejs';

interface AnimatedTextRevealProps {
  content: string;
  onAnimationComplete?: () => void;
  animationDuration?: number; // Total duration in ms
}

export function AnimatedTextReveal({
  content,
  onAnimationComplete,
  animationDuration = 3000, // 3 seconds default
}: AnimatedTextRevealProps) {
  const [displayedChunks, setDisplayedChunks] = useState<string[]>([]);
  const [isAnimating, setIsAnimating] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const chunkRefs = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    if (!content) return;

    // Split content into chunks (paragraphs, headers, lists, etc.)
    const chunks = content.split(/\n\n+/).filter(chunk => chunk.trim());
    
    // Calculate delay between chunks
    const chunkDelay = Math.min(150, animationDuration / chunks.length);
    
    // Reset for new animation
    setDisplayedChunks([]);
    setIsAnimating(true);
    chunkRefs.current = [];

    // Progressively reveal chunks
    chunks.forEach((chunk, index) => {
      setTimeout(() => {
        setDisplayedChunks(prev => [...prev, chunk]);
        
        // Animate the new chunk when it appears
        setTimeout(() => {
          const element = chunkRefs.current[index];
          if (element) {
            // Initial state: invisible and shifted
            element.style.opacity = '0';
            element.style.transform = 'translateY(20px) scale(0.95)';
            
            // Animate to visible
            animate(element, {
              opacity: [0, 1],
              translateY: [20, 0],
              scale: [0.95, 1],
              duration: 600,
              ease: 'out(3)',
            });

            // Add subtle glow effect for important elements
            const headers = element.querySelectorAll('h1, h2, h3');
            headers.forEach((header, i) => {
              setTimeout(() => {
                animate(header as HTMLElement, {
                  textShadow: [
                    '0 0 0px rgba(99, 102, 241, 0)',
                    '0 0 20px rgba(99, 102, 241, 0.3)',
                    '0 0 0px rgba(99, 102, 241, 0)'
                  ],
                  duration: 1000,
                  ease: 'out(2)',
                });
              }, i * 100);
            });
          }
        }, 10);
      }, index * chunkDelay);
    });

    // Mark animation complete
    const totalDuration = chunks.length * chunkDelay + 1000;
    setTimeout(() => {
      setIsAnimating(false);
      if (onAnimationComplete) {
        onAnimationComplete();
      }
      
      // Final flourish: subtle pulse of the entire content
      if (containerRef.current) {
        animate(containerRef.current, {
          scale: [1, 1.005, 1],
          duration: 800,
          ease: 'out(2)',
        });
      }
    }, totalDuration);
  }, [content, animationDuration, onAnimationComplete]);

  return (
    <div ref={containerRef} className="animated-text-reveal">
      {displayedChunks.map((chunk, index) => (
        <div
          key={index}
          ref={el => { chunkRefs.current[index] = el; }}
          className="chunk-wrapper mb-4"
          style={{
            opacity: 0, // Start invisible
            willChange: 'opacity, transform',
          }}
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkMath]}
            rehypePlugins={[rehypeKatex, rehypeHighlight]}
            components={{
              h1: ({node, ...props}) => (
                <h1 
                  className="text-2xl font-bold mt-6 mb-4 pb-2 border-b" 
                  style={{ 
                    color: 'var(--color-primary)', 
                    borderColor: 'var(--color-border-light)',
                    transition: 'text-shadow 0.3s ease'
                  }} 
                  {...props} 
                />
              ),
              h2: ({node, ...props}) => (
                <h2 
                  className="text-xl font-bold mt-5 mb-3" 
                  style={{ 
                    color: 'var(--color-text-primary)',
                    transition: 'text-shadow 0.3s ease'
                  }} 
                  {...props} 
                />
              ),
              h3: ({node, ...props}) => (
                <h3 
                  className="text-lg font-semibold mt-4 mb-2" 
                  style={{ 
                    color: 'var(--color-text-secondary)',
                    transition: 'text-shadow 0.3s ease'
                  }} 
                  {...props} 
                />
              ),
              p: ({node, ...props}) => (
                <p 
                  className="leading-relaxed mb-4 transition-all duration-300" 
                  style={{ color: 'var(--color-text-primary)' }} 
                  {...props} 
                />
              ),
              ul: ({node, ...props}) => (
                <ul 
                  className="list-disc list-inside mb-4 space-y-1" 
                  style={{ color: 'var(--color-text-primary)' }} 
                  {...props} 
                />
              ),
              ol: ({node, ...props}) => (
                <ol 
                  className="list-decimal list-inside mb-4 space-y-1" 
                  style={{ color: 'var(--color-text-primary)' }} 
                  {...props} 
                />
              ),
              li: ({node, ...props}) => <li className="ml-4" {...props} />,
              code: ({node, inline, ...props}: any) =>
                inline ? (
                  <code 
                    className="px-1.5 py-0.5 rounded text-sm font-mono" 
                    style={{ 
                      backgroundColor: 'var(--color-panel-light)', 
                      color: 'var(--color-primary)' 
                    }} 
                    {...props} 
                  />
                ) : (
                  <code 
                    className="block p-4 rounded-lg overflow-x-auto text-sm font-mono my-4" 
                    style={{ 
                      backgroundColor: '#1e1e1e', 
                      color: '#d4d4d4' 
                    }} 
                    {...props} 
                  />
                ),
              pre: ({node, ...props}) => (
                <pre 
                  className="p-4 rounded-lg overflow-x-auto my-4" 
                  style={{ backgroundColor: '#1e1e1e' }} 
                  {...props} 
                />
              ),
              blockquote: ({node, ...props}) => (
                <blockquote 
                  className="border-l-4 pl-4 italic my-4" 
                  style={{ 
                    borderColor: 'var(--color-primary)', 
                    color: 'var(--color-text-muted)' 
                  }} 
                  {...props} 
                />
              ),
              strong: ({node, ...props}) => (
                <strong 
                  className="font-bold" 
                  style={{ color: 'var(--color-text-primary)' }} 
                  {...props} 
                />
              ),
              em: ({node, ...props}) => (
                <em 
                  className="italic" 
                  style={{ color: 'var(--color-text-primary)' }} 
                  {...props} 
                />
              ),
              a: ({node, ...props}) => (
                <a 
                  className="underline hover:opacity-80" 
                  style={{ color: 'var(--color-primary)' }} 
                  target="_blank" 
                  rel="noopener noreferrer" 
                  {...props} 
                />
              ),
            }}
          >
            {chunk}
          </ReactMarkdown>
        </div>
      ))}
      
      {/* Loading indicator during animation */}
      {isAnimating && (
        <div className="flex items-center gap-2 mt-4">
          <div className="flex gap-1">
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: '0ms' }} />
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: '200ms' }} />
            <div className="w-2 h-2 rounded-full bg-primary animate-pulse" style={{ animationDelay: '400ms' }} />
          </div>
          <span className="text-xs text-gray-500 dark:text-gray-400">Assembling report...</span>
        </div>
      )}
    </div>
  );
}