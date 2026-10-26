import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  Check,
  CircleOff,
  Clock,
  Copy,
  CreditCard,
  ExternalLink,
  FlaskConical,
  ReceiptText,
  Search,
  ShieldCheck,
  Trash2,
  Wallet,
  X,
  Zap,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import FreeModeBanner from '../../components/admin/FreeModeBanner';
import { usePlatformConfig } from '../../hooks/usePlatformConfig';
import { cn } from '../../lib/cn';

interface CredentialField {
  key: string;
  label: string;
  hint: string;
  secret: boolean;
  placeholder: string;
  default: string;
  required: boolean;
}

interface Meta {
  driver: string;
  name: string;
  tagline: string;
  brand_slug: string;
  brand_color: string;
  docs_url: string;
  capabilities: string[];
  webhook_events: string[];
  webhook_notes: string;
  modes: string[];
  fields: CredentialField[];
}

interface ProviderRow {
  id: string;
  driver: string;
  mode: string;
  display_name: string;
  is_active: boolean;
  configured: boolean;
  credential_preview: Record<string, string>;
  webhook_url: string;
  last_tested_at: string | null;
  last_test_status: string | null;
  last_test_error: string | null;
}

interface Overview {
  environment: string;
  demo_allowed: boolean;
  modes: string[];
  catalog: Meta[];
  providers: ProviderRow[];
}

interface Transaction {
  id: string;
  merchant_txn_id: string;
  order_ref: string;
  provider_transaction_id: string | null;
  amount_inr: number;
  status: string;
  order_status: string;
  plan_name: string | null;
  provider: string | null;
  mode: string | null;
  is_test: boolean;
  user_email: string | null;
  user_name: string | null;
  created_at: string;
}

const BRAND_ASSETS: Record<string, string> = {
  razorpay: '/brands/razorpay.svg',
  cashfree: '/brands/cashfree.svg',
  paytm: '/brands/paytm.svg',
  phonepe: '/brands/phonepe.svg',
  payu: '/brands/payu.svg',
};

const WIDE_BRANDS = new Set(['cashfree', 'payu']);

const MODE_META: Record<string, { label: string; note: string }> = {
  demo: { label: 'Demo', note: 'Simulated checkout. No credentials, no real money.' },
  sandbox: { label: 'Sandbox', note: 'Provider test keys. No real money.' },
  production: { label: 'Production', note: 'Live keys. Real money moves.' },
};

function BrandLogo({ slug, color, name }: { slug: string; color: string; name: string }) {
  const [failed, setFailed] = useState(false);
  const asset = BRAND_ASSETS[slug];
  if (!asset || failed) {
    return (
      <div
        className="flex h-10 w-10 items-center justify-center rounded-xl text-sm font-bold text-white"
        style={{ background: color }}
      >
        {name.charAt(0)}
      </div>
    );
  }
  return (
    <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-line bg-white p-2">
      <img
        src={asset}
        alt={name}
        className={WIDE_BRANDS.has(slug) ? 'h-4 w-8 object-contain' : 'h-6 w-6 object-contain'}
        onError={() => setFailed(true)}
      />
    </div>
  );
}

function ModeBadge({ mode }: { mode: string }) {
  const label = MODE_META[mode]?.label ?? mode;
  return (
    <Badge tone={mode === 'production' ? 'danger' : mode === 'sandbox' ? 'info' : 'brand'}>
      {label}
    </Badge>
  );
}

