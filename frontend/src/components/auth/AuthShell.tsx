import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { LogoStacked } from '../brand/Logo';

export default function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas p-6">
      <div className="w-full max-w-[440px]">
        <div className="mb-7 flex justify-center">
          <Link to="/" aria-label="Vidhya AI home">
            <LogoStacked width={190} />
          </Link>
        </div>

        <div className="card p-8">
          <div className="mb-6">
            <h1 className="text-xl font-semibold text-ink">{title}</h1>
            {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
          </div>
          {children}
        </div>

        {footer && <div className="mt-5 text-center text-xs text-muted">{footer}</div>}
      </div>
    </div>
  );
}
