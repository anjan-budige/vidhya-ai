import { useCallback, useEffect, useState } from 'react';
import {
  ArrowRight,
  Building2,
  Check,
  Clock3,
  CreditCard,
  Crown,
  History,
  Info,
  Leaf,
  Loader2,
  MessageSquare,
  ReceiptText,
  RefreshCw,
  Wallet,
  Zap,
} from 'lucide-react';
import { animate, stagger } from 'animejs';
import toast from 'react-hot-toast';
import api from '../../api';
import { Badge } from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import ConfirmModal from '../../components/ui/ConfirmModal';
import { useUser } from '../../contexts/UserContext';
import { fmtDateTime, fmtLimit, fmtRupees, pct } from '../../lib/format';
import { cn } from '../../lib/cn';

interface PublicPlan {
  id: string;
  name: string;
  display_name: string;
  description?: string | null;
  price_inr: number;
  validity_days: number;
  messages_per_day: number;
  messages_per_month: number;
  max_sessions: number;
  max_context_tokens: number;
  max_response_tokens: number;
  features: Record<string, boolean>;
}

interface Subscription {
  plan_id: string | null;
  status: string;
  started_at: string;
  expires_at: string | null;
  plan_display_name: string;
  daily_messages_used: number;
  daily_messages_limit: number;
  monthly_messages_used: number;
  monthly_messages_limit: number;
  sessions_used: number;
  max_sessions: number;
  total_messages_used: number;
  total_tokens_consumed: number;
}

interface Order {
  order_ref: string;
  plan_name?: string | null;
  amount_inr: number;
  order_status: string;
  provider?: string | null;
  mode?: string | null;
  created_at: string;
}

const FEATURE_LABELS: Record<string, string> = {
  rag_enabled: 'Answers grounded in your documents',
  streaming_enabled: 'Live streaming replies',
  history_export: 'Export conversation history',
  priority_queue: 'Priority response queue',
  subject_filter: 'Filter by subject',
  mcq_mode: 'Practice question mode',
};

const planIcons = [Leaf, Zap, Crown, Building2];

