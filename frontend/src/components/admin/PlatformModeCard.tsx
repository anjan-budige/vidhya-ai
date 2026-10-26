import { useEffect, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';

type Mode = 'paid' | 'free';

interface PlanLite {
  id: string;
  name: string;
  display_name: string;
  price_inr: number;
}

interface PlatformStatus {
  platform_mode: Mode;
  mode_changed_at: string | null;
  free_plan: { display_name: string; limits: Record<string, any> } | null;
  active_paid_plans: PlanLite[];
  active_paid_subscribers: number;
  subscribers_by_plan: Record<string, number>;
  pending_payments: number;
}

export default function PlatformModeCard() {
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [role, setRole] = useState<string>('');
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(1);
  const [cancelPending, setCancelPending] = useState(false);
  const [ack, setAck] = useState(false);
  const [reactivate, setReactivate] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = async () => {
    try {
      const res = await api.get('/admin/platform/status');
      setStatus(res.data);
    } catch {
      // Non-superadmins may not be allowed to read status on older deployments.
    }
  };

  useEffect(() => {
    load();
    api
      .get('/auth/admin/me')
      .then((res) => setRole(res.data.role))
      .catch(() => {});
  }, []);

  const isSuperadmin = role === 'superadmin';
  const isFree = status?.platform_mode === 'free';
  const limits = status?.free_plan?.limits || {};

  const closeModal = () => {
    setOpen(false);
    setStep(1);
    setCancelPending(false);
    setAck(false);
    setReactivate(true);
  };

  const switchMode = async () => {
    if (!status) return;
    setSaving(true);
    try {
      if (isFree) {
        await api.post('/admin/platform/mode', {
          mode: 'paid',
          reactivate_plans: reactivate,
        });
        toast.success('Platform switched to Paid mode.');
      } else {
        await api.post('/admin/platform/mode', {
          mode: 'free',
          deactivate_plans: true,
          cancel_pending_payments: cancelPending,
        });
        toast.success('Platform switched to Free mode.');
      }
      closeModal();
      await load();
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Failed to switch platform mode.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <div className="glass-card p-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <h3 className="text-lg font-bold text-slate-800">Billing Mode</h3>
              <span
                className={`inline-flex px-2 py-0.5 rounded-full text-xs font-semibold border ${
                  isFree
                    ? 'bg-amber-50 text-amber-700 border-amber-200'
                    : 'bg-green-50 text-green-700 border-green-200'
                }`}
              >
                {isFree ? 'Free mode' : 'Paid mode'}
              </span>
            </div>
            <p className="text-sm text-slate-500">
              {isFree
                ? `Every user has the same access. Limits come from the free plan${
                    status?.free_plan ? ` (${status.free_plan.display_name})` : ''
                  }.`
                : 'Users can buy plans. Payments, upgrades and plan assignment are enabled.'}
            </p>
            {isFree && (
              <p className="text-xs text-slate-400 mt-2">
                {limits.messages_per_day === -1 ? 'Unlimited' : limits.messages_per_day} messages/day ·{' '}
                {limits.messages_per_month === -1 ? 'Unlimited' : limits.messages_per_month} messages/month ·{' '}
                {limits.max_sessions === -1 ? 'Unlimited' : limits.max_sessions} sessions
              </p>
            )}
          </div>

          {isSuperadmin && status && (
            <div className="flex shrink-0 flex-col items-end gap-1">
              <div className="inline-flex rounded-lg border border-line bg-canvas p-1">
                <button
                  type="button"
                  onClick={() => { if (isFree) setOpen(true); }}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    !isFree ? 'bg-brand-500 text-white shadow-sm' : 'text-muted hover:text-ink'
                  }`}
                >
                  Paid
                </button>
                <button
                  type="button"
                  onClick={() => { if (!isFree) setOpen(true); }}
                  className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                    isFree ? 'bg-warning text-white shadow-sm' : 'text-muted hover:text-ink'
                  }`}
                >
                  Free
                </button>
              </div>
              <span className="text-[10px] text-muted">Select the other mode to switch</span>
            </div>
          )}
        </div>
      </div>

      {open && status && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg overflow-hidden">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center">
              <h2 className="text-lg font-bold text-slate-800">
                {isFree
                  ? 'Switch to Paid mode'
                  : `Switch to Free mode · Step ${step} of 2`}
              </h2>
              <button onClick={closeModal} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {isFree ? (
                <>
                  <p className="text-sm text-slate-600">
                    Paid plans must be active before payments can work again. Previously
                    deactivated paid plans can be restored now.
                  </p>
                  <label className="flex items-start gap-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={reactivate}
                      onChange={(e) => setReactivate(e.target.checked)}
                      className="mt-0.5"
                    />
                    Reactivate all deactivated paid plans
                  </label>
                  <p className="text-xs text-slate-500">
                    Users are not restored to old paid plans — they will need to subscribe again.
                  </p>
                </>
              ) : step === 1 ? (
                <>
                  <p className="text-sm text-slate-600">
                    All paid plans must be deactivated. They stay in the database and can be
                    restored when you switch back.
                  </p>
                  {status.active_paid_plans.length === 0 ? (
                    <p className="text-sm text-slate-500">No paid plan is currently active.</p>
                  ) : (
                    <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
                      {status.active_paid_plans.map((p) => (
                        <li key={p.id} className="flex justify-between px-4 py-2.5 text-sm">
                          <span className="text-slate-700">{p.display_name}</span>
                          <span className="text-slate-500">₹{p.price_inr}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                  <p className="text-xs text-slate-500">
                    These plans will be deactivated when you confirm the switch.
                  </p>
                </>
              ) : (
                <>
                  <p className="text-sm text-slate-600">
                    {status.active_paid_subscribers > 0 ? (
                      <>
                        <strong>{status.active_paid_subscribers}</strong> user(s) have an active paid
                        subscription. They will be moved to the free plan and get{' '}
                        <strong>only free limits</strong>.
                      </>
                    ) : (
                      'No user currently has a paid subscription.'
                    )}
                  </p>

                  {Object.keys(status.subscribers_by_plan).length > 0 && (
                    <ul className="text-sm text-slate-600 space-y-1">
                      {Object.entries(status.subscribers_by_plan).map(([name, count]) => (
                        <li key={name}>
                          {name} → Free: <strong>{count}</strong> user(s)
                        </li>
                      ))}
                    </ul>
                  )}

                  {status.pending_payments > 0 && (
                    <div className="rounded-xl border border-amber-200 bg-amber-50 p-3">
                      <p className="text-sm text-amber-800">
                        {status.pending_payments} payment(s) are still pending.
                      </p>
                      <label className="flex items-center gap-2 text-sm text-amber-800 mt-2">
                        <input
                          type="checkbox"
                          checked={cancelPending}
                          onChange={(e) => setCancelPending(e.target.checked)}
                        />
                        Cancel pending payments
                      </label>
                    </div>
                  )}

                  <label className="flex items-start gap-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={ack}
                      onChange={(e) => setAck(e.target.checked)}
                      className="mt-0.5"
                    />
                    I understand that paid subscriptions will be closed and switching back will
                    not restore them.
                  </label>
                </>
              )}
            </div>

            <div className="px-6 py-4 bg-slate-50 flex justify-end gap-3">
              <button
                onClick={closeModal}
                className="px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100 rounded-xl"
              >
                Cancel
              </button>
              {isFree ? (
                <button
                  onClick={switchMode}
                  disabled={saving}
                  className="btn-primary px-5 py-2 rounded-xl text-sm flex items-center disabled:opacity-50"
                >
                  {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Enable Paid mode
                </button>
              ) : step === 1 ? (
                <button
                  onClick={() => setStep(2)}
                  className="btn-primary px-5 py-2 rounded-xl text-sm"
                >
                  Continue
                </button>
              ) : (
                <button
                  onClick={switchMode}
                  disabled={saving || !ack || (status.pending_payments > 0 && !cancelPending)}
                  className="btn-primary px-5 py-2 rounded-xl text-sm flex items-center disabled:opacity-50"
                >
                  {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
                  Switch to Free mode
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
