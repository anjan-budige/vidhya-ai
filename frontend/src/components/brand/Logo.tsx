import { cn } from '../../lib/cn';

export function LogoMark({
  className,
  size = 32,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <img
      src="/vidhya_mark.png"
      alt="Vidhya AI"
      width={size}
      height={size}
      draggable={false}
      className={cn('object-contain select-none', className)}
    />
  );
}

export function LogoLockup({
  className,
  markSize = 30,
  textClassName,
}: {
  className?: string;
  markSize?: number;
  textClassName?: string;
}) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <LogoMark size={markSize} />
      <span
        className={cn('font-semibold tracking-tight text-ink', textClassName)}
        style={{ fontSize: Math.round(markSize * 0.53) }}
      >
        Vidhya AI
      </span>
    </span>
  );
}

export function BrandLockup({
  markSize = 56,
  className,
}: {
  markSize?: number;
  className?: string;
}) {
  return (
    <div className={cn('flex flex-col items-center', className)}>
      <LogoMark size={markSize} />
      <span className="mt-3 text-xl font-semibold tracking-tight text-ink">Vidhya AI</span>
      <span className="mt-1.5 text-[10px] font-medium uppercase tracking-[0.22em] text-muted">
        Learn from what matters
      </span>
    </div>
  );
}

export function LogoFull({
  className,
  height = 44,
}: {
  className?: string;
  height?: number;
}) {
  return (
    <img
      src="/vidhya_logo_horizontal.png"
      alt="Vidhya AI"
      draggable={false}
      style={{ height }}
      className={cn('w-auto object-contain select-none', className)}
    />
  );
}

export function LogoStacked({
  className,
  width = 200,
}: {
  className?: string;
  width?: number;
}) {
  return (
    <img
      src="/vidhya_logo_stacked.png"
      alt="Vidhya AI — Learn from what matters"
      draggable={false}
      style={{ width }}
      className={cn('h-auto object-contain select-none', className)}
    />
  );
}
