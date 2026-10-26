import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useRef, useState } from 'react';
import {
  Activity,
  BookOpenCheck,
  ChevronDown,
  Cpu,
  CreditCard,
  Database,
  ExternalLink,
  IndianRupee,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  Shield,
  Users,
  X,
} from 'lucide-react';
import api from '../../api';
import { LogoLockup, LogoMark } from '../brand/Logo';
import { cn } from '../../lib/cn';

const navGroups = [
  {
    label: 'Overview',
    items: [
      { name: 'Dashboard', path: '/admin/dashboard', icon: LayoutDashboard },
      { name: 'System Status', path: '/admin/system-status', icon: Activity },
    ],
  },
  {
    label: 'Workspace',
    items: [
      { name: 'Knowledge Base', path: '/admin/knowledge-base', icon: Database },
      { name: 'AI Providers', path: '/admin/ai-providers', icon: Cpu },
    ],
  },
  {
    label: 'Monetization',
    items: [
      { name: 'Plans', path: '/admin/plans', icon: CreditCard },
      { name: 'Payments', path: '/admin/payments', icon: IndianRupee },
    ],
  },
  {
    label: 'People',
    items: [{ name: 'Users', path: '/admin/users', icon: Users }],
  },
  {
    label: 'System',
    items: [
      { name: 'Audit Logs', path: '/admin/audit-logs', icon: Shield },
      { name: 'Settings', path: '/admin/settings', icon: Settings },
    ],
  },
];

const flatNav = navGroups.flatMap((group) => group.items);

