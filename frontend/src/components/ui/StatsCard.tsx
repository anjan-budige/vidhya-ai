import type { LucideIcon } from 'lucide-react';
import { ArrowDownRight, ArrowUpRight } from 'lucide-react';
import { cn } from '../../lib/cn';

type Tone = 'brand' | 'success' | 'warning' | 'info' | 'danger';

const tones: Record<Tone, { chip: string; bar: string; glow: string }> = {
  brand: {
    chip: 'bg-brand-50 text-brand-600 ring-brand-100',
    bar: 'from-brand-400 to-brand-600',
    glow: 'bg-brand-100/50',
  },
  success: {
    chip: 'bg-success-soft text-success ring-green-100',
    bar: 'from-emerald-400 to-success',
    glow: 'bg-emerald-100/50',
  },
  warning: {
    chip: 'bg-warning-soft text-warning ring-amber-100',
    bar: 'from-amber-300 to-warning',
    glow: 'bg-amber-100/50',
  },
  info: {
    chip: 'bg-info-soft text-info ring-cyan-100',
    bar: 'from-cyan-300 to-info',
    glow: 'bg-cyan-100/50',
  },
  danger: {
    chip: 'bg-danger-soft text-danger ring-red-100',
    bar: 'from-rose-300 to-danger',
    glow: 'bg-rose-100/50',
  },
};

export default function StatsCard({
  label,
  value,
  hint,
  icon: Icon,
  tone = 'brand',
  trend,
  className,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: LucideIcon;
  tone?: Tone;
  trend?: number;
  className?: string;
}) {
  const t = tones[tone];
  const positive = (trend ?? 0) >= 0;
  return (
    <div className={cn('card card-hover group relative overflow-hidden p-5', className)}>
      <div className={cn('pointer-events-none absolute -right-8 -top-8 h-28 w-28 rounded-full blur-2xl transition-opacity group-hover:opacity-100 opacity-70', t.glow)} />
      <div className="relative flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</p>
          <p className="mt-2 text-[28px] font-bold leading-none tracking-tight text-ink">{value}</p>
          {hint && <p className="mt-2 text-xs text-muted">{hint}</p>}
        </div>
        <span className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ring-1', t.chip)}>
          <Icon className="h-5 w-5" />
        </span>
      </div>
      {typeof trend === 'number' && (
        <div className="relative mt-4 flex items-center gap-2">
          <span
            className={cn(
              'inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 text-[11px] font-semibold',
              positive ? 'bg-success-soft text-success' : 'bg-danger-soft text-danger'
            )}
          >
            {positive ? <ArrowUpRight className="h-3 w-3" /> : <ArrowDownRight className="h-3 w-3" />}
            {Math.abs(trend).toFixed(1)}%
          </span>
          <span className="text-[11px] text-muted">vs previous period</span>
        </div>
      )}
      <div className={cn('absolute inset-x-0 bottom-0 h-0.5 bg-gradient-to-r opacity-80', t.bar)} />
    </div>
  );
}
