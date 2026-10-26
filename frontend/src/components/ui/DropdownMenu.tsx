import { useState } from 'react';
import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '../../lib/cn';

export interface MenuItem {
  label: string;
  icon?: LucideIcon;
  onSelect?: () => void;
  href?: string;
  danger?: boolean;
  disabled?: boolean;
}

export default function DropdownMenu({
  trigger,
  items,
  align = 'right',
  className,
  menuClassName,
}: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  items: MenuItem[];
  align?: 'left' | 'right';
  className?: string;
  menuClassName?: string;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className={cn('relative', className)}>
      {trigger({ open, toggle: () => setOpen((value) => !value) })}
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} aria-hidden="true" />
          <div
            className={cn(
              'absolute top-full z-40 mt-1 min-w-[190px] overflow-hidden rounded-xl border border-line bg-surface p-1 shadow-xl',
              align === 'right' ? 'right-0' : 'left-0',
              menuClassName
            )}
          >
            {items.map((item) => {
              const Icon = item.icon;
              const content = (
                <>
                  {Icon && <Icon className="h-3.5 w-3.5 shrink-0" />}
                  <span className="truncate">{item.label}</span>
                </>
              );
              const classes = cn(
                'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-xs font-medium transition-colors',
                item.danger
                  ? 'text-danger hover:bg-danger-soft'
                  : 'text-muted hover:bg-canvas hover:text-ink',
                item.disabled && 'cursor-not-allowed opacity-40 hover:bg-transparent'
              );

              if (item.href) {
                return (
                  <a
                    key={item.label}
                    href={item.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={classes}
                    onClick={() => setOpen(false)}
                  >
                    {content}
                  </a>
                );
              }
              return (
                <button
                  key={item.label}
                  className={classes}
                  disabled={item.disabled}
                  onClick={() => {
                    setOpen(false);
                    item.onSelect?.();
                  }}
                >
                  {content}
                </button>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
