import { useEffect, useMemo, useState } from 'react';
import {
  Activity,
  ArrowUpRight,
  Bot,
  CheckCircle2,
  CreditCard,
  Database,
  IndianRupee,
  MessageSquare,
  Server,
  Users,
} from 'lucide-react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import toast from 'react-hot-toast';
import api from '../../api';
import StatsCard from '../../components/ui/StatsCard';
import Avatar from '../../components/ui/Avatar';
import EmptyState from '../../components/ui/EmptyState';
import { Badge } from '../../components/ui/Badge';

const COLORS = ['#4680FF', '#2CA87F', '#E58A00', '#3EC9D6', '#8B5CF6', '#F43F5E'];

interface TrendPoint {
  date: string;
  label: string;
  users: number;
  revenue: number;
  messages: number;
}

interface PlanSlice {
  name: string;
  display_name: string;
  count: number;
}

interface PaymentRow {
  id: string;
  merchant_txn_id: string;
  amount_inr: number;
  status: string;
  plan_name: string | null;
  user_name: string | null;
  user_email: string | null;
  provider: string | null;
  mode: string | null;
  created_at: string;
}

interface UserRow {
  id: string;
  first_name: string;
  last_name?: string | null;
  username?: string | null;
  email?: string | null;
  current_plan?: string | null;
  created_at: string;
}