export default function AdminPayments() {
  const { freeMode } = usePlatformConfig();
  const [tab, setTab] = useState<'providers' | 'transactions'>('providers');
  const [overview, setOverview] = useState<Overview | null>(null);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');

  const [wizard, setWizard] = useState<{ meta: Meta; mode: string; provider: ProviderRow | null } | null>(null);
  const [creds, setCreds] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = async () => {
    try {
      const [o, t] = await Promise.all([
        api.get('/admin/payments/overview'),
        api.get('/payments/all').catch(() => ({ data: [] })),
      ]);
      setOverview(o.data);
      setTransactions(t.data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not load payments.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const providersBy = (driver: string, mode: string) =>
    overview?.providers.find((p) => p.driver === driver && p.mode === mode) ?? null;

  const activeFor = (mode: string) =>
    overview?.providers.find((p) => p.mode === mode && p.is_active) ?? null;

  const openWizard = (meta: Meta, mode: string) => {
    const provider = providersBy(meta.driver, mode);
    const initial: Record<string, string> = {};
    if (!provider) {
      meta.fields.forEach((f) => {
        if (!f.secret) {
          const fallback =
            meta.driver === 'paytm' && f.key === 'website' && mode === 'production'
              ? 'DEFAULT'
              : f.default;
          initial[f.key] = fallback ?? '';
        }
      });
    }
    setCreds(initial);
    setWizard({ meta, mode, provider });
  };

  const saveProvider = async () => {
    if (!wizard) return;
    setSaving(true);
    try {
      const credentials = Object.fromEntries(
        Object.entries(creds).filter(([, v]) => v.trim() !== '')
      );
      let res;
      if (wizard.provider) {
        if (Object.keys(credentials).length === 0) {
          toast.success('No changes to save.');
          setSaving(false);
          return;
        }
        res = await api.put(`/admin/payments/providers/${wizard.provider.id}`, {
          credentials,
        });
      } else {
        res = await api.post('/admin/payments/providers', {
          driver: wizard.meta.driver,
          mode: wizard.mode,
          display_name: wizard.meta.name,
          credentials,
        });
      }
      toast.success('Payment provider saved.');
      const saved: ProviderRow = res.data;
      setWizard({ ...wizard, provider: saved });
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not save the provider.');
    } finally {
      setSaving(false);
    }
  };

  const testProvider = async (provider: ProviderRow) => {
    setTesting(true);
    try {
      const res = await api.post(`/admin/payments/providers/${provider.id}/test`);
      toast.success(res.data.message || 'Connection test passed.');
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Connection test failed.');
      await load();
    } finally {
      setTesting(false);
    }
  };

  const activateProvider = async (provider: ProviderRow, expirePending = false) => {
    setBusyId(provider.id);
    try {
      const res = await api.post(`/admin/payments/providers/${provider.id}/activate`, {
        expire_pending: expirePending,
      });
      setWizard((current) =>
        current?.provider?.id === provider.id
          ? { ...current, provider: res.data }
          : current
      );
      toast.success(`${provider.display_name} is now active for ${provider.mode}.`);
      await load();
    } catch (err: any) {
      const detail = err.response?.data?.detail || 'Could not activate the provider.';
      if (err.response?.status === 409 && !expirePending && window.confirm(`${detail}\n\nExpire those pending orders and continue?`)) {
        await activateProvider(provider, true);
      } else {
        toast.error(detail);
      }
    } finally {
      setBusyId(null);
    }
  };

  const deactivateProvider = async (provider: ProviderRow) => {
    if (!window.confirm(
      `Deactivate ${provider.display_name} for ${MODE_META[provider.mode]?.label ?? provider.mode}?\n\n` +
      'New checkouts in this mode will stop until another provider is activated.'
    )) return;
    setBusyId(provider.id);
    try {
      const res = await api.post(`/admin/payments/providers/${provider.id}/deactivate`);
      setWizard((current) =>
        current?.provider?.id === provider.id
          ? { ...current, provider: res.data }
          : current
      );
      toast.success(`${provider.display_name} deactivated for ${provider.mode}.`);
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not deactivate the provider.');
    } finally {
      setBusyId(null);
    }
  };

  const deleteProvider = async (provider: ProviderRow) => {
    if (!window.confirm(`Delete ${provider.display_name} (${provider.mode})?`)) return;
    try {
      await api.delete(`/admin/payments/providers/${provider.id}`);
      toast.success('Provider deleted.');
      setWizard(null);
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not delete the provider.');
    }
  };

  const setEnvironment = async (mode: string) => {
    try {
      await api.put('/admin/payments/environment', { environment: mode });
      toast.success(`Checkout now uses ${MODE_META[mode]?.label ?? mode}.`);
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not change the environment.');
    }
  };

  const copy = async (value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success('Copied.');
    } catch {
      toast.error('Copy failed.');
    }
  };

  const filteredTransactions = useMemo(
    () =>
      transactions.filter(
        (p) =>
          p.user_email?.toLowerCase().includes(searchTerm.toLowerCase()) ||
          p.merchant_txn_id?.toLowerCase().includes(searchTerm.toLowerCase())
      ),
    [transactions, searchTerm]
  );

  const transactionStats = useMemo(() => {
    const paid = transactions.filter((payment) => payment.status === 'success');
    const pending = transactions.filter((payment) => payment.status === 'pending');
    const failed = transactions.filter((payment) => payment.status === 'failed');
    return {
      collected: paid.reduce((sum, payment) => sum + payment.amount_inr / 100, 0),
      paid: paid.length,
      pending: pending.length,
      failed: failed.length,
    };
  }, [transactions]);

  if (loading) {
    return (
      <div className="flex h-72 items-center justify-center">
        <div className="h-10 w-10 animate-spin rounded-full border-4 border-brand-100 border-t-brand-500" />
      </div>
    );
  }

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink">Payments</h1>
          <p className="mt-1 text-sm text-muted">
            Configure providers by environment. One provider can be active per mode, or none.
          </p>
        </div>
        <div className="inline-flex rounded-xl border border-line bg-surface p-1 shadow-sm" role="tablist" aria-label="Payment sections">
          <button
            role="tab"
            aria-selected={tab === 'providers'}
            onClick={() => setTab('providers')}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors',
              tab === 'providers' ? 'bg-[#101d31] text-white shadow-sm' : 'text-muted hover:bg-canvas hover:text-ink'
            )}
          >
            <Wallet className="h-3.5 w-3.5" /> Providers
          </button>
          <button
            role="tab"
            aria-selected={tab === 'transactions'}
            onClick={() => setTab('transactions')}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors',
              tab === 'transactions' ? 'bg-[#101d31] text-white shadow-sm' : 'text-muted hover:bg-canvas hover:text-ink'
            )}
          >
            <ReceiptText className="h-3.5 w-3.5" /> Transactions
            {transactions.length > 0 && (
              <span className={cn('rounded-full px-1.5 py-0.5 text-[9px]', tab === 'transactions' ? 'bg-white/15 text-white' : 'bg-canvas text-muted')}>
                {transactions.length}
              </span>
            )}
          </button>
        </div>
      </div>

      {freeMode && (
        <FreeModeBanner message="Free mode — no new payments can be created on this platform." />
      )}

      {tab === 'providers' && overview && (
        <>
          <div className="card p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-ink">Checkout environment</h2>
                <p className="mt-1 text-xs text-muted">
                  Which mode checkout uses right now. Testing never changes the other modes.
                </p>
              </div>
              <Badge tone="neutral">current: {MODE_META[overview.environment]?.label}</Badge>
            </div>
            {(() => {
              const live = activeFor(overview.environment);
              return (
                <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl bg-[#101d31] px-4 py-3.5 text-white">
                  <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-white/[0.08] text-brand-300"><Activity className="h-4 w-4" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[9px] font-semibold uppercase tracking-[0.16em] text-slate-400">Checkout is currently using</p>
                    <p className="mt-0.5 text-sm font-semibold">
                      {MODE_META[overview.environment]?.label} · {live?.display_name ?? 'No active provider'}
                    </p>
                  </div>
                  <span className={cn(
                    'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10px] font-semibold',
                    live ? 'bg-success/20 text-success-soft' : 'bg-warning/20 text-warning-soft'
                  )}>
                    <span className={cn('h-1.5 w-1.5 rounded-full', live ? 'bg-success' : 'bg-warning')} />
                    {live ? 'Accepting payments' : 'Checkout unavailable'}
                  </span>
                </div>
              );
            })()}
            <div className="mt-3 grid gap-3 md:grid-cols-3">
              {overview.modes.map((mode) => {
                const disabled = mode === 'demo' && !overview.demo_allowed;
                const current = overview.environment === mode;
                const active = activeFor(mode);
                return (
                  <button
                    key={mode}
                    disabled={disabled}
                    onClick={() => setEnvironment(mode)}
                    className={cn(
                      'rounded-xl border p-4 text-left transition-all',
                      current
                        ? 'border-brand-400 bg-brand-50 shadow-sm ring-1 ring-brand-100'
                        : 'border-line bg-white hover:border-line-strong hover:bg-canvas',
                      disabled && 'cursor-not-allowed opacity-50'
                    )}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-sm font-semibold text-ink">{MODE_META[mode].label}</span>
                      {current ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-brand-500 px-2 py-0.5 text-[9px] font-semibold text-white"><Check className="h-2.5 w-2.5" /> Current</span>
                      ) : active ? (
                        <span className="inline-flex items-center gap-1 text-[9px] font-semibold text-success"><span className="h-1.5 w-1.5 rounded-full bg-success" /> Active</span>
                      ) : (
                        <span className="text-[9px] font-medium text-muted">No active provider</span>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-muted">{MODE_META[mode].note}</p>
                    <p className={cn('mt-2 truncate text-xs font-medium', active ? 'text-ink' : 'text-warning')}>
                      {active ? active.display_name : 'Not accepting payments'}
                    </p>
                  </button>
                );
              })}
            </div>
            {!overview.demo_allowed && (
              <p className="mt-3 text-xs text-danger">Demo is disabled because this deployment is in production.</p>
            )}
          </div>

          {overview.modes.map((mode) => (
            <section key={mode} className="space-y-3">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-sm font-semibold text-ink">{MODE_META[mode].label}</h2>
                <ModeBadge mode={mode} />
                <span className="text-xs text-muted">{MODE_META[mode].note}</span>
                <span className={cn(
                  'ml-auto inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-semibold',
                  activeFor(mode) ? 'border-green-200 bg-success-soft text-success' : 'border-amber-200 bg-warning-soft text-warning'
                )}>
                  <span className={cn('h-1.5 w-1.5 rounded-full', activeFor(mode) ? 'bg-success' : 'bg-warning')} />
                  {activeFor(mode) ? `${activeFor(mode)!.display_name} is active` : 'No provider active'}
                </span>
              </div>
              <div className="grid gap-4 lg:grid-cols-2">
                {overview.catalog
                  .filter((meta) => meta.modes.includes(mode))
                  .map((meta) => {
                    const provider = providersBy(meta.driver, mode);
                    const isActive = Boolean(provider?.is_active);
                    return (
                      <div
                        key={`${mode}:${meta.driver}`}
                        className={cn(
                          'card relative flex flex-col gap-4 p-5 transition-all',
                          isActive && 'border-success/40 shadow-[0_14px_34px_-28px_rgba(44,168,127,0.55)] ring-1 ring-success/10'
                        )}
                      >
                        <div className="flex items-start gap-3">
                          <BrandLogo slug={meta.brand_slug} color={meta.brand_color} name={meta.name} />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <h3 className="text-sm font-semibold text-ink">{meta.name}</h3>
                              {isActive ? (
                                <Badge tone="success"><span className="h-1.5 w-1.5 rounded-full bg-success" /> Active checkout</Badge>
                              ) : provider ? (
                                <Badge tone="neutral">Configured</Badge>
                              ) : (
                                <Badge tone="warning">Not connected</Badge>
                              )}
                            </div>
                            <p className="mt-1 text-xs text-muted">{meta.tagline}</p>
                          </div>
                        </div>

                        <div className="flex flex-wrap gap-1.5">
                          {meta.capabilities.slice(0, 5).map((cap) => (
                            <span key={cap} className="rounded-md border border-line bg-canvas px-2 py-0.5 text-[11px] text-muted">
                              {cap}
                            </span>
                          ))}
                        </div>

                        <div className="mt-auto flex flex-wrap gap-2">
                          {provider ? (
                            <>
                              <Button size="sm" variant="ghost" onClick={() => openWizard(meta, mode)}>
                                Manage
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                loading={testing}
                                onClick={() => testProvider(provider)}
                              >
                                <FlaskConical className="h-3.5 w-3.5" /> Test
                              </Button>
                              {provider.is_active ? (
                                <Button
                                  size="sm"
                                  variant="outline"
                                  loading={busyId === provider.id}
                                  onClick={() => deactivateProvider(provider)}
                                  className="text-danger hover:border-red-200 hover:bg-danger-soft"
                                >
                                  <CircleOff className="h-3.5 w-3.5" /> Deactivate
                                </Button>
                              ) : (
                                <Button
                                  size="sm"
                                  variant="primary"
                                  loading={busyId === provider.id}
                                  onClick={() => activateProvider(provider)}
                                >
                                  <Zap className="h-3.5 w-3.5" /> Activate
                                </Button>
                              )}
                            </>
                          ) : (
                            <Button size="sm" variant="primary" onClick={() => openWizard(meta, mode)}>
                              Connect
                            </Button>
                          )}
                        </div>
                      </div>
                    );
                  })}
              </div>
            </section>
          ))}
        </>
      )}

      {tab === 'transactions' && (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              { label: 'Collected', value: `₹${transactionStats.collected.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`, hint: 'Successful payments', icon: Wallet, tone: 'bg-success-soft text-success' },
              { label: 'Successful', value: transactionStats.paid, hint: 'Completed orders', icon: Check, tone: 'bg-brand-50 text-brand-600' },
              { label: 'Pending', value: transactionStats.pending, hint: 'Awaiting confirmation', icon: Clock, tone: 'bg-warning-soft text-warning' },
              { label: 'Failed', value: transactionStats.failed, hint: 'Not completed', icon: X, tone: 'bg-danger-soft text-danger' },
            ].map((stat) => (
              <div key={stat.label} className="card flex items-center gap-3 p-4">
                <span className={cn('flex h-10 w-10 items-center justify-center rounded-xl', stat.tone)}><stat.icon className="h-4 w-4" /></span>
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted">{stat.label}</p>
                  <p className="mt-0.5 text-lg font-semibold text-ink">{stat.value}</p>
                  <p className="text-[10px] text-muted">{stat.hint}</p>
                </div>
              </div>
            ))}
          </div>

          <div className="card overflow-hidden">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">Transactions</h2>
              <p className="text-xs text-muted">{transactions.length} order(s)</p>
            </div>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <input
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="Search email or order ref..."
                className="input-field w-64 pl-9"
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-canvas text-xs uppercase text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Order</th>
                  <th className="px-4 py-3 font-medium">User</th>
                  <th className="px-4 py-3 font-medium">Plan</th>
                  <th className="px-4 py-3 font-medium">Amount</th>
                  <th className="px-4 py-3 font-medium">Provider</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Date</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {filteredTransactions.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-12 text-center text-muted">
                      <CreditCard className="mx-auto mb-3 h-10 w-10 opacity-40" />
                      No payments found.
                    </td>
                  </tr>
                ) : (
                  filteredTransactions.map((payment) => (
                    <tr key={payment.id} className="hover:bg-canvas/60">
                      <td className="px-4 py-3">
                        <div className="font-mono text-xs text-ink">{payment.merchant_txn_id}</div>
                        {payment.provider_transaction_id && (
                          <div className="mt-0.5 font-mono text-[11px] text-muted">
                            {payment.provider_transaction_id}
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-ink">{payment.user_name || 'User'}</div>
                        <div className="text-xs text-muted">{payment.user_email}</div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge tone="brand">{payment.plan_name || '—'}</Badge>
                      </td>
                      <td className="px-4 py-3 font-semibold text-ink">
                        ₹{(payment.amount_inr / 100).toFixed(2)}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex flex-wrap items-center gap-1">
                          <span className="text-xs capitalize text-ink">{payment.provider || '—'}</span>
                          {payment.mode && <ModeBadge mode={payment.mode} />}
                          {payment.is_test && <Badge tone="neutral">test</Badge>}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {payment.status === 'success' ? (
                          <Badge tone="success"><Check className="h-3 w-3" /> Success</Badge>
                        ) : payment.status === 'failed' ? (
                          <Badge tone="danger"><X className="h-3 w-3" /> Failed</Badge>
                        ) : (
                          <Badge tone="warning"><Clock className="h-3 w-3" /> Pending</Badge>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-xs text-muted">
                        {new Date(payment.created_at).toLocaleString()}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
          </div>
        </div>
      )}

      {wizard && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-4">
          <div className="my-8 w-full max-w-2xl rounded-xl border border-line bg-surface">
            <div className="flex items-start justify-between gap-3 border-b border-line p-5">
              <div className="flex items-start gap-3">
                <BrandLogo slug={wizard.meta.brand_slug} color={wizard.meta.brand_color} name={wizard.meta.name} />
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <h2 className="text-base font-semibold text-ink">
                      {wizard.provider ? `Manage ${wizard.meta.name}` : `Connect ${wizard.meta.name}`}
                    </h2>
                    <ModeBadge mode={wizard.mode} />
                    {wizard.provider?.is_active && <Badge tone="success"><span className="h-1.5 w-1.5 rounded-full bg-success" /> Active checkout</Badge>}
                  </div>
                  <p className="mt-1 text-xs text-muted">{wizard.meta.tagline}</p>
                </div>
              </div>
              <button onClick={() => setWizard(null)} className="text-muted hover:text-ink">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-5 p-5">
              <div className="flex flex-wrap gap-1.5">
                {wizard.meta.capabilities.map((cap) => (
                  <span key={cap} className="rounded-md border border-line bg-canvas px-2 py-0.5 text-[11px] text-muted">
                    {cap}
                  </span>
                ))}
              </div>

              {wizard.meta.fields.length > 0 && (
                <div className="space-y-3">
                  <h3 className="text-sm font-semibold text-ink">Credentials</h3>
                  {wizard.meta.fields.map((field) => (
                    <Input
                      key={field.key}
                      label={field.label}
                      type={field.secret ? 'password' : 'text'}
                      value={creds[field.key] ?? ''}
                      placeholder={
                        wizard.provider?.credential_preview?.[field.key] || field.placeholder
                      }
                      onChange={(e) => setCreds({ ...creds, [field.key]: e.target.value })}
                      hint={field.hint}
                    />
                  ))}
                  {wizard.provider && (
                    <p className="text-xs text-muted">
                      Leave a secret blank to keep the saved value. Saving new credentials resets the test status.
                    </p>
                  )}
                  {!wizard.provider && (
                    <p className="text-xs text-muted">
                      After saving, this screen shows the webhook URL and the events to paste into your provider dashboard.
                    </p>
                  )}
                  <div className="flex justify-end">
                    <Button onClick={saveProvider} loading={saving}>
                      {wizard.provider ? 'Save changes' : 'Save provider'}
                    </Button>
                  </div>
                </div>
              )}

              {wizard.meta.fields.length === 0 && (
                <div className="rounded-lg border border-line bg-canvas p-4 text-sm text-muted">
                  Demo mode needs no credentials. It simulates success or failure locally and never calls a provider.
                  {wizard.provider ? ' Activate it to use demo checkout.' : ' Save it, then activate it.'}
                  <div className="mt-3 flex justify-end">
                    <Button onClick={saveProvider} loading={saving} disabled={!!wizard.provider}>
                      {wizard.provider ? 'Saved' : 'Save demo provider'}
                    </Button>
                  </div>
                </div>
              )}

              {wizard.provider && (
                <>
                  <div className="rounded-xl border border-line p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <ShieldCheck className="h-4 w-4 text-muted" />
                        <h3 className="text-sm font-semibold text-ink">Webhook</h3>
                      </div>
                      {wizard.provider.last_test_status && (
                        <Badge tone={wizard.provider.last_test_status === 'ok' ? 'success' : 'danger'}>
                          test: {wizard.provider.last_test_status}
                        </Badge>
                      )}
                    </div>
                    {wizard.mode === 'demo' ? (
                      <p className="mt-2 text-xs text-muted">Demo mode does not use a webhook.</p>
                    ) : (
                      <>
                        <p className="mt-1 text-xs text-muted">{wizard.meta.webhook_notes}</p>
                        <div className="mt-2 flex items-center gap-2">
                          <input readOnly value={wizard.provider.webhook_url} className="input-field flex-1 font-mono text-xs" />
                          <Button size="sm" variant="ghost" onClick={() => copy(wizard.provider!.webhook_url)}>
                            <Copy className="h-3.5 w-3.5" /> Copy
                          </Button>
                        </div>
                        {wizard.meta.webhook_events.length > 0 && (
                          <div className="mt-3">
                            <p className="text-xs font-medium text-ink">Events to enable</p>
                            <div className="mt-1 flex flex-wrap gap-1.5">
                              {wizard.meta.webhook_events.map((event) => (
                                <span key={event} className="rounded-md border border-line bg-canvas px-2 py-0.5 font-mono text-[11px] text-muted">
                                  {event}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}
                        <a
                          href={wizard.meta.docs_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-brand hover:underline"
                        >
                          Provider setup docs <ExternalLink className="h-3 w-3" />
                        </a>
                      </>
                    )}
                    {wizard.provider.last_test_error && (
                      <p className="mt-2 text-xs text-danger">{wizard.provider.last_test_error}</p>
                    )}
                  </div>

                  <div className="flex flex-wrap justify-between gap-2">
                    <Button variant="ghost" onClick={() => deleteProvider(wizard.provider!)}>
                      <Trash2 className="h-3.5 w-3.5" /> Delete
                    </Button>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="ghost"
                        loading={testing}
                        onClick={() => testProvider(wizard.provider!)}
                      >
                        <FlaskConical className="h-3.5 w-3.5" /> Test connection
                      </Button>
                      {wizard.provider.is_active ? (
                        <Button
                          variant="outline"
                          loading={busyId === wizard.provider.id}
                          onClick={() => deactivateProvider(wizard.provider!)}
                          className="text-danger hover:border-red-200 hover:bg-danger-soft"
                        >
                          <CircleOff className="h-3.5 w-3.5" /> Deactivate for {MODE_META[wizard.mode]?.label}
                        </Button>
                      ) : (
                        <Button
                          loading={busyId === wizard.provider.id}
                          onClick={() => activateProvider(wizard.provider!)}
                        >
                          <Zap className="h-3.5 w-3.5" /> Activate for {MODE_META[wizard.mode]?.label}
                        </Button>
                      )}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