export default function AdminLayout() {
  const navigate = useNavigate();
  const location = useLocation();
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem('vidhya.sidebar') === 'mini'
  );
  const [mobileOpen, setMobileOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState('');
  const searchRef = useRef<HTMLInputElement>(null);

  const activeItem = flatNav.find((item) => location.pathname.startsWith(item.path));
  const pageTitle = activeItem?.name ?? 'Admin Console';

  useEffect(() => {
    const handleUnauthorized = () => navigate('/admin/login');
    window.addEventListener('auth:unauthorized', handleUnauthorized);

    api
      .get('/analytics/dashboard')
      .then(() => setCheckingAuth(false))
      .catch(() => navigate('/admin/login'));

    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [navigate]);

  useEffect(() => {
    localStorage.setItem('vidhya.sidebar', collapsed ? 'mini' : 'full');
  }, [collapsed]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        searchRef.current?.focus();
      }
      if (event.key === 'Escape') {
        setMenuOpen(false);
        setQuery('');
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // The UI still returns to login if the request fails.
    }
    navigate('/admin/login');
  };

  const results = query
    ? flatNav.filter((item) => item.name.toLowerCase().includes(query.toLowerCase()))
    : [];

  if (checkingAuth) {
    return (
      <div className="flex min-h-screen bg-canvas">
        <aside className="hidden w-[260px] shrink-0 border-r border-line bg-surface p-4 md:block">
          <div className="mb-8 flex items-center gap-3">
            <div className="h-8 w-8 animate-pulse rounded-lg bg-line" />
            <div className="h-4 w-28 animate-pulse rounded bg-line" />
          </div>
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="mb-2 flex items-center gap-3 rounded-lg p-3">
              <div className="h-4 w-4 animate-pulse rounded bg-line" />
              <div className="h-3.5 w-24 animate-pulse rounded bg-line" />
            </div>
          ))}
        </aside>
        <main className="flex-1 p-6">
          <div className="mb-6 h-7 w-48 animate-pulse rounded bg-line" />
          <div className="grid grid-cols-1 gap-5 sm:grid-cols-2 xl:grid-cols-4">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="h-32 animate-pulse rounded-xl bg-surface" />
            ))}
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-canvas">
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-ink/40 backdrop-blur-sm md:hidden"
          onClick={() => setMobileOpen(false)}
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex w-[260px] flex-col border-r border-line bg-surface transition-all duration-200',
          mobileOpen ? 'translate-x-0' : '-translate-x-full',
          'md:translate-x-0',
          collapsed ? 'md:w-[72px]' : 'md:w-[260px]'
        )}
      >
        <div className="flex h-[64px] shrink-0 items-center border-b border-line px-4">
          {collapsed ? (
            <LogoMark size={30} className="mx-auto hidden md:block" />
          ) : (
            <LogoLockup markSize={30} className="hidden md:inline-flex" />
          )}
          <LogoLockup markSize={30} className="md:hidden" />
          <button
            className="ml-auto rounded-lg p-1.5 text-muted hover:bg-canvas hover:text-ink md:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-4 overflow-y-auto px-3 py-4">
          {navGroups.map((group) => (
            <div key={group.label}>
              {!collapsed && (
                <p className="mb-1.5 px-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-muted/70">
                  {group.label}
                </p>
              )}
              <div className="space-y-1">
                {group.items.map((item) => (
                  <NavLink
                    key={item.name}
                    to={item.path}
                    title={collapsed ? item.name : undefined}
                    onClick={() => setMobileOpen(false)}
                    className={({ isActive }) =>
                      cn(
                        'group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all',
                        collapsed && 'md:justify-center md:px-0',
                        isActive
                          ? 'bg-gradient-to-r from-brand-500 to-brand-600 text-white shadow-lg shadow-brand-500/25'
                          : 'text-muted hover:bg-canvas hover:text-ink'
                      )
                    }
                  >
                    {({ isActive }) => (
                      <>
                        <item.icon
                          className={cn(
                            'h-[18px] w-[18px] shrink-0 transition-transform group-hover:scale-105',
                            isActive ? 'text-white' : 'text-muted group-hover:text-brand-500'
                          )}
                        />
                        <span className={cn('truncate', collapsed && 'md:hidden')}>
                          {item.name}
                        </span>
                        {isActive && !collapsed && (
                          <span className="ml-auto h-1.5 w-1.5 rounded-full bg-white/80" />
                        )}
                      </>
                    )}
                  </NavLink>
                ))}
              </div>
            </div>
          ))}
        </nav>

        <div className="border-t border-line p-3">
          {!collapsed && (
            <div className="mb-3 rounded-xl border border-line bg-gradient-to-br from-brand-50 to-surface p-3">
              <div className="flex items-center gap-2 text-xs font-semibold text-brand-700">
                <BookOpenCheck className="h-3.5 w-3.5" /> Vidhya AI v3
              </div>
              <p className="mt-1 text-[11px] leading-relaxed text-muted">
                AI knowledge platform
              </p>
            </div>
          )}
          <button
            onClick={handleLogout}
            title={collapsed ? 'Sign out' : undefined}
            className={cn(
              'flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted transition-colors hover:bg-danger-soft hover:text-danger',
              collapsed && 'md:justify-center md:px-0'
            )}
          >
            <LogOut className="h-[18px] w-[18px] shrink-0" />
            <span className={cn(collapsed && 'md:hidden')}>Sign out</span>
          </button>
        </div>
      </aside>

      <div
        className={cn(
          'min-h-screen transition-[padding] duration-200',
          collapsed ? 'md:pl-[72px]' : 'md:pl-[260px]'
        )}
      >
        <header className="sticky top-0 z-20 flex h-[64px] items-center gap-3 border-b border-line bg-surface/90 px-4 backdrop-blur md:px-6">
          <button
            className="rounded-lg p-1.5 text-muted hover:bg-canvas hover:text-ink md:hidden"
            onClick={() => setMobileOpen(true)}
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" />
          </button>

          <button
            className="hidden rounded-lg p-1.5 text-muted hover:bg-canvas hover:text-ink md:inline-flex"
            onClick={() => setCollapsed((v) => !v)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? (
              <PanelLeftOpen className="h-[18px] w-[18px]" />
            ) : (
              <PanelLeftClose className="h-[18px] w-[18px]" />
            )}
          </button>

          <div className="min-w-0">
            <p className="text-[11px] font-medium text-muted">Admin / {pageTitle}</p>
            <h2 className="truncate text-sm font-semibold text-ink">{pageTitle}</h2>
          </div>

          <div className="relative ml-auto hidden lg:block">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              ref={searchRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search pages…"
              className="input-field h-9 w-56 rounded-lg pl-9 pr-12 text-xs"
            />
            <kbd className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-line bg-canvas px-1.5 py-0.5 text-[10px] text-muted">
              Ctrl K
            </kbd>
            {results.length > 0 && (
              <div className="absolute right-0 top-11 w-full overflow-hidden rounded-xl border border-line bg-surface shadow-xl">
                {results.map((item) => (
                  <button
                    key={item.path}
                    onClick={() => {
                      navigate(item.path);
                      setQuery('');
                    }}
                    className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-ink hover:bg-canvas"
                  >
                    <item.icon className="h-3.5 w-3.5 text-muted" /> {item.name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <span className="hidden items-center gap-1.5 rounded-full border border-green-200 bg-success-soft px-2.5 py-1 text-[11px] font-semibold text-success sm:inline-flex">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-success" /> Live
          </span>

          <div className="relative">
            <button
              onClick={() => setMenuOpen((v) => !v)}
              className="flex items-center gap-2 rounded-lg px-1.5 py-1 hover:bg-canvas"
            >
              <span className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-xs font-semibold text-white shadow-md shadow-brand-500/30">
                A
              </span>
              <span className="hidden text-left md:block">
                <span className="block text-xs font-semibold leading-tight text-ink">Administrator</span>
                <span className="block text-[10px] leading-tight text-muted">Superadmin</span>
              </span>
              <ChevronDown className="hidden h-3.5 w-3.5 text-muted md:block" />
            </button>
            {menuOpen && (
              <>
                <div className="fixed inset-0 z-30" onClick={() => setMenuOpen(false)} />
                <div className="absolute right-0 top-12 z-40 w-48 overflow-hidden rounded-xl border border-line bg-surface p-1 shadow-xl">
                  <a
                    href="/"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted hover:bg-canvas hover:text-ink"
                  >
                    <ExternalLink className="h-3.5 w-3.5" /> View site
                  </a>
                  <button
                    onClick={handleLogout}
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs text-danger hover:bg-danger-soft"
                  >
                    <LogOut className="h-3.5 w-3.5" /> Sign out
                  </button>
                </div>
              </>
            )}
          </div>
        </header>

        <main className="page-shell min-h-[calc(100vh-64px)] p-4 md:p-6">
          <div className="animate-rise">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
