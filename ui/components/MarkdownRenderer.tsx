'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Check, Copy } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
}

export default function MarkdownRenderer({ content }: MarkdownRendererProps) {
  // ensure newlines are preserved if they are coming in as escaped literals
  const processedContent = typeof content === 'string' ? content.replace(/\\n/g, '\n') : '';

  return (
    <div className="markdown-content text-sm leading-6 text-gray-200" style={{ border: '1px dashed #444', padding: '10px', borderRadius: '8px' }}>
      <div className="text-xs text-gray-500 mb-2 font-mono flex items-center justify-between">
        <span>[Markdown Mode]</span>
      </div>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            const value = String(children).replace(/\n$/, '');

            if (!inline && match) {
              return (
                <div className="relative group my-4 rounded-lg overflow-hidden border border-gray-700">
                  <div className="absolute top-2 right-2 z-10 opacity-0 group-hover:opacity-100 transition-opacity">
                    <CopyButton value={value} />
                  </div>
                  <SyntaxHighlighter
                    style={oneDark}
                    language={match[1]}
                    PreTag="div"
                    customStyle={{
                      margin: 0,
                      padding: '1.5rem',
                      backgroundColor: '#1a1b26',
                    }}
                    {...props}
                  >
                    {value}
                  </SyntaxHighlighter>
                </div>
              );
            }

            return (
              <code className="bg-gray-800 text-pink-400 px-1.5 py-0.5 rounded font-mono text-sm" {...props}>
                {children}
              </code>
            );
          },
          h1: ({ children }) => <h1 className="text-2xl font-bold mt-6 mb-4 border-b border-gray-700 pb-2">{children}</h1>,
          h2: ({ children }) => <h2 className="text-xl font-bold mt-5 mb-3">{children}</h2>,
          h3: ({ children }) => <h3 className="text-lg font-bold mt-4 mb-2">{children}</h3>,
          p: ({ children }) => <p className="mb-4 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-6 mb-4 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-6 mb-4 space-y-1">{children}</ol>,
          li: ({ children }) => <li>{children}</li>,
          blockquote: ({ children }) => <blockquote className="border-l-4 border-blue-500 pl-4 py-1 my-4 bg-gray-800/30 italic">{children}</blockquote>,
          a: ({ children, href }) => <a href={href} className="text-blue-400 hover:underline" target="_blank" rel="noreferrer">{children}</a>,
        }}
      >
        {processedContent}
      </ReactMarkdown>
    </div>
  );
}

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = React.useState(false);

  const onCopy = () => {
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={onCopy}
      className="p-1.5 bg-gray-700 hover:bg-gray-600 rounded-md transition-colors"
      title="Copy code"
    >
      {copied ? <Check size={14} className="text-green-400" /> : <Copy size={14} className="text-gray-300" />}
    </button>
  );
}
