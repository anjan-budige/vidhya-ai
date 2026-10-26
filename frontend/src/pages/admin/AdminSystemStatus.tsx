import { useEffect, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Activity,
  AlertTriangle,
  Bot,
  Boxes,
  CheckCircle2,
  CreditCard,
  Database,
  HardDrive,
  RefreshCw,
  Server,
  XCircle,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';
import { Badge } from '../../components/ui/Badge';

type HealthLevel = 'good' | 'warn' | 'bad';

function classify(status?: string): HealthLevel {
  if (!status) return 'bad';
  if (['connected', 'configured', 'healthy', 'online'].includes(status)) return 'good';
  if (['degraded', 'not_configured'].includes(status)) return 'warn';
  return 'bad';
}

const levelStyles: Record<HealthLevel, string> = {
  good: 'border-green-200 bg-success-soft/40',
  warn: 'border-amber-200 bg-warning-soft/40',
  bad: 'border-red-200 bg-danger-soft/40',
};

function StatusIcon({ level }: { level: HealthLevel }) {
  if (level === 'good') return <CheckCircle2 className="h-5 w-5 text-success" />;
  if (level === 'warn') return <AlertTriangle className="h-5 w-5 text-warning" />;
  return <XCircle className="h-5 w-5 text-danger" />;
}

function ServiceCard({
  title,
  subtitle,
  icon: Icon,
  status,
  metrics,
  error,
}: {
  title: string;
  subtitle: string;
  icon: LucideIcon;
  status?: string;
  metrics: { label: string; value: string | number }[];
  error?: string;
}) {
  const level = classify(status);
  return (
    <div className={`card border-2 p-5 transition-colors ${levelStyles[level]}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface text-ink ring-1 ring-line">
            <Icon className="h-5 w-5" />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-ink">{title}</h3>
            <p className="text-xs text-muted">{subtitle}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge tone={level === 'good' ? 'success' : level === 'warn' ? 'warning' : 'danger'}>
            {status || 'unknown'}
          </Badge>
          <StatusIcon level={level} />
        </div>
      </div>

      {metrics.length > 0 && (
        <div className="mt-4 grid grid-cols-2 gap-2">
          {metrics.map((metric) => (
            <div key={metric.label} className="rounded-lg bg-surface/80 px-3 py-2 ring-1 ring-line">
              <p className="text-[10px] font-medium uppercase tracking-wider text-muted">
                {metric.label}
              </p>
              <p className="mt-0.5 truncate text-xs font-semibold text-ink" title={String(metric.value)}>
                {metric.value}
              </p>
            </div>
          ))}
        </div>
      )}

      {error && (
        <p className="mt-3 rounded-md bg-surface/70 px-2.5 py-1.5 text-[11px] text-danger ring-1 ring-red-100">
          {error}
        </p>
      )}
    </div>
  );
}

export default function AdminSystemStatus() {
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchHealth = async () => {
    setRefreshing(true);
    try {
      const response = await api.get('/analytics/system-health');
      setHealth(response.data);
    } catch (err: any) {
      if (err.response?.data) setHealth(err.response.data);
      else toast.error('Unable to load system status.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds: number) => {
    if (!seconds) return '0s';
    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    if (d) return `${d}d ${h}h`;
    if (h) return `${h}h ${m}m`;
    return `${m}m ${Math.floor(seconds % 60)}s`;
  };

  if (loading && !health) {
    return (
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="h-20 animate-pulse rounded-xl bg-surface" />
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="h-48 animate-pulse rounded-xl bg-surface" />
          ))}
        </div>
      </div>
    );
  }

  const services = health?.services || {};
  const overall = classify(health?.status);
  const serviceList = Object.entries(services);
  const healthyCount = serviceList.filter(
    ([, value]: [string, any]) => classify(value?.status) === 'good'
  ).length;

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-600">Operations</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">System Status</h1>
          <p className="mt-1 text-sm text-muted">
            Live health of the API, database, cache, storage, AI and workers.
          </p>
        </div>
        <button onClick={fetchHealth} disabled={refreshing} className="btn-outline gap-2 text-xs">
          <RefreshCw className={`h-3.5 w-3.5 ${refreshing ? 'animate-spin' : ''}`} />
          {refreshing ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      <div className={`card border-2 ${levelStyles[overall]} p-5`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-surface ring-1 ring-line">
              <Activity className={`h-5 w-5 ${overall === 'good' ? 'text-success' : overall === 'warn' ? 'text-warning' : 'text-danger'}`} />
            </span>
            <div>
              <p className="text-sm font-semibold text-ink">
                {overall === 'good' ? 'All systems operational' : 'Attention required'}
              </p>
              <p className="text-xs text-muted">
                {healthyCount}/{serviceList.length} services healthy · checked{' '}
                {health?.timestamp ? new Date(health.timestamp).toLocaleTimeString() : '—'}
              </p>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge tone="neutral">Environment: {health?.environment || 'unknown'}</Badge>
            <Badge tone="neutral">Uptime: {formatUptime(health?.uptime_seconds)}</Badge>
            <Badge tone="brand">v{health?.version || '—'}</Badge>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <ServiceCard
          title="Core API"
          subtitle={health?.service || 'FastAPI'}
          icon={Server}
          status={health?.status}
          metrics={[
            { label: 'Environment', value: health?.environment || 'unknown' },
            { label: 'Uptime', value: formatUptime(health?.uptime_seconds) },
          ]}
        />

        <ServiceCard
          title="PostgreSQL"
          subtitle="Primary database · pgvector"
          icon={Database}
          status={services.postgres?.status}
          metrics={[
            {
              label: 'Latency',
              value: services.postgres?.latency_ms != null ? `${services.postgres.latency_ms} ms` : 'N/A',
            },
            { label: 'Tables', value: services.postgres?.tables ?? '—' },
          ]}
          error={services.postgres?.error}
        />

        <ServiceCard
          title="Redis"
          subtitle="Sessions, quotas and cache"
          icon={HardDrive}
          status={services.redis?.status}
          metrics={[
            {
              label: 'Latency',
              value: services.redis?.latency_ms != null ? `${services.redis.latency_ms} ms` : 'N/A',
            },
            { label: 'Memory', value: services.redis?.used_memory || '—' },
          ]}
          error={services.redis?.error}
        />

        <ServiceCard
          title="Object storage"
          subtitle="Silo · PDF bucket"
          icon={Boxes}
          status={services.object_storage?.status}
          metrics={[
            { label: 'Bucket', value: services.object_storage?.bucket || '—' },
            {
              label: 'Latency',
              value:
                services.object_storage?.latency_ms != null
                  ? `${services.object_storage.latency_ms} ms`
                  : 'N/A',
            },
          ]}
          error={services.object_storage?.error}
        />

        <ServiceCard
          title="AI chat model"
          subtitle={
            services.ai?.chat?.provider
              ? `${services.ai.chat.provider} · ${services.ai.chat.model}`
              : 'No active chat model'
          }
          icon={Bot}
          status={services.ai?.chat?.status}
          metrics={[
            {
              label: 'Context',
              value: services.ai?.chat?.context_window?.toLocaleString() || '—',
            },
            {
              label: 'Max output',
              value: services.ai?.chat?.max_output_tokens?.toLocaleString() || '—',
            },
          ]}
          error={services.ai?.chat?.detail}
        />

        <ServiceCard
          title="AI embeddings"
          subtitle={
            services.ai?.embedding?.provider
              ? `${services.ai.embedding.provider} · ${services.ai.embedding.model}`
              : 'No active embedding model'
          }
          icon={Database}
          status={services.ai?.embedding?.status}
          metrics={[
            { label: 'Dimensions', value: services.ai?.embedding?.dimensions ?? '—' },
            { label: 'Used for', value: 'Document search' },
          ]}
          error={services.ai?.embedding?.detail}
        />

        <ServiceCard
          title="Celery workers"
          subtitle="PDF ingestion, quotas and analytics"
          icon={Activity}
          status={services.celery?.status}
          metrics={[
            {
              label: 'Latency',
              value: services.celery?.latency_ms != null ? `${services.celery.latency_ms} ms` : 'N/A',
            },
            { label: 'Workers online', value: services.celery?.workers_online ?? 0 },
          ]}
          error={services.celery?.error || services.celery?.message}
        />

        <ServiceCard
          title="Payments"
          subtitle={
            services.payments?.provider
              ? `${services.payments.provider} · ${services.payments.environment}`
              : `No active provider · ${services.payments?.environment || '—'}`
          }
          icon={CreditCard}
          status={services.payments?.status}
          metrics={[
            { label: 'Environment', value: services.payments?.environment || '—' },
            { label: 'Provider', value: services.payments?.provider || 'none' },
          ]}
          error={services.payments?.detail}
        />

        <ServiceCard
          title="Telegram bot"
          subtitle="API-key login and chat"
          icon={Bot}
          status={services.telegram_bot?.status}
          metrics={[
            { label: 'Username', value: services.telegram_bot?.username || '—' },
            {
              label: 'Backend',
              value: services.telegram_bot?.status === 'configured' ? 'connected' : 'not configured',
            },
          ]}
        />
      </div>
    </div>
  );
}