export default function UserPlans() {
  const { freeMode, billingEnabled, refreshQuota } = useUser();
  const [tab, setTab] = useState<'plans' | 'history'>('plans');
  const [plans, setPlans] = useState<PublicPlan[]>([]);
  const [subscription, setSubscription] = useState<Subscription | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyPlan, setBusyPlan] = useState<string | null>(null);
  const [demoOrder, setDemoOrder] = useState<{ ref: string; plan: string } | null>(null);
  const [pending, setPending] = useState<{ ref: string; url: string; plan: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [plansRes, subRes, ordersRes] = await Promise.all([
        api.get('/plans/'),
        api.get('/subscriptions/me'),
        api.get('/payments/history'),
      ]);
      setPlans(plansRes.data ?? []);
      setSubscription(subRes.data ?? null);
      setOrders(ordersRes.data ?? []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (loading || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animate('.membership-hero', { y: [14, 0], duration: 560, ease: 'outExpo' });
    animate('.plan-card', {
      y: [16, 0],
      duration: 520,
      delay: stagger(65, { start: 120 }),
      ease: 'outExpo',
    });
  }, [loading, tab]);

  useEffect(() => {
    if (!pending) return;
    let stopped = false;
    const timer = window.setInterval(async () => {
      try {
        const res = await api.get(`/payments/check/${pending.ref}`);
        if (stopped) return;
        if (res.data?.order_status === 'paid') {
          window.clearInterval(timer);
          setPending(null);
          toast.success(`${pending.plan} is active`);
          void load();
          void refreshQuota();
        } else if (res.data?.order_status === 'failed') {
          window.clearInterval(timer);
          setPending(null);
          toast.error('The payment did not complete.');
        }
      } catch {
        // The order reference remains authoritative while the page polls.
      }
    }, 3000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [pending, load, refreshQuota]);

  const startCheckout = async (plan: PublicPlan) => {
    setBusyPlan(plan.id);
    try {
      const res = await api.post('/payments/initiate', {
        plan_id: plan.id,
        idempotency_key: crypto.randomUUID(),
      });
      const order = res.data;
      if (order.mode === 'demo') {
        setDemoOrder({ ref: order.order_ref, plan: plan.display_name });
        return;
      }
      if (!order.payment_url) {
        toast.error('The payment gateway did not return a checkout link.');
        return;
      }
      setPending({ ref: order.order_ref, url: order.payment_url, plan: plan.display_name });
      window.open(order.payment_url, '_blank', 'noopener');
    } catch {
    } finally {
      setBusyPlan(null);
    }
  };

  const activateFree = async (plan: PublicPlan) => {
    setBusyPlan(plan.id);
    try {
      await api.post('/subscriptions/free/activate');
      toast.success('Free plan active');
      void load();
      void refreshQuota();
    } catch {
      // api.ts surfaces the reason.
    } finally {
      setBusyPlan(null);
    }
  };

  const resolveDemo = async (result: 'success' | 'failed') => {
    if (!demoOrder) return;
    setBusyPlan(demoOrder.ref);
    try {
      await api.post(`/payments/demo/${demoOrder.ref}/complete`, { result });
      if (result === 'success') {
        toast.success(`${demoOrder.plan} is active`);
        void refreshQuota();
      } else {
        toast('Payment cancelled.');
      }
      setDemoOrder(null);
      void load();
    } catch {
      // api.ts surfaces the reason.
    } finally {
      setBusyPlan(null);
    }
  };

  const currentPlanId = subscription?.plan_id ?? null;
  const paidPrices = plans.filter((plan) => plan.price_inr > 0).map((plan) => plan.price_inr);
  const bestValuePrice = paidPrices.length ? Math.max(...paidPrices) : -1;
  const dailyPercent = pct(subscription?.daily_messages_used ?? 0, subscription?.daily_messages_limit ?? 0);
  const monthlyPercent = pct(subscription?.monthly_messages_used ?? 0, subscription?.monthly_messages_limit ?? 0);

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-6 md:px-7 md:py-8">
      <header className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="mb-1.5 inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-brand-600">
            <Crown className="h-3.5 w-3.5" /> Membership
          </div>
          <h1 className="user-display text-2xl font-semibold tracking-tight text-ink md:text-[30px]">A plan that fits how you study.</h1>
          <p className="mt-1.5 text-sm text-muted">More room to explore, revise, and keep every useful conversation.</p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()}><RefreshCw className="h-3.5 w-3.5" /> Refresh</Button>
      </header>

      {freeMode && (
        <div className="mb-5 flex items-center gap-2.5 rounded-xl border border-line bg-white/80 px-4 py-3 text-xs text-muted">
          <ShieldNoticeIcon />
          <span>This workspace is in open-access mode. Plan purchases are disabled and everyone uses the free-plan limits.</span>
        </div>
      )}

      {pending && (
        <div className="mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-brand-100 bg-brand-50 px-4 py-3 text-xs text-brand-800">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="flex-1">Waiting for the {pending.plan} payment to settle. This page updates automatically.</span>
          <a href={pending.url} target="_blank" rel="noopener noreferrer" className="font-semibold underline underline-offset-2">Reopen checkout</a>
        </div>
      )}

      <section className="membership-hero relative mb-6 overflow-hidden rounded-[22px] bg-[#0d1a2d] px-5 py-5 text-white shadow-[0_28px_70px_-40px_rgba(13,26,45,0.9)] md:px-7 md:py-6">
        <div className="pointer-events-none absolute -right-14 -top-24 h-64 w-64 rounded-full bg-brand-500/25 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-28 left-1/3 h-56 w-56 rounded-full bg-info/15 blur-3xl" />
        <div className="pointer-events-none absolute inset-0 user-noise" />

        <div className="relative grid gap-6 md:grid-cols-[minmax(0,1fr)_250px] md:items-center">
          <div>
            <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              <CreditCard className="h-3.5 w-3.5 text-brand-300" /> Your current membership
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-3">
              <h2 className="user-display text-2xl font-semibold tracking-tight text-white md:text-[28px]">{subscription?.plan_display_name || 'Free plan'}</h2>
              <span className="rounded-full border border-white/10 bg-white/[0.07] px-2.5 py-1 text-[10px] font-semibold text-slate-200">
                {currentPlanId && plans.find((plan) => plan.id === currentPlanId)?.price_inr === 0
                  ? 'Free plan · no renewal needed'
                  : subscription?.expires_at ? `Active until ${fmtDateTime(subscription.expires_at)}` : 'No expiry'}
              </span>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-3">
              <UsageLine icon={MessageSquare} label="Today" value={`${subscription?.daily_messages_used ?? 0} / ${fmtLimit(subscription?.daily_messages_limit)}`} percent={dailyPercent} />
              <UsageLine icon={Clock3} label="This month" value={`${subscription?.monthly_messages_used ?? 0} / ${fmtLimit(subscription?.monthly_messages_limit)}`} percent={monthlyPercent} />
              <UsageLine icon={Wallet} label="Saved chats" value={`${subscription?.sessions_used ?? 0} / ${fmtLimit(subscription?.max_sessions)}`} percent={pct(subscription?.sessions_used ?? 0, subscription?.max_sessions ?? 0)} />
            </div>
          </div>

          <div className="hidden rounded-2xl border border-white/[0.08] bg-white/[0.045] p-4 backdrop-blur md:block">
            <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-slate-400">
              <span>Daily allowance</span><span>{fmtLimit(subscription?.daily_messages_limit)}</span>
            </div>
            <p className="user-display mt-3 text-[34px] font-semibold leading-none">{dailyPercent}<span className="text-base text-slate-400">% used</span></p>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-white/10">
              <div className="h-full rounded-full bg-gradient-to-r from-brand-400 to-info transition-[width] duration-700" style={{ width: `${Math.max(dailyPercent, 2)}%` }} />
            </div>
            <p className="mt-3 text-[10px] leading-relaxed text-slate-400">Counters reset at midnight IST. Your chats stay available after a reset.</p>
          </div>
        </div>
      </section>

      <div className="mb-5 inline-flex rounded-xl border border-line bg-white p-1 shadow-sm">
        {[
          { value: 'plans' as const, label: 'Available plans', icon: Wallet },
          { value: 'history' as const, label: 'Payment history', icon: ReceiptText },
        ].map((item) => (
          <button
            key={item.value}
            onClick={() => setTab(item.value)}
            className={cn(
              'inline-flex items-center gap-2 rounded-lg px-3.5 py-2 text-xs font-semibold transition-colors',
              tab === item.value ? 'bg-[#101d31] text-white shadow-sm' : 'text-muted hover:bg-canvas hover:text-ink'
            )}
          >
            <item.icon className="h-3.5 w-3.5" /> {item.label}
            {item.value === 'history' && orders.length > 0 && <span className={cn('rounded-full px-1.5 py-0.5 text-[9px]', tab === item.value ? 'bg-white/15' : 'bg-canvas')}>{orders.length}</span>}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="grid gap-4 lg:grid-cols-4">
          {[1, 2, 3, 4].map((item) => <div key={item} className="h-[390px] animate-pulse rounded-2xl bg-white/80" />)}
        </div>
      ) : tab === 'plans' ? (
        <div className="grid items-stretch gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {plans.map((plan, index) => {
            const isCurrent = plan.id === currentPlanId;
            const isBest = plan.price_inr > 0 && plan.price_inr === bestValuePrice;
            const PlanIcon = planIcons[index % planIcons.length];
            const features = Object.entries(plan.features ?? {}).filter(([, enabled]) => enabled);
            return (
              <article
                key={plan.id}
                className={cn(
                  'plan-card user-card user-card-hover relative flex flex-col overflow-hidden p-5',
                  isCurrent && 'border-brand-300 ring-2 ring-brand-100',
                  isBest && 'border-[#16263f] bg-[#101d31] text-white shadow-[0_24px_60px_-34px_rgba(13,26,45,0.95)]'
                )}
              >
                {isBest && <div className="pointer-events-none absolute -right-10 -top-14 h-40 w-40 rounded-full bg-brand-500/25 blur-3xl" />}
                <div className="relative flex items-start justify-between gap-3">
                  <span className={cn('flex h-10 w-10 items-center justify-center rounded-xl ring-1', isBest ? 'bg-white/[0.08] text-brand-200 ring-white/10' : 'bg-brand-50 text-brand-600 ring-brand-100')}>
                    <PlanIcon className="h-5 w-5" />
                  </span>
                  {isCurrent ? (
                    <span className={cn('rounded-full px-2 py-1 text-[9px] font-semibold uppercase tracking-wider', isBest ? 'bg-white/10 text-white' : 'bg-brand-50 text-brand-700')}>Current</span>
                  ) : isBest ? (
                    <span className="rounded-full bg-gradient-to-r from-brand-400 to-info px-2 py-1 text-[9px] font-bold uppercase tracking-wider text-[#0d1a2d]">Best value</span>
                  ) : plan.price_inr === 0 ? (
                    <Badge tone="success">Free</Badge>
                  ) : null}
                </div>

                <h3 className={cn('user-display relative mt-4 text-lg font-semibold', isBest ? 'text-white' : 'text-ink')}>{plan.display_name}</h3>
                <p className={cn('relative mt-1 min-h-[36px] text-[11px] leading-relaxed', isBest ? 'text-slate-400' : 'text-muted')}>{plan.description || `${plan.validity_days}-day access`}</p>

                <div className="relative mt-4 flex items-end gap-1.5">
                  <span className={cn('user-display text-[30px] font-semibold leading-none tracking-tight', isBest ? 'text-white' : 'text-ink')}>{fmtRupees(plan.price_inr)}</span>
                  <span className={cn('pb-0.5 text-[10px]', isBest ? 'text-slate-400' : 'text-muted')}>{plan.price_inr > 0 ? `/ ${plan.validity_days} days` : 'forever'}</span>
                </div>

                <div className={cn('relative my-4 h-px', isBest ? 'bg-white/10' : 'bg-line')} />

                <ul className={cn('relative flex-1 space-y-2.5 text-[11px] leading-relaxed', isBest ? 'text-slate-300' : 'text-muted')}>
                  {[
                    `${fmtLimit(plan.messages_per_day)} messages / day`,
                    `${fmtLimit(plan.messages_per_month)} messages / month`,
                    `${fmtLimit(plan.max_sessions)} saved chats`,
                    `${plan.max_context_tokens.toLocaleString('en-IN')} context tokens`,
                    ...features.slice(0, 3).map(([key]) => FEATURE_LABELS[key] ?? key.replace(/_/g, ' ')),
                  ].map((line) => (
                    <li key={line} className="flex items-start gap-2">
                      <span className={cn('mt-0.5 flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full', isBest ? 'bg-brand-400/20 text-brand-200' : 'bg-success-soft text-success')}>
                        <Check className="h-2 w-2" />
                      </span>
                      {line}
                    </li>
                  ))}
                </ul>

                <div className="relative mt-5">
                  {isCurrent ? (
                    <button disabled className={cn('w-full cursor-default rounded-xl border py-2.5 text-xs font-semibold', isBest ? 'border-white/10 bg-white/[0.06] text-slate-300' : 'border-line bg-canvas text-muted')}>Your current plan</button>
                  ) : plan.price_inr === 0 ? (
                    <Button variant={isBest ? 'outline' : 'outline'} className="w-full" loading={busyPlan === plan.id} disabled={freeMode || !billingEnabled} onClick={() => void activateFree(plan)}>Switch to free</Button>
                  ) : (
                    <button
                      onClick={() => void startCheckout(plan)}
                      disabled={freeMode || !billingEnabled || Boolean(busyPlan)}
                      className={cn(
                        'flex w-full items-center justify-center gap-1.5 rounded-xl py-2.5 text-xs font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50',
                        isBest ? 'bg-white text-[#101d31] hover:bg-brand-50' : 'bg-[#101d31] text-white hover:bg-[#172942]'
                      )}
                    >
                      {busyPlan === plan.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                      Choose {plan.display_name} <ArrowRight className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="user-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div><h2 className="user-display text-base font-semibold text-ink">Payments</h2><p className="mt-0.5 text-xs text-muted">Every order raised from this account.</p></div>
            <History className="h-5 w-5 text-muted" />
          </div>
          {orders.length ? (
            <div className="divide-y divide-line/80">
              {orders.map((order) => (
                <div key={order.order_ref} className="flex flex-wrap items-center gap-4 px-5 py-4 transition-colors hover:bg-canvas/60">
                  <span className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-xl', order.order_status === 'paid' ? 'bg-success-soft text-success' : order.order_status === 'failed' ? 'bg-danger-soft text-danger' : 'bg-warning-soft text-warning')}>
                    <ReceiptText className="h-4 w-4" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold text-ink">{order.plan_name ?? 'Plan payment'}</p>
                    <p className="mt-0.5 font-mono text-[10px] text-muted">{order.order_ref} · {order.provider ?? 'Provider'}{order.mode ? ` · ${order.mode}` : ''}</p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-ink">₹{(order.amount_inr / 100).toFixed(2)}</p>
                    <p className="mt-0.5 text-[10px] text-muted">{fmtDateTime(order.created_at)}</p>
                  </div>
                  <span className={cn('rounded-full px-2.5 py-1 text-[9px] font-semibold uppercase tracking-wider', order.order_status === 'paid' ? 'bg-success-soft text-success' : order.order_status === 'failed' ? 'bg-danger-soft text-danger' : 'bg-warning-soft text-warning')}>{order.order_status}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="px-5 py-14 text-center">
              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-canvas text-muted"><ReceiptText className="h-5 w-5" /></span>
              <p className="mt-3 text-sm font-semibold text-ink">No payments yet</p>
              <p className="mt-1 text-xs text-muted">Your receipts will appear here.</p>
            </div>
          )}
        </div>
      )}

      <ConfirmModal
        open={Boolean(demoOrder)}
        title="Demo checkout"
        tone="primary"
        confirmLabel="Pay and activate"
        cancelLabel="Cancel payment"
        loading={Boolean(busyPlan)}
        description={<>This workspace is using the <strong className="text-ink">demo</strong> provider for <strong className="text-ink">{demoOrder?.plan}</strong>. Confirming activates the plan immediately; no money moves.</>}
        onConfirm={() => void resolveDemo('success')}
        onClose={() => void resolveDemo('failed')}
      />
    </div>
  );
}

function UsageLine({ icon: Icon, label, value, percent }: { icon: typeof MessageSquare; label: string; value: string; percent: number }) {
  return (
    <div className="rounded-xl border border-white/[0.07] bg-white/[0.04] px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-[10px] text-slate-400"><Icon className="h-3 w-3" /> {label}</div>
      <p className="mt-1 text-xs font-semibold text-white">{value}</p>
      <div className="mt-2 h-1 overflow-hidden rounded-full bg-white/10">
        <div className="h-full rounded-full bg-brand-400/80" style={{ width: `${Math.max(percent, 2)}%` }} />
      </div>
    </div>
  );
}

function ShieldNoticeIcon() {
  return <Info className="h-3.5 w-3.5 shrink-0 text-brand-500" />;
}
