import type { HTMLAttributes } from 'react';
import { cn } from '../../lib/cn';

type Tone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger' | 'info';

const tones: Record<Tone, string> = {
  neutral: 'bg-canvas text-muted border-line',
  brand: 'bg-brand-50 text-brand-600 border-brand-100',
  success: 'bg-success-soft text-success border-green-200',
  warning: 'bg-warning-soft text-warning border-amber-200',
  danger: 'bg-danger-soft text-danger border-red-200',
  info: 'bg-info-soft text-info border-cyan-200',
};

export function Badge({
  tone = 'neutral',
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium',
        tones[tone],
        className
      )}
      {...props}
    />
  );
}
