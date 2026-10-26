import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { BadgeCheck, Check, Copy, FileText, UserRound } from 'lucide-react';
import { LogoMark } from '../brand/Logo';
import { cn } from '../../lib/cn';
import 'katex/dist/katex.min.css';

function CodeBlock({ className, children, ...props }: any) {
  const [copied, setCopied] = useState(false);
  const raw = String(children).replace(/\n$/, '');
  const language = /language-(\w+)/.exec(className || '')?.[1];
  const isBlock = Boolean(language) || String(children).includes('\n');

  if (!isBlock) {
    return (
      <code className="rounded-md border border-line bg-canvas px-1.5 py-0.5 font-mono text-[0.85em] font-medium text-brand-700" {...props}>
        {children}
      </code>
    );
  }

  return (
    <div className="my-3 overflow-hidden rounded-xl border border-slate-800 bg-[#0d1726] shadow-sm">
      <div className="flex items-center justify-between border-b border-white/10 px-3 py-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">{language || 'code'}</span>
        <button
          type="button"
          onClick={async () => {
            await navigator.clipboard.writeText(raw);
            setCopied(true);
            setTimeout(() => setCopied(false), 1600);
          }}
          className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-slate-400 transition-colors hover:bg-white/10 hover:text-white"
        >
          {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto p-3.5 text-xs leading-relaxed text-slate-100">
        <code className={className} {...props}>{children}</code>
      </pre>
    </div>
  );
}

export default function ChatMessage({
  role,
  content,
  sources,
  streaming,
}: {
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: { document_name?: string; page?: number; score?: number }[] | null;
  streaming?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const isUser = role === 'user';

  const copy = async () => {
    await navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className={cn('chat-message group/message flex w-full gap-3 px-4 py-4 md:px-8', isUser && 'justify-end')}>
      {!isUser && (
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm ring-1 ring-line">
          <LogoMark size={19} />
        </span>
      )}

      <div className={cn('min-w-0', isUser ? 'max-w-[86%] sm:max-w-[75%]' : 'flex-1')}>
        {isUser ? (
          <div className="rounded-[18px] rounded-br-md bg-gradient-to-br from-[#203354] to-[#141f35] px-4 py-3 text-sm leading-relaxed text-white shadow-[0_12px_28px_-18px_rgba(16,29,48,0.75)]">
            <p className="whitespace-pre-wrap break-words">{content}</p>
          </div>
        ) : (
          <div className="min-w-0">
            <div className="mb-1.5 flex items-center gap-2">
              <span className="text-[11px] font-semibold text-ink">Vidhya</span>
              <span className="inline-flex items-center gap-1 rounded-full bg-success-soft px-1.5 py-0.5 text-[9px] font-semibold text-success">
                <BadgeCheck className="h-2.5 w-2.5" /> Study assistant
              </span>
            </div>

            <div className="markdown-body text-[15px] leading-[1.72] text-ink">
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{ code: CodeBlock, pre: ({ children }) => <>{children}</> }}
              >
                {content || (streaming ? '…' : '')}
              </ReactMarkdown>
              {streaming && <span className="ml-1 inline-block h-4 w-[3px] animate-pulse rounded-full bg-brand-500 align-middle" />}
            </div>

            {!streaming && content && (
              <div className="mt-2 flex items-center gap-1">
                <button
                  type="button"
                  onClick={copy}
                  className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] font-medium text-muted transition-colors hover:bg-white hover:text-ink"
                >
                  {copied ? <Check className="h-3 w-3 text-success" /> : <Copy className="h-3 w-3" />}
                  {copied ? 'Copied' : 'Copy answer'}
                </button>
              </div>
            )}

            {!!sources?.length && (
              <div className="mt-2.5 rounded-xl border border-line/80 bg-white/60 px-3 py-2.5">
                <p className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.14em] text-muted">
                  <FileText className="h-3 w-3 text-brand-500" /> Sources used
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {sources.map((source, index) => (
                    <span
                      key={`${source.document_name}-${source.page}-${index}`}
                      className="inline-flex items-center gap-1 rounded-lg border border-cyan-100 bg-info-soft px-2 py-1 text-[10px] font-medium text-info"
                    >
                      <FileText className="h-2.5 w-2.5" />
                      {source.document_name}{source.page ? ` · p.${source.page}` : ''}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {isUser && (
        <span className="mt-0.5 hidden h-8 w-8 shrink-0 items-center justify-center rounded-xl border border-line bg-white text-muted shadow-sm sm:flex">
          <UserRound className="h-4 w-4" />
        </span>
      )}
    </div>
  );
}
