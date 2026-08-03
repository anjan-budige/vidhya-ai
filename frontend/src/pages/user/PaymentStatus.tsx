import { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { CheckCircle2, XCircle, ArrowRight, Loader2, Clock } from 'lucide-react';
import api from '../../api';

interface PaymentResult {
  status: 'loading' | 'success' | 'failed' | 'pending';
  merchant_txn_id: string | null;
  plan_name: string | null;
  amount_inr: number | null;
}

export default function PaymentStatus() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [result, setResult] = useState<PaymentResult>({
    status: 'loading',
    merchant_txn_id: null,
    plan_name: null,
    amount_inr: null,
  });

  useEffect(() => {
    const txnId = searchParams.get('txn_id');

    if (!txnId) {
      // No txn_id in URL — fallback to legacy code param check
      const code = searchParams.get('code');
      setTimeout(() => {
        setResult({
          status: code === 'PAYMENT_SUCCESS' ? 'success' : 'failed',
          merchant_txn_id: searchParams.get('transactionId'),
          plan_name: null,
          amount_inr: null,
        });
      }, 1500);
      return;
    }

    // Poll backend for actual payment status (webhook may take a moment)
    let attempts = 0;
    const maxAttempts = 10;

    const checkStatus = async () => {
      try {
        const res = await api.get(`/payments/check/${txnId}`);
        const data = res.data;

        if (data.status === 'success') {
          setResult({
            status: 'success',
            merchant_txn_id: data.merchant_txn_id,
            plan_name: data.plan_name,
            amount_inr: data.amount_inr,
          });
          return; // stop polling
        }

        if (data.status === 'failed') {
          setResult({
            status: 'failed',
            merchant_txn_id: data.merchant_txn_id,
            plan_name: data.plan_name,
            amount_inr: data.amount_inr,
          });
          return; // stop polling
        }

        // Still "initiated" — webhook hasn't arrived yet, keep polling
        attempts++;
        if (attempts >= maxAttempts) {
          setResult({
            status: 'pending',
            merchant_txn_id: txnId,
            plan_name: null,
            amount_inr: null,
          });
          return;
        }

        setTimeout(checkStatus, 2000); // retry in 2s
      } catch {
        // API error — show pending status
        setResult({
          status: 'pending',
          merchant_txn_id: txnId,
          plan_name: null,
          amount_inr: null,
        });
      }
    };

    // Initial delay for webhook to arrive
    setTimeout(checkStatus, 1500);
  }, [searchParams]);

  const handleReturn = () => {
    const win = window as any;
    if (win.Telegram?.WebApp?.close) {
      win.Telegram.WebApp.close();
    } else {
      navigate('/user/dashboard');
    }
  };

  const amountDisplay = result.amount_inr
    ? `₹${(result.amount_inr / 100).toFixed(2)}`
    : null;

  return (
    <div className="min-h-screen bg-[#f4f7fa] flex items-center justify-center p-4">
      <div className="glass-card max-w-md w-full p-8 text-center animate-in zoom-in duration-500">

        {result.status === 'loading' && (
          <div className="flex flex-col items-center py-8">
            <Loader2 className="w-16 h-16 text-brand-500 animate-spin mb-6" />
            <h2 className="text-xl font-bold text-slate-800 mb-2">Verifying Payment...</h2>
            <p className="text-slate-500">Please wait while we confirm your transaction.</p>
          </div>
        )}

        {result.status === 'success' && (
          <div className="flex flex-col items-center py-8">
            <div className="w-20 h-20 bg-green-100 text-green-500 rounded-full flex items-center justify-center mb-6 animate-in zoom-in duration-300">
              <CheckCircle2 className="w-12 h-12" />
            </div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Payment Successful! 🎉</h2>
            <p className="text-slate-500 mb-6">
              {result.plan_name
                ? `Your ${result.plan_name} plan is now active!`
                : 'Your subscription has been activated.'}
            </p>

            {(amountDisplay || result.merchant_txn_id) && (
              <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 w-full mb-6 space-y-2">
                {amountDisplay && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Amount Paid</span>
                    <span className="font-semibold text-slate-700">{amountDisplay}</span>
                  </div>
                )}
                {result.merchant_txn_id && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Transaction ID</span>
                    <span className="font-mono text-xs text-slate-600 truncate max-w-[180px]">
                      {result.merchant_txn_id}
                    </span>
                  </div>
                )}
              </div>
            )}

            <button onClick={handleReturn} className="btn-primary w-full flex items-center justify-center">
              Return to Telegram <ArrowRight className="w-4 h-4 ml-2" />
            </button>
          </div>
        )}

        {result.status === 'failed' && (
          <div className="flex flex-col items-center py-8">
            <div className="w-20 h-20 bg-red-100 text-red-500 rounded-full flex items-center justify-center mb-6">
              <XCircle className="w-12 h-12" />
            </div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Payment Failed</h2>
            <p className="text-slate-500 mb-6">
              Your transaction could not be completed. No charges were made.
            </p>
            <button
              onClick={handleReturn}
              className="w-full px-6 py-3 bg-slate-800 hover:bg-slate-900 text-white font-semibold rounded-xl transition-all shadow-md flex items-center justify-center"
            >
              Close & Try Again <ArrowRight className="w-4 h-4 ml-2" />
            </button>
          </div>
        )}

        {result.status === 'pending' && (
          <div className="flex flex-col items-center py-8">
            <div className="w-20 h-20 bg-amber-100 text-amber-500 rounded-full flex items-center justify-center mb-6">
              <Clock className="w-12 h-12" />
            </div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">Payment Processing</h2>
            <p className="text-slate-500 mb-6">
              Your payment is being processed. You'll receive a confirmation message on Telegram once it's complete.
            </p>
            <button onClick={handleReturn} className="btn-primary w-full flex items-center justify-center">
              Return to Telegram <ArrowRight className="w-4 h-4 ml-2" />
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
