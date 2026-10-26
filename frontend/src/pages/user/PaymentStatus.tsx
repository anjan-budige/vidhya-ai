import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { ArrowRight, CheckCircle2, Clock, Wallet, XCircle } from 'lucide-react';
import api from '../../api';
import Button from '../../components/ui/Button';
import { LogoStacked } from '../../components/brand/Logo';

type Status = 'loading' | 'success' | 'failed' | 'pending' | 'unknown';

interface PaymentResult {
  status: Status;
  order_ref: string | null;
  plan_name: string | null;
  amount_paise: number | null;
}

export default function PaymentStatus() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [result, setResult] = useState<PaymentResult>({
    status: 'loading',
    order_ref: null,
    plan_name: null,
    amount_paise: null,
  });

  useEffect(() => {
    const txnId = searchParams.get('txn_id');
    if (!txnId) {
      setResult({ status: 'unknown', order_ref: null, plan_name: null, amount_paise: null });
      return;
    }

    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 10;

    const check = async () => {
      if (cancelled) return;
      try {
        const res = await api.get(`/payments/check/${txnId}`);
        const data = res.data;
        if (data.order_status === 'paid') {
          setResult({
            status: 'success',
            order_ref: data.order_ref ?? txnId,
            plan_name: data.plan_name ?? null,
            amount_paise: data.amount_inr ?? null,
          });
          return;
        }
        if (data.order_status === 'failed') {
          setResult({
            status: 'failed',
            order_ref: data.order_ref ?? txnId,
            plan_name: data.plan_name ?? null,
            amount_paise: data.amount_inr ?? null,
          });
          return;
        }
        attempts += 1;
        if (attempts >= maxAttempts) {
          setResult({ status: 'pending', order_ref: txnId, plan_name: null, amount_paise: null });
          return;
        }
        window.setTimeout(check, 2000);
      } catch {
        if (!cancelled) {
          setResult({ status: 'pending', order_ref: txnId, plan_name: null, amount_paise: null });
        }
      }
    };

    // Give the provider webhook a moment to land before the first poll.
    const timer = window.setTimeout(check, 1500);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [searchParams]);

  const messages: Record<Status, { title: string; body: string; tone: string }> = {
    loading: {
      title: 'Verifying your payment',
      body: 'Hold on while we confirm the transaction with the payment provider.',
      tone: 'text-brand-600',
    },
    success: {
      title: 'Payment successful',
      body: result.plan_name
        ? `Your ${result.plan_name} plan is active. Limits apply from your next message.`
        : 'Your subscription is active.',
      tone: 'text-success',
    },
    failed: {
      title: 'Payment failed',
      body: 'The transaction did not complete and nothing was charged. You can try again.',
      tone: 'text-danger',
    },
    pending: {
      title: 'Payment still processing',
      body: 'We have not received confirmation yet. Plans activate automatically once the provider reports the payment.',
      tone: 'text-warning',
    },
    unknown: {
      title: 'No payment reference',
      body: 'This page needs a transaction reference. Open Plans & billing to see your orders.',
      tone: 'text-muted',
    },
  };

  const view = messages[result.status];

  return (
    <div className="page-shell flex min-h-screen items-center justify-center p-4">
      <div className="card w-full max-w-md p-8 text-center">
        <LogoStacked width={168} className="mx-auto mb-8" />

        <div className="mb-6 flex justify-center">
          {result.status === 'loading' ? (
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-brand-50 text-brand-600 ring-1 ring-brand-100">
              <Clock className="h-8 w-8 animate-spin" />
            </span>
          ) : result.status === 'success' ? (
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-success-soft text-success ring-1 ring-green-100">
              <CheckCircle2 className="h-8 w-8" />
            </span>
          ) : result.status === 'failed' ? (
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-danger-soft text-danger ring-1 ring-red-100">
              <XCircle className="h-8 w-8" />
            </span>
          ) : (
            <span className="flex h-16 w-16 items-center justify-center rounded-2xl bg-warning-soft text-warning ring-1 ring-amber-100">
              <Wallet className="h-8 w-8" />
            </span>
          )}
        </div>

        <h1 className="text-xl font-semibold text-ink">{view.title}</h1>
        <p className="mx-auto mt-2 max-w-xs text-sm leading-relaxed text-muted">{view.body}</p>

        {(result.amount_paise || result.order_ref) && (
          <div className="mt-6 space-y-2 rounded-xl border border-line bg-canvas p-4 text-left">
            {result.amount_paise ? (
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted">Amount</span>
                <span className="font-semibold text-ink">
                  ₹{(result.amount_paise / 100).toFixed(2)}
                </span>
              </div>
            ) : null}
            {result.order_ref ? (
              <div className="flex items-center justify-between gap-4 text-sm">
                <span className="text-muted">Reference</span>
                <span className="truncate font-mono text-xs text-ink">{result.order_ref}</span>
              </div>
            ) : null}
          </div>
        )}

        <Button className="mt-6 w-full" onClick={() => navigate('/plans')}>
          <ArrowRight className="h-4 w-4" /> Go to Plans &amp; billing
        </Button>
      </div>
    </div>
  );
}
