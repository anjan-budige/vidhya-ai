import { useEffect, useMemo, useRef, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  BookOpenCheck,
  ChevronRight,
  CreditCard,
  Gauge,
  KeyRound,
  LogOut,
  Menu,
  MessageSquare,
  PanelLeft,
  Plus,
  Search,
  Trash2,
  UserRound,
  X,
} from 'lucide-react';
import { animate } from 'animejs';
import { LogoMark } from '../brand/Logo';
import Avatar from '../ui/Avatar';
import { useUser } from '../../contexts/UserContext';
import { fmtLimit, pct } from '../../lib/format';
import { cn } from '../../lib/cn';

const NAV = [
  { path: '/plans', label: 'Plans & billing', icon: CreditCard },
  { path: '/api-keys', label: 'Telegram access', icon: KeyRound },
  { path: '/profile', label: 'Profile', icon: UserRound },
];

function dayLabel(value: string) {
  const date = new Date(value);
  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
  const startYesterday = startToday - 86_400_000;
  if (date.getTime() >= startToday) return 'Today';
  if (date.getTime() >= startYesterday) return 'Yesterday';
  return 'Earlier';
}

export default function UserAppLayout() {
  const {
    conversations,
    conversationsLoading,
    deleteConversation,
    quota,
    fullDisplay,
    setActiveId,
    logout,
  } = useUser();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('vidhya.userSidebar') === 'mini'
  );
  const [desktop, setDesktop] = useState(() => window.matchMedia('(min-width: 768px)').matches);
  const [query, setQuery] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const isChat = location.pathname.startsWith('/chat');
  const compact = collapsed && desktop;

  useEffect(() => {
    localStorage.setItem('vidhya.userSidebar', collapsed ? 'mini' : 'full');
  }, [collapsed]);

  useEffect(() => {
    const media = window.matchMedia('(min-width: 768px)');
    const change = (event: MediaQueryListEvent) => setDesktop(event.matches);
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);

  useEffect(() => {
    const match = location.pathname.match(/^\/chat\/([^/]+)/);
    setActiveId(match?.[1] ?? null);
    setMenuOpen(false);
    mainRef.current?.scrollTo({ top: 0 });
  }, [location.pathname, setActiveId]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        setMenuOpen(true);
        window.setTimeout(() => searchRef.current?.focus(), 50);
      }
      if (event.key === 'Escape') {
        setMenuOpen(false);
        setQuery('');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animate('.user-new-chat', { scale: [0.97, 1], duration: 520, ease: 'outExpo' });
    animate('.user-sidebar-brand', { y: [-8, 0], duration: 500, ease: 'outExpo' });
  }, []);

  const filtered = useMemo(
    () => conversations.filter((conversation) =>
      (conversation.title || 'Untitled chat').toLowerCase().includes(query.toLowerCase())
    ),
    [conversations, query]
  );

  const groups = useMemo(() => {
    const ordered = ['Today', 'Yesterday', 'Earlier'];
    return ordered
      .map((label) => ({
        label,
        items: filtered.filter((conversation) => dayLabel(conversation.last_activity_at) === label),
      }))
      .filter((group) => group.items.length > 0);
  }, [filtered]);

  const newChat = () => {
    setActiveId(null);
    navigate('/chat');
    setMenuOpen(false);
  };

  const remove = async (id: string, title: string) => {
    if (!window.confirm(`Delete "${title}"? This cannot be undone.`)) return;
    if (await deleteConversation(id) && location.pathname === `/chat/${id}`) navigate('/chat');
  };

  const dailyLimit = quota?.daily_messages_limit ?? 0;
  const dailyUsed = quota?.daily_messages_used ?? 0;
  const percent = dailyLimit === -1 ? 100 : pct(dailyUsed, dailyLimit);

  const sidebar = (
    <aside className="user-sidebar relative flex h-full w-full flex-col overflow-hidden">
      <div className="pointer-events-none absolute inset-0 user-noise" />

      <div className={cn('user-sidebar-brand relative flex h-[72px] shrink-0 items-center gap-2.5 border-b border-white/[0.07] px-4', compact && 'md:gap-1.5 md:px-1.5')}>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/[0.07] ring-1 ring-white/10">
          <LogoMark size={23} />
        </span>
        {!compact && (
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold tracking-tight text-white">Vidhya AI</p>
            <p className="text-[10px] font-medium uppercase tracking-[0.16em] text-slate-400">Study workspace</p>
          </div>
        )}
        <button
          className="ml-auto rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/[0.07] hover:text-white md:hidden"
          onClick={() => setMenuOpen(false)}
          aria-label="Close menu"
        ><X className="h-5 w-5" /></button>
        <button
          className={cn('hidden rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-white/[0.07] hover:text-white md:inline-flex', compact && 'md:ml-0')}
          onClick={() => setCollapsed((value) => !value)}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        ><PanelLeft className={cn('h-[18px] w-[18px] transition-transform duration-200', collapsed && 'rotate-180')} /></button>
      </div>

      <div className={cn('relative shrink-0 px-3 pb-3 pt-4', compact && 'md:px-2.5')}>
        <button
          onClick={newChat}
          title={compact ? 'New study chat' : undefined}
          aria-label="New study chat"
          className={cn(
            'user-new-chat group flex w-full items-center gap-2.5 rounded-xl bg-gradient-to-r from-brand-500 to-brand-600 px-3.5 py-3 text-sm font-semibold text-white shadow-[0_10px_26px_-12px_rgba(70,128,255,0.85)] transition-all hover:brightness-110',
            compact && 'md:justify-center md:px-0'
          )}
        >
          <Plus className="h-[18px] w-[18px] shrink-0 transition-transform group-hover:rotate-90" />
          {!compact && <span className="flex-1 text-left">New study chat</span>}
          {!compact && <ChevronRight className="h-4 w-4 opacity-60" />}
        </button>
      </div>

      <div className={cn('relative px-3', compact && 'md:hidden')}>
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-500" />
          <input
            ref={searchRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search your study chats"
            className="h-9 w-full rounded-lg border border-white/[0.08] bg-white/[0.045] pl-8 pr-12 text-xs text-white outline-none placeholder:text-slate-500 focus:border-brand-400/60 focus:bg-white/[0.07]"
          />
          <kbd className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 rounded border border-white/10 px-1 py-0.5 text-[9px] text-slate-500">Ctrl K</kbd>
        </div>
      </div>

      <div className={cn('relative mt-4 flex min-h-0 flex-1 flex-col px-2', compact && 'md:mt-2 md:items-center md:px-2')}>
        <div className="min-h-0 flex-1 overflow-y-auto pr-0.5">
          {conversationsLoading ? (
            <div className="space-y-2 px-1 pt-1">
              {[1, 2, 3, 4, 5].map((item) => <div key={item} className="h-9 animate-pulse rounded-lg bg-white/[0.05]" />)}
            </div>
          ) : groups.length === 0 ? (
            !compact && (
              <div className="mx-1 rounded-xl border border-dashed border-white/10 px-3 py-5 text-center">
                <BookOpenCheck className="mx-auto h-5 w-5 text-slate-500" />
                <p className="mt-2 text-xs text-slate-400">{query ? 'No chats match that search.' : 'Your first conversation starts here.'}</p>
              </div>
            )
          ) : (
            groups.map((group) => (
              <div key={group.label} className="mb-3 last:mb-0">
                {!compact && <p className="mb-1.5 px-2 text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">{group.label}</p>}
                <div className="space-y-0.5">
                  {group.items.map((conversation) => (
                    <div key={conversation.id} className="group relative">
                      <NavLink
                        to={`/chat/${conversation.id}`}
                        title={compact ? conversation.title || 'Untitled chat' : undefined}
                        className={({ isActive }) => cn(
                          'user-session flex min-w-0 items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition-colors',
                          compact && 'md:h-9 md:w-9 md:justify-center md:gap-0 md:rounded-xl md:px-0',
                          isActive && 'user-session-active',
                          compact && isActive && 'md:bg-brand-500/20 md:shadow-none'
                        )}
                      >
                        <MessageSquare className="h-3.5 w-3.5 shrink-0 opacity-70" />
                        {!compact && <span className="truncate pr-5">{conversation.title || 'Untitled chat'}</span>}
                      </NavLink>
                      {!compact && (
                        <button
                          onClick={() => void remove(conversation.id, conversation.title || 'Untitled chat')}
                          className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-md p-1 text-slate-500 opacity-0 transition-all hover:bg-danger/20 hover:text-danger-soft focus:opacity-100 group-hover:opacity-100"
                          aria-label={`Delete ${conversation.title || 'chat'}`}
                        ><Trash2 className="h-3.5 w-3.5" /></button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className={cn('relative mt-2 shrink-0 px-3 pb-2', compact && 'md:border-t md:border-white/[0.07] md:px-2 md:pt-3')}>
        {!compact && <p className="mb-1.5 px-2 text-[9px] font-semibold uppercase tracking-[0.18em] text-slate-500">Workspace</p>}
        <div className="space-y-0.5">
          {NAV.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              title={compact ? item.label : undefined}
              className={({ isActive }) => cn(
                'group relative flex items-center gap-2.5 rounded-lg px-2.5 py-2.5 text-[13px] font-medium transition-colors',
                compact && 'md:justify-center md:px-0',
                isActive ? 'bg-white/[0.07] text-white' : 'text-slate-400 hover:bg-white/[0.05] hover:text-white'
              )}
            >
              {({ isActive }) => (
                <>
                  <item.icon className={cn('h-4 w-4 shrink-0 transition-colors', isActive ? 'text-brand-300' : 'text-slate-500 group-hover:text-slate-300')} />
                  {!compact && <span>{item.label}</span>}
                  {!compact && isActive && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-brand-400" />}
                  {compact && isActive && <span className="absolute -left-2 h-1.5 w-1.5 rounded-full bg-brand-400" />}
                </>
              )}
            </NavLink>
          ))}
        </div>
      </div>

      <div className={cn('relative shrink-0 border-t border-white/[0.07] p-3', compact && 'md:px-2 md:py-3')}>
        {!compact && quota && (
          <div className="mb-2 overflow-hidden rounded-xl border border-white/[0.08] bg-white/[0.045] p-3">
            <div className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-1.5 text-[11px] font-semibold capitalize text-white"><CreditCard className="h-3 w-3 text-brand-300" /> {quota.plan_name}</span>
              <span className="text-[10px] text-slate-400">{dailyLimit === -1 ? 'Unlimited' : `${dailyUsed}/${fmtLimit(dailyLimit)}`}</span>
            </div>
            <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gradient-to-r from-brand-400 to-info transition-[width] duration-500" style={{ width: `${Math.min(percent, 100)}%` }} />
            </div>
            <p className="mt-2 text-[10px] text-slate-500">Messages reset at midnight IST</p>
          </div>
        )}

        {compact && (
          <div className="hidden flex-col items-center gap-2.5 md:flex">
            <NavLink to="/plans" title={`${quota?.plan_name ?? 'Free'} plan · ${dailyUsed}/${fmtLimit(dailyLimit)} today`} className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-white/[0.05] text-brand-300 ring-1 ring-white/10 transition-colors hover:bg-white/[0.09]" aria-label="Plan usage">
              <svg viewBox="0 0 36 36" className="ring-progress absolute inset-0 h-9 w-9">
                <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="2.5" />
                <circle cx="18" cy="18" r="15" fill="none" stroke="#6293FF" strokeWidth="2.5" strokeLinecap="round" strokeDasharray={`${(Math.min(percent, 100) / 100) * 94.2} 94.2`} />
              </svg>
              <Gauge className="h-3.5 w-3.5" />
            </NavLink>
            <Avatar name={fullDisplay || 'Learner'} size="sm" className="ring-2 ring-white/10" />
            <button onClick={() => void logout()} className="rounded-lg p-2 text-slate-500 transition-colors hover:bg-danger/15 hover:text-danger-soft" aria-label="Sign out"><LogOut className="h-4 w-4" /></button>
          </div>
        )}

        <div className={cn('flex items-center gap-2.5', compact && 'md:hidden')}>
          <Avatar name={fullDisplay || 'Learner'} size="sm" />
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">{fullDisplay || 'Learner'}</p>
            <p className="truncate text-[10px] capitalize text-slate-500">{quota?.plan_name || 'Vidhya AI'}</p>
          </div>
          <button onClick={() => void logout()} className="rounded-lg p-1.5 text-slate-500 transition-colors hover:bg-danger/15 hover:text-danger-soft" aria-label="Sign out"><LogOut className="h-4 w-4" /></button>
        </div>
      </div>
    </aside>
  );

  return (
    <div className="user-canvas flex h-dvh overflow-hidden">
      {menuOpen && <div className="fixed inset-0 z-40 bg-ink/45 backdrop-blur-sm md:hidden" onClick={() => setMenuOpen(false)} aria-hidden="true" />}
      <div className={cn(
        'fixed inset-y-0 left-0 z-50 shrink-0 transition-[transform,width] duration-200 md:static md:z-auto',
        menuOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0',
        collapsed ? 'w-[292px] md:w-[84px]' : 'w-[292px]'
      )}>
        {sidebar}
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-[60px] shrink-0 items-center gap-3 border-b border-line bg-white/85 px-4 backdrop-blur-xl md:hidden">
          <button onClick={() => setMenuOpen(true)} className="rounded-lg p-1.5 text-muted hover:bg-canvas" aria-label="Open chats"><Menu className="h-5 w-5" /></button>
          <div className="flex items-center gap-2">
            <LogoMark size={22} />
            <span className="user-display text-sm font-semibold text-ink">Vidhya AI</span>
          </div>
          <NavLink to="/plans" className="ml-auto rounded-full border border-line bg-surface px-2.5 py-1 text-[10px] font-semibold capitalize text-muted">
            {quota?.plan_name || 'Free'}
          </NavLink>
        </header>
        <main ref={mainRef} className={cn('min-h-0 flex-1', isChat ? 'flex flex-col overflow-hidden' : 'overflow-y-auto')}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
