import { cn } from '../../lib/cn';

const PALETTE = [
  'bg-brand-50 text-brand-600 ring-brand-100',
  'bg-emerald-50 text-emerald-600 ring-emerald-100',
  'bg-amber-50 text-amber-600 ring-amber-100',
  'bg-cyan-50 text-cyan-600 ring-cyan-100',
  'bg-violet-50 text-violet-600 ring-violet-100',
  'bg-rose-50 text-rose-600 ring-rose-100',
];

function initials(name: string) {
  const parts = (name || '?').trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] || '?') + (parts[1]?.[0] || '')).toUpperCase();
}

function hash(value: string) {
  let h = 0;
  for (let i = 0; i < value.length; i += 1) h = (h * 31 + value.charCodeAt(i)) >>> 0;
  return h;
}

export default function Avatar({
  name,
  size = 'md',
  className,
}: {
  name: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}) {
  const sizes = {
    sm: 'h-7 w-7 text-[10px]',
    md: 'h-9 w-9 text-xs',
    lg: 'h-11 w-11 text-sm',
  };
  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full font-semibold ring-1',
        PALETTE[hash(name) % PALETTE.length],
        sizes[size],
        className
      )}
      title={name}
    >
      {initials(name)}
    </span>
  );
}
