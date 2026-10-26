import { useState, useEffect } from 'react';
import { CreditCard, Edit, Plus, Check, X, Save, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';
import FreeModeBanner from '../../components/admin/FreeModeBanner';
import { usePlatformConfig } from '../../hooks/usePlatformConfig';
import { Badge } from '../../components/ui/Badge';

export default function AdminPlans() {
  const { freeMode } = usePlatformConfig();
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingPlan, setEditingPlan] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  const [aiDefaults, setAiDefaults] = useState<any>(null);

  const fetchPlans = async () => {
    try {
      const response = await api.get('/plans/all');
      setPlans(response.data);
    } catch (err) {
      toast.error('Failed to fetch plans');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchPlans();
    api
      .get('/admin/ai/defaults')
      .then((res) => setAiDefaults(res.data))
      .catch(() => {});
  }, []);

  const handleEditClick = (plan: any) => {
    setEditingPlan({ ...plan });
  };

  const handleCreateClick = () => {
    setEditingPlan({
      display_name: '',
      name: '',
      price_inr: 0,
      validity_days: 30,
      messages_per_day: 5,
      messages_per_month: 50,
      max_context_tokens: 2000,
      max_response_tokens: 512,
      max_sessions: 10
    });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPlan) return;

    const contextTokens = parseInt(editingPlan.max_context_tokens);
    const responseTokens = parseInt(editingPlan.max_response_tokens);
    const window = aiDefaults?.chat?.context_window;
    const maxOutput = aiDefaults?.chat?.max_output_tokens;

    if (maxOutput && responseTokens > maxOutput) {
      toast.error(
        `Max output is ${maxOutput} tokens for ${aiDefaults.chat.model}. Lower the plan's output limit.`
      );
      return;
    }

    if (window && contextTokens + responseTokens + 128 > window) {
      toast.error(
        `Max input is ${Math.max(0, window - responseTokens - 128)} tokens for ${aiDefaults.chat.model} (${window} window).`
      );
      return;
    }

    setSaving(true);
    try {
      const payload = {
        display_name: editingPlan.display_name,
        price_inr: parseInt(editingPlan.price_inr),
        messages_per_day: parseInt(editingPlan.messages_per_day),
        messages_per_month: parseInt(editingPlan.messages_per_month),
        max_context_tokens: parseInt(editingPlan.max_context_tokens),
        max_response_tokens: parseInt(editingPlan.max_response_tokens),
        max_sessions: parseInt(editingPlan.max_sessions)
      };

      if (editingPlan.id) {
        await api.put(`/plans/${editingPlan.id}`, payload);
        toast.success('Plan updated successfully');
      } else {
        await api.post('/plans/', {
          ...payload,
          name: editingPlan.name,
          validity_days: parseInt(editingPlan.validity_days)
        });
        toast.success('Plan created successfully');
      }
      
      setEditingPlan(null);
      await fetchPlans(); // Refresh data
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update plan');
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteClick = async (plan: any) => {
    if (plan.name === 'free') {
      toast.error('Cannot delete the default free plan');
      return;
    }
    if (!window.confirm(`Are you sure you want to permanently delete the ${plan.display_name} plan?`)) return;
    
    try {
      await api.delete(`/plans/${plan.id}`);
      toast.success('Plan deleted successfully');
      await fetchPlans();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to delete plan');
    }
  };

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-600">Monetization</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">Subscription plans</h1>
          <p className="mt-1 text-sm text-muted">
            {freeMode
              ? 'Free mode — the free plan applies to every user.'
              : 'Pricing tiers, quotas and AI context limits.'}
          </p>
        </div>
        <button
          onClick={handleCreateClick}
          disabled={freeMode}
          title={freeMode ? 'Plan creation is disabled in Free mode' : undefined}
          className="btn-primary gap-2 disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="h-4 w-4" /> Create plan
        </button>
      </div>

      {aiDefaults?.chat && (
        <div className="card flex flex-col gap-1 border-brand-100 bg-brand-50/40 p-4 text-xs sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="font-semibold text-ink">Active chat model: {aiDefaults.chat.model}</p>
            <p className="text-muted">
              Plans must fit inside {aiDefaults.chat.context_window.toLocaleString()} context and{' '}
              {aiDefaults.chat.max_output_tokens.toLocaleString()} max output tokens.
            </p>
          </div>
          <Badge tone="brand">model limits</Badge>
        </div>
      )}

      {freeMode && <FreeModeBanner message="Free mode — plan creation is disabled." />}

      {loading ? (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-80 animate-pulse rounded-xl bg-surface" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 xl:grid-cols-3">
          {plans.map((plan) => {
            const highlight = plan.name === 'pro' || plan.name === 'premium';
            return (
              <div
                key={plan.id}
                className={`card card-hover group relative overflow-hidden p-6 ${
                  highlight ? 'ring-1 ring-brand-200' : ''
                }`}
              >
                <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${highlight ? 'from-brand-400 to-brand-600' : 'from-line to-line'}`} />
                {plan.name === 'pro' && (
                  <span className="absolute right-4 top-4 rounded-full bg-brand-500 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-white shadow-md shadow-brand-500/30">
                    Popular
                  </span>
                )}
                <div className="flex items-start gap-3">
                  <span className={`flex h-11 w-11 items-center justify-center rounded-xl ring-1 ${highlight ? 'bg-brand-50 text-brand-600 ring-brand-100' : 'bg-canvas text-muted ring-line'}`}>
                    <CreditCard className="h-5 w-5" />
                  </span>
                  <div>
                    <h2 className="text-base font-semibold text-ink">{plan.display_name}</h2>
                    <p className="text-xs text-muted">{plan.name === 'free' ? 'Default tier' : `Billed every ${plan.validity_days} days`}</p>
                  </div>
                </div>

                <div className="mt-5 flex items-end gap-1">
                  <span className="text-3xl font-bold tracking-tight text-ink">₹{plan.price_inr}</span>
                  <span className="pb-1 text-xs text-muted">/ {plan.validity_days} days</span>
                </div>

                <div className="mt-5 space-y-2.5 border-t border-line pt-4">
                  {[
                    `${plan.messages_per_day === -1 ? 'Unlimited' : plan.messages_per_day.toLocaleString()} messages / day`,
                    `${plan.messages_per_month === -1 ? 'Unlimited' : plan.messages_per_month.toLocaleString()} messages / month`,
                    `${plan.max_sessions === -1 ? 'Unlimited' : plan.max_sessions} saved sessions`,
                    `${plan.max_context_tokens.toLocaleString()} input · ${plan.max_response_tokens.toLocaleString()} output tokens`,
                  ].map((feature) => (
                    <div key={feature} className="flex items-center gap-2 text-xs text-muted">
                      <Check className="h-3.5 w-3.5 shrink-0 text-success" />
                      <span>{feature}</span>
                    </div>
                  ))}
                </div>

                {aiDefaults?.chat &&
                  (plan.max_response_tokens > aiDefaults.chat.max_output_tokens ||
                    plan.max_context_tokens + plan.max_response_tokens + 128 >
                      aiDefaults.chat.context_window) && (
                    <p className="mt-3 rounded-md bg-danger-soft px-2.5 py-1.5 text-[11px] font-medium text-danger">
                      Exceeds the active chat model's limits — adjust this plan or the model.
                    </p>
                  )}

                <div className="mt-5 flex gap-2">
                  <button
                    onClick={() => handleEditClick(plan)}
                    disabled={freeMode && plan.name !== 'free'}
                    className="btn-outline flex-1 gap-1.5 py-2 text-xs disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <Edit className="h-3.5 w-3.5" /> Edit
                  </button>
                  {plan.name !== 'free' && !freeMode && (
                    <button
                      onClick={() => handleDeleteClick(plan)}
                      className="rounded-lg border border-line p-2 text-muted transition-colors hover:border-red-200 hover:bg-danger-soft hover:text-danger"
                      title="Delete plan"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {editingPlan && (
        <div className="fixed inset-0 bg-ink/40 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-surface border border-line rounded-xl shadow-xl w-full max-w-lg overflow-y-auto max-h-[90vh]">
            <div className="p-5 border-b border-line flex justify-between items-center">
              <h2 className="text-lg font-semibold text-ink">{editingPlan.id ? `Edit ${editingPlan.display_name}` : 'Create New Plan'}</h2>
              <button onClick={() => setEditingPlan(null)} className="text-muted hover:text-ink">
                <X className="w-6 h-6" />
              </button>
            </div>
            
            <form onSubmit={handleSave} className="p-6 space-y-4">
              <div>
                <label className="input-label">Display Name</label>
                <input 
                  type="text" 
                  value={editingPlan.display_name}
                  onChange={(e) => setEditingPlan({...editingPlan, display_name: e.target.value})}
                  className="input-field"
                  required
                />
              </div>

              {!editingPlan.id && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="input-label">Internal Name</label>
                    <input 
                      type="text" 
                      value={editingPlan.name}
                      onChange={(e) => setEditingPlan({...editingPlan, name: e.target.value.toLowerCase().replace(/[^a-z_]/g, '')})}
                      className="input-field"
                      placeholder="e.g. basic_plus"
                      required
                    />
                  </div>
                  <div>
                    <label className="input-label">Validity (Days)</label>
                    <input 
                      type="number" 
                      value={editingPlan.validity_days}
                      onChange={(e) => setEditingPlan({...editingPlan, validity_days: e.target.value})}
                      className="input-field"
                      min="1"
                      required
                    />
                  </div>
                </div>
              )}
              
              <div>
                <label className="input-label">Price (INR)</label>
                <input 
                  type="number" 
                  value={editingPlan.price_inr}
                  onChange={(e) => setEditingPlan({...editingPlan, price_inr: e.target.value})}
                  className="input-field"
                  min="0"
                  required
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <label className="input-label">Messages/Day</label>
                  <input
                    type="number"
                    value={editingPlan.messages_per_day}
                    onChange={(e) => setEditingPlan({...editingPlan, messages_per_day: e.target.value})}
                    className="input-field"
                    min="-1"
                    required
                  />
                  <p className="mt-1 text-xs text-muted">-1 for unlimited</p>
                </div>

                <div>
                  <label className="input-label">Messages/Month</label>
                  <input 
                    type="number" 
                    value={editingPlan.messages_per_month}
                    onChange={(e) => setEditingPlan({...editingPlan, messages_per_month: e.target.value})}
                    className="input-field"
                    min="-1"
                    required
                  />
                  <p className="mt-1 text-xs text-muted">-1 for unlimited</p>
                </div>
                
                <div>
                  <label className="input-label">Max Sessions</label>
                  <input 
                    type="number" 
                    value={editingPlan.max_sessions}
                    onChange={(e) => setEditingPlan({...editingPlan, max_sessions: e.target.value})}
                    className="input-field"
                    min="-1"
                    required
                  />
                  <p className="mt-1 text-xs text-muted">Saved chats per user (-1 for unlimited)</p>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="input-label">Input Context Tokens</label>
                  <input 
                    type="number" 
                    value={editingPlan.max_context_tokens || 2000}
                    onChange={(e) => setEditingPlan({...editingPlan, max_context_tokens: e.target.value})}
                    className="input-field"
                    min="500"
                    required
                  />
                  <p className="mt-1 text-xs text-muted">
                    Maximum input tokens sent to the model per request.
                  </p>
                </div>
                
                <div>
                  <label className="input-label">Max Output Tokens</label>
                  <input 
                    type="number" 
                    value={editingPlan.max_response_tokens}
                    onChange={(e) => setEditingPlan({...editingPlan, max_response_tokens: e.target.value})}
                    className="input-field"
                    min="128"
                    required
                  />
                  <p className="mt-1 text-xs text-muted">Max tokens AI can generate per reply.</p>
                </div>
              </div>



              <div className="pt-4 flex justify-end space-x-3">
                <button 
                  type="button"
                  onClick={() => setEditingPlan(null)}
                  className="btn-ghost"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={saving}
                  className="btn-primary flex items-center"
                >
                  {saving ? (
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" /> Save Changes
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