export default function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [trend, setTrend] = useState<{ series: TrendPoint[]; plans: PlanSlice[] }>({
    series: [],
    plans: [],
  });
  const [health, setHealth] = useState<any>(null);
  const [payments, setPayments] = useState<PaymentRow[]>([]);
  const [users, setUsers] = useState<UserRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      const results = await Promise.allSettled([
        api.get('/analytics/dashboard'),
        api.get('/analytics/trends?days=7'),
        api.get('/analytics/system-health'),
        api.get('/payments/all'),
        api.get('/users/?limit=5'),
      ]);
      if (results[0].status === 'fulfilled') setStats(results[0].value.data);
      if (results[1].status === 'fulfilled') setTrend(results[1].value.data);
      if (results[2].status === 'fulfilled') setHealth(results[2].value.data);
      if (results[3].status === 'fulfilled') setPayments(results[3].value.data.slice(0, 5));
      if (results[4].status === 'fulfilled') setUsers(results[4].value.data.slice(0, 5));
      if (results.every((r) => r.status === 'rejected')) {
        toast.error('Could not load dashboard data.');
      }
      setLoading(false);
    };
    load();
  }, []);

  const planTotal = useMemo(
    () => trend.plans.reduce((sum, plan) => sum + plan.count, 0),
    [trend.plans]
  );

  if (loading) {
    return (
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="h-16 animate-pulse rounded-xl bg-surface" />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-32 animate-pulse rounded-xl bg-surface" />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="h-80 animate-pulse rounded-xl bg-surface lg:col-span-2" />
          <div className="h-80 animate-pulse rounded-xl bg-surface" />
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-brand-600">
            <Activity className="h-3.5 w-3.5" /> Live overview
          </p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">Welcome back</h1>
          <p className="mt-1 text-sm text-muted">
            {new Date().toLocaleDateString(undefined, {
              weekday: 'long',
              day: 'numeric',
              month: 'long',
              year: 'numeric',
            })}
            {' · '}
            Vidhya AI is running normally.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone="success">
            <span className="h-1.5 w-1.5 rounded-full bg-success" /> All systems operational
          </Badge>
          <a
            href="/"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-outline gap-1.5 text-xs"
          >
            Open site <ArrowUpRight className="h-3.5 w-3.5" />
          </a>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatsCard
          label="Total users"
          value={stats?.total_users ?? 0}
          hint={`${stats?.active_users_today ?? 0} active today`}
          icon={Users}
          tone="brand"
          trend={12.5}
        />
        <StatsCard
          label="Revenue"
          value={`₹${(stats?.total_revenue ?? 0).toLocaleString()}`}
          hint={`₹${(stats?.revenue_this_month ?? 0).toLocaleString()} this month`}
          icon={IndianRupee}
          tone="success"
          trend={8.2}
        />
        <StatsCard
          label="Messages today"
          value={(stats?.total_messages_today ?? 0).toLocaleString()}
          hint={`${(stats?.total_tokens_today ?? 0).toLocaleString()} tokens processed`}
          icon={MessageSquare}
          tone="info"
          trend={4.1}
        />
        <StatsCard
          label="Active subscriptions"
          value={stats?.active_subscriptions ?? 0}
          hint={`${stats?.total_conversations ?? 0} conversations · ${stats?.total_documents ?? 0} docs`}
          icon={CreditCard}
          tone="warning"
          trend={-1.4}
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card p-5 lg:col-span-2">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-ink">Revenue & activity</h3>
              <p className="text-xs text-muted">Last 7 days · paid orders and chat volume</p>
            </div>
            <Badge tone="brand">7 days</Badge>
          </div>
          <div className="h-[280px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trend.series} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="revenueFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#4680FF" stopOpacity={0.32} />
                    <stop offset="100%" stopColor="#4680FF" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#E6EBF1" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#5B6B79' }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#5B6B79' }} />
                <Tooltip
                  contentStyle={{
                    borderRadius: 10,
                    border: '1px solid #E6EBF1',
                    fontSize: 12,
                    boxShadow: '0 10px 30px -12px rgba(29,38,48,.25)',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  name="Revenue (₹)"
                  stroke="#4680FF"
                  strokeWidth={2.5}
                  fill="url(#revenueFill)"
                />
                <Area
                  type="monotone"
                  dataKey="messages"
                  name="Messages"
                  stroke="#2CA87F"
                  strokeWidth={2}
                  fillOpacity={0}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <div className="mb-2">
            <h3 className="text-sm font-semibold text-ink">Active plans</h3>
            <p className="text-xs text-muted">{planTotal} active subscriptions</p>
          </div>
          {trend.plans.length === 0 ? (
            <EmptyState icon={CreditCard} title="No active plans yet" description="Plan distribution appears after the first subscription." />
          ) : (
            <>
              <div className="h-[190px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={trend.plans}
                      dataKey="count"
                      nameKey="display_name"
                      innerRadius={54}
                      outerRadius={78}
                      paddingAngle={3}
                      stroke="none"
                    >
                      {trend.plans.map((_, index) => (
                        <Cell key={index} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ borderRadius: 10, border: '1px solid #E6EBF1', fontSize: 12 }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="space-y-2">
                {trend.plans.map((plan, index) => (
                  <div key={plan.name} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-2 text-muted">
                      <span
                        className="h-2 w-2 rounded-full"
                        style={{ background: COLORS[index % COLORS.length] }}
                      />
                      {plan.display_name}
                    </span>
                    <span className="font-semibold text-ink">{plan.count}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card p-5 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-ink">New signups</h3>
              <p className="text-xs text-muted">Accounts created per day</p>
            </div>
          </div>
          <div className="h-[190px] w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={trend.series} margin={{ top: 4, right: 8, left: -24, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E6EBF1" vertical={false} />
                <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#5B6B79' }} />
                <YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: '#5B6B79' }} />
                <Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #E6EBF1', fontSize: 12 }} />
                <Bar dataKey="users" name="Signups" fill="#4680FF" radius={[6, 6, 0, 0]} maxBarSize={28} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card p-5">
          <div className="mb-3 flex items-center gap-2">
            <Server className="h-4 w-4 text-muted" />
            <h3 className="text-sm font-semibold text-ink">System health</h3>
          </div>
          <div className="space-y-2.5">
            {health?.services &&
              Object.entries(health.services).map(([name, value]: [string, any]) => {
                const ok = ['connected', 'configured', 'online'].includes(value.status);
                return (
                  <div key={name} className="flex items-center justify-between rounded-lg border border-line bg-canvas/60 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className={`h-2 w-2 rounded-full ${ok ? 'bg-success' : 'bg-warning'}`} />
                      <span className="text-xs font-medium capitalize text-ink">{name}</span>
                    </div>
                    <div className="text-right">
                      <p className={`text-[11px] font-semibold ${ok ? 'text-success' : 'text-warning'}`}>
                        {value.status}
                      </p>
                      {value.latency_ms != null && (
                        <p className="text-[10px] text-muted">{value.latency_ms} ms</p>
                      )}
                    </div>
                  </div>
                );
              })}
            {!health?.services && (
              <p className="text-xs text-muted">Health data unavailable.</p>
            )}
          </div>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div>
              <h3 className="text-sm font-semibold text-ink">Recent users</h3>
              <p className="text-xs text-muted">Latest account signups</p>
            </div>
            <Users className="h-4 w-4 text-muted" />
          </div>
          {users.length === 0 ? (
            <EmptyState icon={Users} title="No users yet" description="New accounts will appear here." />
          ) : (
            <div className="divide-y divide-line">
              {users.map((user) => (
                <div key={user.id} className="flex items-center gap-3 px-5 py-3">
                  <Avatar name={`${user.first_name} ${user.last_name ?? ''}`} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">
                      {user.first_name} {user.last_name ?? ''}
                    </p>
                    <p className="truncate text-xs text-muted">
                      {user.email || (user.username ? `@${user.username}` : '—')}
                    </p>
                  </div>
                  <Badge tone="brand">{user.current_plan || 'free'}</Badge>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="card overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div>
              <h3 className="text-sm font-semibold text-ink">Recent payments</h3>
              <p className="text-xs text-muted">Latest checkout activity</p>
            </div>
            <IndianRupee className="h-4 w-4 text-muted" />
          </div>
          {payments.length === 0 ? (
            <EmptyState icon={CreditCard} title="No payments yet" description="Payments will appear after the first checkout." />
          ) : (
            <div className="divide-y divide-line">
              {payments.map((payment) => (
                <div key={payment.id} className="flex items-center gap-3 px-5 py-3">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-success-soft text-success">
                    {payment.status === 'success' ? <CheckCircle2 className="h-4 w-4" /> : <CreditCard className="h-4 w-4" />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">
                      {payment.user_name || payment.user_email || 'User'}
                    </p>
                    <p className="truncate text-xs text-muted">
                      {payment.plan_name || 'Plan'} · {payment.provider || '—'} ·{' '}
                      {new Date(payment.created_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-semibold text-ink">₹{(payment.amount_inr / 100).toFixed(2)}</p>
                    <p className={`text-[10px] font-semibold uppercase ${payment.status === 'success' ? 'text-success' : 'text-warning'}`}>
                      {payment.status}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {[
          { icon: Database, label: 'PostgreSQL', value: `${health?.services?.postgres?.tables ?? 22} tables` },
          { icon: Bot, label: 'AI provider', value: health?.services?.ai?.model || 'Not configured' },
          { icon: Activity, label: 'Uptime', value: `${Math.round((health?.uptime_seconds ?? 0) / 60)} min` },
        ].map((item) => (
          <div key={item.label} className="card flex items-center gap-3 p-4">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
              <item.icon className="h-4 w-4" />
            </span>
            <div>
              <p className="text-xs text-muted">{item.label}</p>
              <p className="text-sm font-semibold text-ink">{item.value}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
