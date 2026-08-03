import { useState, useEffect } from 'react';
import { CreditCard, Edit, Plus, Check, X, Save, Trash2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';

export default function AdminPlans() {
  const [plans, setPlans] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingPlan, setEditingPlan] = useState<any>(null);
  const [saving, setSaving] = useState(false);

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
      messages_per_month: 50,
      max_context_tokens: 2000,
      max_response_tokens: 512,
      max_conversations: 10,
      max_active_conversations: 2
    });
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingPlan) return;
    
    setSaving(true);
    try {
      const payload = {
        display_name: editingPlan.display_name,
        price_inr: parseInt(editingPlan.price_inr),
        messages_per_month: parseInt(editingPlan.messages_per_month),
        max_context_tokens: parseInt(editingPlan.max_context_tokens),
        max_response_tokens: parseInt(editingPlan.max_response_tokens),
        max_conversations: parseInt(editingPlan.max_conversations),
        max_active_conversations: parseInt(editingPlan.max_active_conversations)
      };

      if (editingPlan.id) {
        // Update existing
        await api.put(`/plans/${editingPlan.id}`, payload);
        toast.success('Plan updated successfully');
      } else {
        // Create new
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
    <div className="flex flex-col h-full max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Subscription Plans</h1>
          <p className="text-sm text-slate-500">Manage pricing tiers and limits.</p>
        </div>
        <button onClick={handleCreateClick} className="btn-primary flex items-center">
          <Plus className="w-4 h-4 mr-2" /> Create New Plan
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="w-10 h-10 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin"></div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {plans.map((plan) => (
            <div key={plan.id} className={`glass-card p-8 relative ${plan.name === 'pro' ? 'border-brand-500 shadow-md ring-1 ring-brand-500' : ''}`}>
              {plan.name === 'pro' && (
                <div className="absolute top-0 left-1/2 -translate-x-1/2 -translate-y-1/2 bg-brand-500 text-white text-xs font-bold px-3 py-1 rounded-full uppercase tracking-wider shadow-sm">
                  Most Popular
                </div>
              )}
              <div className="flex justify-between items-start mb-4">
                <h2 className="text-xl font-bold text-slate-800">{plan.display_name}</h2>
                <div className="p-2 bg-slate-50 rounded-lg text-slate-400">
                  <CreditCard className="w-5 h-5" />
                </div>
              </div>
              
              <div className="mb-6">
                <span className="text-4xl font-extrabold text-slate-900">₹{plan.price_inr}</span>
                <span className="text-slate-500 font-medium">/{plan.validity_days} days</span>
              </div>

              <div className="space-y-3 mb-8">
                <div className="flex items-center text-sm text-slate-600">
                  <Check className="w-4 h-4 text-green-500 mr-3 shrink-0" />
                  <span className="font-medium text-slate-800">{plan.messages_per_month === -1 ? 'Unlimited' : plan.messages_per_month}</span> &nbsp;Messages/month
                </div>
                <div className="flex items-center text-sm text-slate-600">
                  <Check className="w-4 h-4 text-green-500 mr-3 shrink-0" />
                  <span className="font-medium text-slate-800">{plan.max_response_tokens}</span> &nbsp;Max Output Tokens
                </div>
                <div className="flex items-center text-sm text-slate-600">
                  <Check className="w-4 h-4 text-green-500 mr-3 shrink-0" />
                  <span className="font-medium text-slate-800">{plan.max_conversations}</span> &nbsp;Total Conversations
                </div>
              </div>

              <div className="flex space-x-3">
                <button 
                  onClick={() => handleEditClick(plan)}
                  className="flex-1 py-2.5 rounded-xl border-2 border-slate-200 text-slate-600 font-medium hover:border-brand-500 hover:text-brand-600 transition-colors flex justify-center items-center"
                >
                  <Edit className="w-4 h-4 mr-2" /> Edit Plan
                </button>
                {plan.name !== 'free' && (
                  <button 
                    onClick={() => handleDeleteClick(plan)}
                    className="p-2.5 rounded-xl border-2 border-slate-200 text-slate-400 hover:border-red-500 hover:text-red-500 hover:bg-red-50 transition-colors flex justify-center items-center"
                    title="Delete Plan"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Edit Modal */}
      {editingPlan && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center">
              <h2 className="text-xl font-bold text-slate-800">{editingPlan.id ? `Edit ${editingPlan.display_name}` : 'Create New Plan'}</h2>
              <button onClick={() => setEditingPlan(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-6 h-6" />
              </button>
            </div>
            
            <form onSubmit={handleSave} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Display Name</label>
                <input 
                  type="text" 
                  value={editingPlan.display_name}
                  onChange={(e) => setEditingPlan({...editingPlan, display_name: e.target.value})}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
                  required
                />
              </div>

              {!editingPlan.id && (
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Internal Name</label>
                    <input 
                      type="text" 
                      value={editingPlan.name}
                      onChange={(e) => setEditingPlan({...editingPlan, name: e.target.value.toLowerCase().replace(/[^a-z_]/g, '')})}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
                      placeholder="e.g. basic_plus"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Validity (Days)</label>
                    <input 
                      type="number" 
                      value={editingPlan.validity_days}
                      onChange={(e) => setEditingPlan({...editingPlan, validity_days: e.target.value})}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
                      min="1"
                      required
                    />
                  </div>
                </div>
              )}
              
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Price (INR)</label>
                <input 
                  type="number" 
                  value={editingPlan.price_inr}
                  onChange={(e) => setEditingPlan({...editingPlan, price_inr: e.target.value})}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
                  min="0"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Messages/Month</label>
                  <input 
                    type="number" 
                    value={editingPlan.messages_per_month}
                    onChange={(e) => setEditingPlan({...editingPlan, messages_per_month: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
                    min="-1"
                    required
                  />
                  <p className="text-xs text-slate-500 mt-1">-1 for unlimited</p>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Total Conversations</label>
                  <input 
                    type="number" 
                    value={editingPlan.max_conversations}
                    onChange={(e) => setEditingPlan({...editingPlan, max_conversations: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
                    min="-1"
                    required
                  />
                  <p className="text-xs text-slate-500 mt-1">Lifetime limit (-1 for unlimited)</p>
                </div>
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Input Context Tokens</label>
                  <input 
                    type="number" 
                    value={editingPlan.max_context_tokens || 2000}
                    onChange={(e) => setEditingPlan({...editingPlan, max_context_tokens: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
                    min="500"
                    required
                  />
                  <p className="text-xs text-slate-500 mt-1">Max tokens AI remembers from history.</p>
                </div>
                
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Max Output Tokens</label>
                  <input 
                    type="number" 
                    value={editingPlan.max_response_tokens}
                    onChange={(e) => setEditingPlan({...editingPlan, max_response_tokens: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
                    min="128"
                    required
                  />
                  <p className="text-xs text-slate-500 mt-1">Max tokens AI can generate per reply.</p>
                </div>
              </div>


              <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Max Active Conversations</label>
                  <input 
                    type="number" 
                    value={editingPlan.max_active_conversations}
                    onChange={(e) => setEditingPlan({...editingPlan, max_active_conversations: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none"
                    min="1"
                    required
                  />
                  <p className="text-xs text-slate-500 mt-1">Concurrent open threads allowed.</p>
                </div>

              <div className="pt-4 flex justify-end space-x-3">
                <button 
                  type="button"
                  onClick={() => setEditingPlan(null)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-xl font-medium transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={saving}
                  className="btn-primary px-6 py-2 rounded-xl flex items-center"
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
