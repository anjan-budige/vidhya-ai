import { useEffect, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  ArrowUp,
  BookOpenText,
  Check,
  FileCheck2,
  FileSearch,
  ListChecks,
  Pencil,
  Plus,
  Radio,
  ShieldCheck,
  Square,
  Target,
} from 'lucide-react';
import { animate, stagger } from 'animejs';
import toast from 'react-hot-toast';
import api from '../../api';
import { useUser } from '../../contexts/UserContext';
import ChatMessage from '../../components/user/ChatMessage';
import { LogoMark } from '../../components/brand/Logo';
import { cn } from '../../lib/cn';

function cookie(name: string) {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${name}=([^;]+)`));
  return match ? decodeURIComponent(match[1]) : '';
}

async function csrfToken() {
  const existing = cookie('csrf_token');
  if (existing) return existing;
  await fetch('/api/v1/auth/csrf', { credentials: 'include' });
  return cookie('csrf_token');
}

async function streamChat(id: string, text: string, signal: AbortSignal, onToken: (full: string) => void) {
  const token = await csrfToken();
  const response = await fetch('/api/v1/ai/chat/stream', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
    body: JSON.stringify({ message: text, conversation_id: id }),
    signal,
  });

  if (!response.ok) {
    const data = await response.json().catch(() => ({ detail: 'Request failed.' }));
    throw new Error(data.detail || 'Request failed.');
  }
  if (!response.body) throw new Error('The provider did not stream a response.');

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let event = '';
  let full = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const raw of lines) {
      const line = raw.trim();
      if (!line) continue;
      if (line.startsWith('event:')) {
        event = line.slice(6).trim();
        continue;
      }
      if (!line.startsWith('data:')) continue;
      const data = JSON.parse(line.slice(5));
      if (event === 'token') {
        full += data.token || '';
        onToken(full);
      } else if (event === 'error') {
        throw new Error(data.detail || 'The assistant could not complete that answer.');
      } else if (event === 'done') {
        return full;
      }
    }
  }
  return full;
}

const prompts = [
  {
    icon: BookOpenText,
    title: 'Understand a concept',
    text: 'Explain a difficult topic from my study material in simple terms.',
    prompt: 'Explain a difficult concept from my study material in simple terms, with an example.',
    tint: 'sky',
  },
  {
    icon: FileSearch,
    title: 'Find it in my documents',
    text: 'Locate the exact section and page I should revise.',
    prompt: 'Search my documents and tell me where a key topic is explained.',
    tint: 'cyan',
  },
  {
    icon: ListChecks,
    title: 'Build a revision plan',
    text: 'Turn my syllabus into a focused plan for the week.',
    prompt: 'Create a focused revision plan for this week from my syllabus.',
    tint: 'violet',
  },
  {
    icon: Target,
    title: 'Practice with answers',
    text: 'Generate questions and check my understanding.',
    prompt: 'Give me practice questions with answers from my current material.',
    tint: 'emerald',
  },
];

const tintStyles: Record<string, string> = {
  sky: 'bg-brand-50 text-brand-600 ring-brand-100',
  cyan: 'bg-info-soft text-info ring-cyan-100',
  violet: 'bg-violet-50 text-violet-600 ring-violet-100',
  emerald: 'bg-success-soft text-success ring-green-100',
};

export default function ChatApp() {
  const { conversationId } = useParams();
  const navigate = useNavigate();
  const { createConversation, loadConversations, quota, refreshQuota, user, setActiveId } = useUser();

  const [conv, setConv] = useState<any>(null);
  const [messages, setMessages] = useState<any[]>([]);
  const [draft, setDraft] = useState('');
  const [loading, setLoading] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const [streamText, setStreamText] = useState('');
  const [error, setError] = useState('');
  const [renaming, setRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const skipNextLoad = useRef<string | null>(null);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animate('.chat-hero-item', {
      y: [16, 0],
      duration: 620,
      delay: stagger(75),
      ease: 'outExpo',
    });
    animate('.chat-prompt', {
      y: [12, 0],
      duration: 520,
      delay: stagger(58, { start: 240 }),
      ease: 'outExpo',
    });
  }, []);

  useEffect(() => {
    if (skipNextLoad.current === conversationId) {
      skipNextLoad.current = null;
      return;
    }
    if (!conversationId) {
      setConv(null);
      setMessages([]);
      if (scrollRef.current) scrollRef.current.scrollTop = 0;
      return;
    }

    abortRef.current?.abort();
    setStreaming(false);
    setStreamText('');
    setError('');

    const load = async () => {
      setLoading(true);
      try {
        const [conversation, msgs] = await Promise.all([
          api.get(`/conversations/${conversationId}`),
          api.get(`/conversations/${conversationId}/messages`, { params: { page_size: 200 } }),
        ]);
        setConv(conversation.data);
        setMessages(msgs.data);
      } catch (err: any) {
        setError(err.response?.data?.detail || 'Could not open this chat.');
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [conversationId]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages.length, streamText]);

  const sendMessage = async (override?: string) => {
    const text = (override ?? draft).trim();
    if (!text || streaming) return;

    setError('');
    setStreaming(true);
    setStreamText('');
    setMessages((prev) => [...prev, { id: `local-user-${Date.now()}`, role: 'user', content: text }]);
    setDraft('');

    const controller = new AbortController();
    abortRef.current = controller;
    let targetId = conversationId;

    try {
      if (!targetId) {
        const created = await createConversation(text.slice(0, 60));
        if (!created) throw new Error('Could not create a chat.');
        targetId = created.id;
        skipNextLoad.current = targetId;
        setConv(created);
        navigate(`/chat/${targetId}`, { replace: true });
      }

      await streamChat(targetId, text, controller.signal, setStreamText);
      const saved = await api.get(`/conversations/${targetId}/messages`, { params: { page_size: 200 } });
      setMessages(saved.data);
      setStreamText('');
      await Promise.all([loadConversations(), refreshQuota()]);
    } catch (err: any) {
      if (err.name !== 'AbortError') {
        setError(err.message || 'The assistant could not answer. Please try again.');
      }
    } finally {
      setStreaming(false);
    }
  };

  const stop = () => {
    abortRef.current?.abort();
    setStreaming(false);
    toast('Generation stopped.');
  };

  const rename = async () => {
    if (!conv || !renameValue.trim()) return;
    try {
      await api.patch(`/conversations/${conv.id}`, { title: renameValue.trim() });
      setConv({ ...conv, title: renameValue.trim() });
      setRenaming(false);
      await loadConversations();
      toast.success('Chat renamed.');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not rename chat.');
    }
  };

  return (
    <div className="chat-canvas flex h-full min-h-0 flex-col">
      {conversationId && (
        <header className="flex h-[64px] shrink-0 items-center gap-3 border-b border-line/90 bg-white/75 px-4 backdrop-blur-xl md:px-7">
          <span className="hidden h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600 ring-1 ring-brand-100 sm:flex">
            <BookOpenText className="h-4 w-4" />
          </span>
          <div className="min-w-0 flex-1">
            {renaming ? (
              <div className="flex max-w-lg items-center gap-2">
                <input
                  autoFocus
                  value={renameValue}
                  onChange={(event) => setRenameValue(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter') rename();
                    if (event.key === 'Escape') setRenaming(false);
                  }}
                  className="input-field h-8 text-sm"
                  aria-label="Chat title"
                />
                <button onClick={rename} className="rounded-lg p-1.5 text-success hover:bg-success-soft" aria-label="Save title"><Check className="h-4 w-4" /></button>
              </div>
            ) : (
              <>
                <h1 className="truncate text-sm font-semibold tracking-tight text-ink">{conv?.title || 'Untitled chat'}</h1>
                <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted">
                  <span>{messages.length} messages</span>
                  <span className="h-0.5 w-0.5 rounded-full bg-muted" />
                  <span className="inline-flex items-center gap-1"><ShieldCheck className="h-2.5 w-2.5 text-success" /> Grounded</span>
                </div>
              </>
            )}
          </div>
          {!renaming && (
            <button
              onClick={() => { setRenameValue(conv?.title || ''); setRenaming(true); }}
              className="rounded-lg p-2 text-muted transition-colors hover:bg-canvas hover:text-ink"
              aria-label="Rename chat"
            ><Pencil className="h-4 w-4" /></button>
          )}
          <button
            onClick={() => { setActiveId(null); navigate('/chat'); }}
            className="hidden items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-brand-200 hover:text-ink sm:inline-flex"
          ><Plus className="h-3.5 w-3.5" /> New chat</button>
        </header>
      )}

      {error && (
        <div className="mx-4 mt-3 flex items-center justify-between gap-3 rounded-xl border border-red-200 bg-danger-soft px-3.5 py-2.5 text-xs text-danger md:mx-7">
          <span>{error}</span>
          <button onClick={() => setError('')} className="font-semibold underline underline-offset-2">Dismiss</button>
        </div>
      )}

      <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto">
        {!conversationId ? (
          <div className="relative flex min-h-full items-center justify-center overflow-hidden px-4 py-10 md:px-8">
            <div className="pointer-events-none absolute inset-0 user-grid-lines" />
            <div className="user-aurora pointer-events-none absolute -top-32 left-1/2 h-72 w-[38rem] -translate-x-1/2 rounded-full bg-brand-200/30 blur-3xl" />
            <div className="pointer-events-none absolute bottom-0 right-0 h-52 w-52 rounded-full bg-info/10 blur-3xl" />

            <div className="relative w-full max-w-[860px] text-center">
              <div className="chat-hero-item mx-auto inline-flex items-center gap-2 rounded-full border border-brand-100 bg-white/80 px-3.5 py-1.5 text-[11px] font-semibold text-brand-700 shadow-sm backdrop-blur">
                <BookOpenText className="h-3.5 w-3.5" /> Your document-grounded study copilot
              </div>

              <h1 className="chat-hero-item user-display mx-auto mt-6 max-w-2xl text-[34px] font-semibold leading-[1.08] text-ink md:text-[48px]">
                {user?.first_name ? `Welcome back, ${user.first_name}.` : 'What should we learn?'}
                <span className="block text-brand-500">Let’s make it click.</span>
              </h1>

              <p className="chat-hero-item mx-auto mt-4 max-w-lg text-sm leading-relaxed text-muted md:text-[15px]">
                Ask from your institution’s own notes, manuals and study material. Every answer can point you back to the exact source.
              </p>

              <div className="mt-8 grid w-full gap-3 text-left sm:grid-cols-2">
                {prompts.map((item) => (
                  <button
                    key={item.title}
                    onClick={() => sendMessage(item.prompt)}
                    className="chat-prompt user-prompt group p-4"
                  >
                    <span className={cn('flex h-9 w-9 items-center justify-center rounded-xl ring-1', tintStyles[item.tint])}>
                      <item.icon className="h-[18px] w-[18px]" />
                    </span>
                    <span className="mt-3 block text-sm font-semibold text-ink">{item.title}</span>
                    <span className="mt-1 block pr-5 text-xs leading-relaxed text-muted">{item.text}</span>
                    <ArrowUp className="absolute bottom-4 right-4 h-3.5 w-3.5 rotate-45 text-slate-300 transition-all group-hover:rotate-0 group-hover:text-brand-500" />
                  </button>
                ))}
              </div>

              <div className="chat-hero-item mt-6 flex flex-wrap items-center justify-center gap-x-5 gap-y-2 text-[10px] font-medium text-muted">
                <span className="inline-flex items-center gap-1.5"><ShieldCheck className="h-3.5 w-3.5 text-success" /> Private to your workspace</span>
                <span className="inline-flex items-center gap-1.5"><FileCheck2 className="h-3.5 w-3.5 text-brand-500" /> Sources attached to answers</span>
                <span className="inline-flex items-center gap-1.5"><Radio className="h-3.5 w-3.5 text-info" /> Live streaming responses</span>
              </div>
            </div>
          </div>
        ) : loading ? (
          <div className="mx-auto max-w-4xl space-y-5 px-4 py-8 md:px-8">
            {[1, 2, 3].map((item) => (
              <div key={item} className={cn('flex gap-3', item % 2 === 0 && 'justify-end')}>
                <div className={cn('h-20 animate-pulse rounded-2xl bg-white/70 shadow-sm', item % 2 === 0 ? 'w-1/2' : 'w-2/3')} />
              </div>
            ))}
          </div>
        ) : (
          <div className="mx-auto max-w-[880px] pb-6 pt-2">
            {messages.map((message) => (
              <ChatMessage key={message.id} role={message.role} content={message.content} sources={message.sources} />
            ))}
            {streaming && !streamText && (
              <div className="flex items-center gap-3 px-4 py-5 md:px-8">
                <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-50 ring-1 ring-brand-100"><LogoMark size={18} /></span>
                <div className="flex items-center gap-2 rounded-2xl border border-line bg-white px-4 py-3 shadow-sm">
                  <span className="user-typing flex items-center gap-1">
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                    <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                  </span>
                  <span className="text-[11px] font-medium text-muted">Reading your material…</span>
                </div>
              </div>
            )}
            {streamText && <ChatMessage role="assistant" content={streamText} streaming />}
          </div>
        )}
      </div>

      <div className="shrink-0 bg-gradient-to-t from-[#F6F8FC] via-[#F6F8FC]/95 to-transparent px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-5 md:px-8">
        <form
          onSubmit={(event) => { event.preventDefault(); sendMessage(); }}
          className="mx-auto max-w-[880px]"
        >
          {quota && !quota.can_send && (
            <div className="mb-2 flex items-center justify-between gap-3 rounded-xl border border-amber-200 bg-warning-soft px-3 py-2 text-[11px] text-warning">
              <span>You have reached today’s message limit on {quota.plan_name}.</span>
              <button type="button" onClick={() => navigate('/plans')} className="shrink-0 font-semibold underline">View plans</button>
            </div>
          )}
          <div className="user-composer overflow-hidden p-2">
            <textarea
              id="composer"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault();
                  sendMessage();
                }
              }}
              rows={2}
              placeholder={streaming ? 'Vidhya is writing…' : 'Ask anything from your study material…'}
              className="max-h-40 min-h-[52px] w-full resize-none bg-transparent px-3 pb-1 pt-2.5 text-sm leading-relaxed text-ink outline-none placeholder:text-slate-400"
            />
            <div className="flex items-center gap-2 px-1.5 pb-0.5 pt-1">
              <span className="hidden text-[10px] text-slate-400 sm:block">Shift + Enter for a new line</span>
              {streaming ? (
                <button
                  type="button"
                  onClick={stop}
                  className="ml-auto inline-flex h-9 items-center justify-center gap-1.5 rounded-xl border border-line bg-surface px-3 text-xs font-semibold text-muted transition-colors hover:border-red-200 hover:bg-danger-soft hover:text-danger"
                >
                  <Square className="h-3 w-3 fill-current" /> <span className="hidden sm:inline">Stop</span>
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!draft.trim()}
                  aria-label="Send message"
                  className={cn(
                    'ml-auto flex h-9 w-9 items-center justify-center rounded-xl text-white transition-all',
                    draft.trim()
                      ? 'bg-gradient-to-br from-brand-500 to-brand-700 shadow-lg shadow-brand-500/25 hover:-translate-y-0.5 hover:shadow-brand-500/35'
                      : 'cursor-not-allowed bg-slate-300'
                  )}
                >
                  <ArrowUp className="h-[18px] w-[18px]" />
                </button>
              )}
            </div>
          </div>
          <p className="mt-2 text-center text-[10px] leading-relaxed text-slate-400">
            Vidhya can make mistakes. Check important information against your source documents.
          </p>
        </form>
      </div>
    </div>
  );
}
