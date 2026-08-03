import { useState, useEffect, useRef } from 'react';
import { Search, Filter, MoreVertical, Ban, CheckCircle, ShieldAlert, ShieldCheck, CreditCard, X, Save } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';

export default function AdminUsers() {
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeDropdown, setActiveDropdown] = useState<string | null>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [assigningUser, setAssigningUser] = useState<any | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [assigning, setAssigning] = useState(false);
  const [viewingUserId, setViewingUserId] = useState<string | null>(null);
  const [userDetails, setUserDetails] = useState<any | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);
  
  // Close dropdown when clicking outside
  const dropdownRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setActiveDropdown(null);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchUsers = async () => {
    try {
      const response = await api.get('/users/', { params: { search: search || undefined } });
      setUsers(response.data);
    } catch (err) {
      toast.error('Failed to fetch users');
    } finally {
      setLoading(false);
    }
  };

  const fetchPlans = async () => {
    try {
      const response = await api.get('/plans/');
      setPlans(response.data);
      if (response.data.length > 0) {
        setSelectedPlanId(response.data[0].id);
      }
    } catch (err) {
      console.error('Failed to fetch plans', err);
    }
  };

  useEffect(() => {
    fetchUsers();
    fetchPlans();
  }, [search]); // Re-fetch on search change

  const fetchUserDetails = async (userId: string) => {
    setViewingUserId(userId);
    setLoadingDetails(true);
    try {
      const response = await api.get(`/users/${userId}/details`);
      setUserDetails(response.data);
    } catch (err) {
      toast.error('Failed to fetch user details');
      setViewingUserId(null);
    } finally {
      setLoadingDetails(false);
    }
  };

  const toggleStatus = async (user: any) => {
    setActiveDropdown(null);
    const action = user.is_banned ? 'unban' : 'Violation of Terms of Service';
    const confirmMsg = user.is_banned 
      ? `Are you sure you want to unban ${user.first_name}?` 
      : `Are you sure you want to ban ${user.first_name}?`;

    if (!window.confirm(confirmMsg)) return;

    try {
      await api.put(`/users/${user.id}/status`, { reason: action });
      toast.success(`User ${user.is_banned ? 'unbanned' : 'banned'} successfully`);
      await fetchUsers(); // Refresh
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to update user status');
    }
  };

  const handleAssignPlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!assigningUser || !selectedPlanId) return;

    setAssigning(true);
    try {
      await api.post('/subscriptions/admin/assign', {
        user_id: assigningUser.id,
        plan_id: selectedPlanId
      });
      toast.success(`Plan assigned to ${assigningUser.first_name} successfully`);
      setAssigningUser(null);
      fetchUsers(); // Refresh to show new plan badge
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to assign plan');
    } finally {
      setAssigning(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-2 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">User Management</h1>
          <p className="text-sm text-slate-500">View and manage all registered Telegram users.</p>
        </div>
        
        <div className="flex flex-wrap sm:flex-nowrap items-center gap-4 w-full sm:w-auto">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 h-4 w-4" />
            <input 
              type="text" 
              placeholder="Search users..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 bg-white rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-sm w-64"
            />
          </div>
          <button className="flex items-center text-sm bg-white border border-slate-200 px-4 py-2 rounded-xl hover:bg-slate-50 font-medium text-slate-600 shadow-sm transition-colors">
            <Filter className="h-4 w-4 mr-2" /> Filter
          </button>
        </div>
      </div>

      <div className="glass-card overflow-visible">
        {loading ? (
          <div className="p-12 flex flex-col items-center justify-center text-slate-400">
            <div className="w-10 h-10 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin mb-4"></div>
            Loading user database...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[800px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">User</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Telegram ID</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Plan</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Status</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Join Date</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-slate-500">No users found.</td>
                  </tr>
                ) : users.map((user) => (
                  <tr key={user.id} className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
                    <td className="py-4 px-6">
                      <div className="flex items-center">
                        <div className="w-10 h-10 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center font-bold mr-3">
                          {user.first_name.charAt(0)}
                        </div>
                        <div>
                          <p className="font-medium text-slate-800">{user.first_name} {user.last_name || ''}</p>
                          <p className="text-xs text-slate-500">@{user.telegram_username || 'unknown'}</p>
                        </div>
                      </div>
                    </td>
                    <td className="py-4 px-6 text-sm text-slate-600 font-mono">
                      {user.telegram_id}
                    </td>
                    <td className="py-4 px-6">
                      <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium border uppercase ${
                        user.current_plan === 'pro' || user.current_plan === 'enterprise' 
                          ? 'bg-purple-50 text-purple-700 border-purple-200'
                          : 'bg-slate-100 text-slate-600 border-slate-200'
                      }`}>
                        {user.current_plan}
                      </span>
                    </td>
                    <td className="py-4 px-6">
                      {!user.is_banned ? (
                        <span className="inline-flex items-center text-green-600 text-sm font-medium">
                          <CheckCircle className="w-4 h-4 mr-1.5" /> Active
                        </span>
                      ) : (
                        <span className="inline-flex items-center text-red-600 text-sm font-medium">
                          <Ban className="w-4 h-4 mr-1.5" /> Banned
                        </span>
                      )}
                    </td>
                    <td className="py-4 px-6 text-sm text-slate-500">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="py-4 px-6 text-right relative whitespace-nowrap">
                      <button 
                        onClick={() => fetchUserDetails(user.id)}
                        className="text-brand-600 hover:text-brand-800 transition-colors p-2 bg-brand-50 rounded-lg mr-2 inline-flex items-center text-xs font-medium"
                      >
                        Details
                      </button>
                      <button 
                        onClick={() => setActiveDropdown(activeDropdown === user.id ? null : user.id)}
                        onMouseDown={(e) => e.stopPropagation()}
                        className="text-slate-400 hover:text-brand-600 transition-colors p-2"
                      >
                        <MoreVertical className="w-5 h-5" />
                      </button>
                      
                      {activeDropdown === user.id && (
                        <div ref={dropdownRef} className="absolute right-8 top-10 w-48 bg-white rounded-xl shadow-lg border border-slate-100 z-50 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                          <div className="py-1">
                            <button 
                              onClick={() => {
                                setActiveDropdown(null);
                                setAssigningUser(user);
                              }}
                              className="w-full text-left px-4 py-3 text-sm flex items-center text-slate-700 hover:bg-slate-50 transition-colors border-b border-slate-100"
                            >
                              <CreditCard className="w-4 h-4 mr-2 text-brand-500" /> Assign Plan
                            </button>
                            <button 
                              onClick={() => toggleStatus(user)}
                              className={`w-full text-left px-4 py-3 text-sm flex items-center transition-colors ${
                                user.is_banned 
                                  ? 'text-green-600 hover:bg-green-50' 
                                  : 'text-red-600 hover:bg-red-50'
                              }`}
                            >
                              {user.is_banned ? (
                                <><ShieldCheck className="w-4 h-4 mr-2" /> Unban User</>
                              ) : (
                                <><ShieldAlert className="w-4 h-4 mr-2" /> Ban User</>
                              )}
                            </button>
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Assign Plan Modal */}
      {assigningUser && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center">
              <h2 className="text-xl font-bold text-slate-800">Assign Plan to {assigningUser.first_name}</h2>
              <button onClick={() => setAssigningUser(null)} className="text-slate-400 hover:text-slate-600">
                <X className="w-6 h-6" />
              </button>
            </div>
            
            <form onSubmit={handleAssignPlan} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Select Subscription Plan</label>
                <select 
                  value={selectedPlanId}
                  onChange={(e) => setSelectedPlanId(e.target.value)}
                  className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 outline-none bg-white"
                  required
                >
                  {plans.map(p => (
                    <option key={p.id} value={p.id}>{p.display_name} ({p.name})</option>
                  ))}
                </select>
                <p className="text-xs text-slate-500 mt-2">
                  This will immediately override any existing subscription this user has and provision them with the selected plan.
                </p>
              </div>
              
              <div className="pt-4 flex justify-end space-x-3">
                <button 
                  type="button"
                  onClick={() => setAssigningUser(null)}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-xl font-medium transition-colors"
                >
                  Cancel
                </button>
                <button 
                  type="submit"
                  disabled={assigning}
                  className="btn-primary px-6 py-2 rounded-xl flex items-center"
                >
                  {assigning ? (
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" /> Assign Now
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* User Details Modal */}
      {viewingUserId && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-200">
            <div className="p-6 border-b border-slate-100 flex justify-between items-center bg-slate-50">
              <h2 className="text-xl font-bold text-slate-800">User Details</h2>
              <button onClick={() => { setViewingUserId(null); setUserDetails(null); }} className="text-slate-400 hover:text-slate-600">
                <X className="w-6 h-6" />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1">
              {loadingDetails ? (
                <div className="flex justify-center items-center h-32">
                  <div className="w-8 h-8 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin"></div>
                </div>
              ) : userDetails ? (
                <div className="space-y-8">
                  {/* Profile Block */}
                  <div className="flex items-center space-x-4">
                    <div className="w-16 h-16 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center font-bold text-2xl">
                      {userDetails.first_name.charAt(0)}
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-slate-800">{userDetails.first_name} {userDetails.last_name || ''}</h3>
                      <p className="text-slate-500">@{userDetails.telegram_username || 'unknown'} • ID: <span className="font-mono text-slate-600">{userDetails.telegram_id}</span></p>
                      <p className="text-xs text-slate-400 mt-1">Joined: {new Date(userDetails.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>

                  {/* Stats Grid */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                      <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Plan Usage</div>
                      <div className="text-2xl font-bold text-slate-800">
                        {userDetails.subscription?.monthly_messages_used || 0} <span className="text-sm font-normal text-slate-500">/ {userDetails.subscription?.monthly_messages_limit > 0 ? userDetails.subscription.monthly_messages_limit : '∞'} msgs</span>
                      </div>
                      <div className="text-sm text-brand-600 font-medium mt-1 uppercase">{userDetails.subscription?.plan_name}</div>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                      <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Validity</div>
                      <div className="text-2xl font-bold text-slate-800">
                        {userDetails.subscription?.current_period_end 
                          ? `${Math.max(0, Math.floor((new Date(userDetails.subscription.current_period_end).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))} Days`
                          : (userDetails.subscription?.validity_days ? `${userDetails.subscription.validity_days} Days` : 'Lifetime')}
                      </div>
                      <div className="text-sm text-slate-500 mt-1">
                        {userDetails.subscription?.current_period_end 
                          ? `Expires: ${new Date(userDetails.subscription.current_period_end).toLocaleDateString()}` 
                          : 'No expiration'}
                      </div>
                    </div>
                    <div className="bg-slate-50 p-4 rounded-xl border border-slate-100">
                      <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Conversations</div>
                      <div className="text-2xl font-bold text-slate-800">{userDetails.conversations_count}</div>
                      <div className="text-sm text-slate-500 mt-1">Total Active Chats</div>
                    </div>
                  </div>

                  {/* Conversations History */}
                  <div>
                    <h4 className="text-md font-bold text-slate-800 mb-3 flex items-center">
                      <Search className="w-4 h-4 mr-2 text-brand-500" /> Conversations List
                    </h4>
                    {!userDetails.conversations || userDetails.conversations.length === 0 ? (
                      <div className="p-4 bg-slate-50 rounded-lg text-slate-500 text-sm text-center">No conversations found.</div>
                    ) : (
                      <div className="border border-slate-200 rounded-xl overflow-hidden max-h-60 overflow-y-auto">
                        <table className="w-full text-left text-sm">
                          <thead className="bg-slate-50 sticky top-0">
                            <tr>
                              <th className="py-2 px-4 font-medium text-slate-600">Title</th>
                              <th className="py-2 px-4 font-medium text-slate-600">Total</th>
                              <th className="py-2 px-4 font-medium text-slate-600">User</th>
                              <th className="py-2 px-4 font-medium text-slate-600">Agent</th>
                              <th className="py-2 px-4 font-medium text-slate-600">Started At</th>
                              <th className="py-2 px-4 font-medium text-slate-600">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {userDetails.conversations.map((conv: any) => (
                              <tr key={conv.id} className="hover:bg-slate-50">
                                <td className="py-2 px-4 text-slate-800 font-medium truncate max-w-[200px]" title={conv.title}>{conv.title}</td>
                                <td className="py-2 px-4 font-mono text-slate-600">{conv.total_messages}</td>
                                <td className="py-2 px-4 font-mono text-brand-600">{conv.user_messages || 0}</td>
                                <td className="py-2 px-4 font-mono text-emerald-600">{conv.agent_messages || 0}</td>
                                <td className="py-2 px-4 text-slate-600">{new Date(conv.started_at).toLocaleDateString()}</td>
                                <td className="py-2 px-4">
                                  <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                                    conv.status === 'active' ? 'bg-green-100 text-green-700' : 
                                    'bg-slate-100 text-slate-700'
                                  }`}>
                                    {conv.status}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  {/* Quota & Limits Details */}
                  <div>
                    <h4 className="text-md font-bold text-slate-800 mb-3 flex items-center">
                      <ShieldCheck className="w-4 h-4 mr-2 text-brand-500" /> Usage Limits & Quota
                    </h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex flex-col justify-center items-center text-center">
                        <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Daily Limit</div>
                        <div className="text-2xl font-bold text-slate-800">
                          {userDetails.subscription?.daily_messages_used || 0} <span className="text-sm font-normal text-slate-500">/ {userDetails.subscription?.daily_messages_limit > 0 ? userDetails.subscription.daily_messages_limit : '∞'}</span>
                        </div>
                        <div className="w-full bg-slate-200 rounded-full h-1.5 mt-3 overflow-hidden">
                          <div className={`h-1.5 rounded-full ${((userDetails.subscription?.daily_messages_used || 0) / (userDetails.subscription?.daily_messages_limit || 1)) > 0.9 ? 'bg-red-500' : 'bg-brand-500'}`} style={{ width: `${userDetails.subscription?.daily_messages_limit > 0 ? Math.min(100, ((userDetails.subscription?.daily_messages_used || 0) / userDetails.subscription.daily_messages_limit) * 100) : 0}%` }}></div>
                        </div>
                      </div>
                      <div className="bg-slate-50 p-4 rounded-xl border border-slate-100 flex flex-col justify-center items-center text-center">
                        <div className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-1">Monthly Limit</div>
                        <div className="text-2xl font-bold text-slate-800">
                          {userDetails.subscription?.monthly_messages_used || 0} <span className="text-sm font-normal text-slate-500">/ {userDetails.subscription?.monthly_messages_limit > 0 ? userDetails.subscription.monthly_messages_limit : '∞'}</span>
                        </div>
                        <div className="w-full bg-slate-200 rounded-full h-1.5 mt-3 overflow-hidden">
                          <div className={`h-1.5 rounded-full ${((userDetails.subscription?.monthly_messages_used || 0) / (userDetails.subscription?.monthly_messages_limit || 1)) > 0.9 ? 'bg-red-500' : 'bg-brand-500'}`} style={{ width: `${userDetails.subscription?.monthly_messages_limit > 0 ? Math.min(100, ((userDetails.subscription?.monthly_messages_used || 0) / userDetails.subscription.monthly_messages_limit) * 100) : 0}%` }}></div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Payments History */}
                  <div>
                    <h4 className="text-md font-bold text-slate-800 mb-3 flex items-center">
                      <CreditCard className="w-4 h-4 mr-2 text-brand-500" /> Payment History
                    </h4>
                    {userDetails.payments?.length === 0 ? (
                      <div className="p-4 bg-slate-50 rounded-lg text-slate-500 text-sm text-center">No payment history found.</div>
                    ) : (
                      <div className="border border-slate-200 rounded-xl overflow-hidden">
                        <table className="w-full text-left text-sm">
                          <thead className="bg-slate-50">
                            <tr>
                              <th className="py-2 px-4 font-medium text-slate-600">Date</th>
                              <th className="py-2 px-4 font-medium text-slate-600">Plan</th>
                              <th className="py-2 px-4 font-medium text-slate-600">Amount</th>
                              <th className="py-2 px-4 font-medium text-slate-600">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {userDetails.payments.map((payment: any) => (
                              <tr key={payment.id} className="hover:bg-slate-50">
                                <td className="py-2 px-4 text-slate-600">{new Date(payment.created_at).toLocaleDateString()}</td>
                                <td className="py-2 px-4 text-slate-800 font-medium capitalize">{payment.plan_name}</td>
                                <td className="py-2 px-4 font-mono text-slate-600">₹{payment.amount}</td>
                                <td className="py-2 px-4">
                                  <span className={`inline-flex px-2 py-0.5 rounded text-xs font-medium ${
                                    payment.status === 'success' || payment.status === 'COMPLETED' ? 'bg-green-100 text-green-700' : 
                                    payment.status === 'pending' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'
                                  }`}>
                                    {payment.status}
                                  </span>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                </div>
              ) : null}
            </div>
            <div className="p-4 border-t border-slate-100 flex justify-end">
              <button 
                onClick={() => { setViewingUserId(null); setUserDetails(null); }}
                className="px-6 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl font-medium transition-colors"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
