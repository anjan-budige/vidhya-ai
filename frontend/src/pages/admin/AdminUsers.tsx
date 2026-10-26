import { useState, useEffect } from 'react';
import {
  Search,
  Filter,
  MoreVertical,
  Ban,
  CheckCircle,
  ShieldAlert,
  ShieldCheck,
  CreditCard,

  Save,
  UserPlus,
  KeyRound,
  RefreshCw,
  Copy,
  ShieldOff,
  Pencil,
  Trash2,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';
import FreeModeBanner from '../../components/admin/FreeModeBanner';
import { usePlatformConfig } from '../../hooks/usePlatformConfig';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';
import Modal from '../../components/ui/Modal';
import Avatar from '../../components/ui/Avatar';
import StatsCard from '../../components/ui/StatsCard';
import { UserCheck, UserX, Wallet, Users as UsersIcon } from 'lucide-react';

export default function AdminUsers() {
  const { freeMode } = usePlatformConfig();
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [actionsUser, setActionsUser] = useState<any | null>(null);
  const [plans, setPlans] = useState<any[]>([]);
  const [assigningUser, setAssigningUser] = useState<any | null>(null);
  const [selectedPlanId, setSelectedPlanId] = useState<string>('');
  const [assigning, setAssigning] = useState(false);
  const [viewingUserId, setViewingUserId] = useState<string | null>(null);
  const [userDetails, setUserDetails] = useState<any | null>(null);
  const [loadingDetails, setLoadingDetails] = useState(false);

  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createdResult, setCreatedResult] = useState<any | null>(null);
  const [createForm, setCreateForm] = useState({
    name: '',
    username: '',
    email: '',
    mobile: '',
    password: '',
  });

  const [editingUser, setEditingUser] = useState<any | null>(null);
  const [editForm, setEditForm] = useState({
    name: '',
    username: '',
    email: '',
    mobile: '',
  });
  const [editBusy, setEditBusy] = useState(false);

  const [keyUser, setKeyUser] = useState<any | null>(null);
  const [keyInfo, setKeyInfo] = useState<any | null>(null);
  const [rawKey, setRawKey] = useState('');
  const [keyBusy, setKeyBusy] = useState(false);

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

  const openEditUser = (user: any) => {
    setActionsUser(null);
    setEditingUser(user);
    setEditForm({
      name: [user.first_name, user.last_name].filter(Boolean).join(' '),
      username: user.username || '',
      email: user.email || '',
      mobile: user.mobile || '',
    });
  };

  const saveUserDetails = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!editingUser) return;
    setEditBusy(true);
    try {
      await api.patch(`/users/${editingUser.id}`, editForm);
      toast.success('User details updated.');
      setEditingUser(null);
      await fetchUsers();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not update the user.');
    } finally {
      setEditBusy(false);
    }
  };

  const deleteUser = async (user: any) => {
    const name = [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username;
    if (
      !window.confirm(
        `Permanently delete ${name}? This deletes their chats, messages, usage, subscriptions and API keys. This cannot be undone.`
      )
    ) {
      return;
    }
    setActionsUser(null);
    try {
      await api.delete(`/users/${user.id}`);
      toast.success('User deleted.');
      await fetchUsers();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not delete the user.');
    }
  };

  const toggleStatus = async (user: any) => {
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

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await api.post('/users/', {
        name: createForm.name,
        username: createForm.username.toLowerCase(),
        email: createForm.email,
        mobile: createForm.mobile,
        password: createForm.password || null,
      });
      setCreatedResult(res.data);
      setCreateForm({ name: '', username: '', email: '', mobile: '', password: '' });
      fetchUsers();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not create the user.');
    } finally {
      setCreating(false);
    }
  };

  const openApiAccess = async (user: any) => {
    setKeyUser(user);
    setKeyInfo(null);
    setRawKey('');
    try {
      const res = await api.get(`/users/${user.id}/api-key`);
      setKeyInfo(res.data);
    } catch {
      // A missing key is not an error.
    }
  };

  const rotateKey = async () => {
    if (!keyUser) return;
    setKeyBusy(true);
    try {
      const res = await api.post(`/users/${keyUser.id}/api-key`);
      setKeyInfo(res.data.info);
      setRawKey(res.data.key);
      toast.success('New key created. Copy it now.');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not create a key.');
    } finally {
      setKeyBusy(false);
    }
  };

  const toggleKey = async () => {
    if (!keyUser || !keyInfo) return;
    setKeyBusy(true);
    try {
      const res = await api.patch(`/users/${keyUser.id}/api-key`, {
        is_enabled: !keyInfo.is_enabled,
      });
      setKeyInfo(res.data);
      toast.success(res.data.is_enabled ? 'API access enabled.' : 'API access disabled.');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not update the key.');
    } finally {
      setKeyBusy(false);
    }
  };

  const revokeKey = async () => {
    if (!keyUser) return;
    if (!window.confirm('Revoke this API key? Bot sessions using it stop working.')) return;
    setKeyBusy(true);
    try {
      await api.delete(`/users/${keyUser.id}/api-key`);
      setKeyInfo(null);
      setRawKey('');
      toast.success('API key revoked.');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not revoke the key.');
    } finally {
      setKeyBusy(false);
    }
  };

  const copyKey = async () => {
    try {
      await navigator.clipboard.writeText(rawKey);
      toast.success('Key copied.');
    } catch {
      toast.error('Copy failed — select the key manually.');
    }
  };

  return (
    <div className="mx-auto flex h-full max-w-7xl flex-col space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-brand-600">People</p>
          <h1 className="mt-1 text-2xl font-bold tracking-tight text-ink">Users</h1>
          <p className="mt-1 text-sm text-muted">Accounts, access and API keys in one place.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              type="text"
              placeholder="Search name, email..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input-field h-10 w-64 pl-9 text-xs"
            />
          </div>
          <button className="btn-outline gap-2 text-xs"><Filter className="h-3.5 w-3.5" /> Filter</button>
          <button
            onClick={() => { setCreatedResult(null); setCreateOpen(true); }}
            className="btn-primary gap-2 text-xs"
          >
            <UserPlus className="h-4 w-4" /> Add user
          </button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatsCard label="Total users" value={users.length} icon={UsersIcon} tone="brand" hint="All accounts" />
        <StatsCard label="Active" value={users.filter((u) => u.is_active && !u.is_banned).length} icon={UserCheck} tone="success" hint="Can sign in" />
        <StatsCard label="Banned" value={users.filter((u) => u.is_banned).length} icon={UserX} tone="danger" hint="Access blocked" />
        <StatsCard label="Paid plans" value={users.filter((u) => u.current_plan && u.current_plan !== "free").length} icon={Wallet} tone="warning" hint="Upgraded users" />
      </div>

      {freeMode && (
        <FreeModeBanner message="Free mode — every user has the same access. Plan assignment is disabled." />
      )}

      <div className="card overflow-visible">
        {loading ? (
          <div className="p-12 flex flex-col items-center justify-center text-muted">
            <div className="w-10 h-10 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin mb-4"></div>
            Loading user database...
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[800px]">
              <thead>
                <tr className="border-b border-line bg-canvas">
                  <th className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">User</th>
                  <th className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">Telegram ID</th>
                  <th className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">Plan</th>
                  <th className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">Status</th>
                  <th className="px-5 py-3 text-[11px] font-semibold uppercase tracking-wider text-muted">Join Date</th>
                  <th className="px-5 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-muted">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-12 text-center text-sm text-muted">No users found.</td>
                  </tr>
                ) : users.map((user) => (
                  <tr key={user.id} className="border-b border-line/70 transition-colors hover:bg-canvas/60">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center">
                        <Avatar name={`${user.first_name} ${user.last_name || ''}`} className="mr-3" />
                        <div>
                          <p className="font-medium text-ink">{user.first_name} {user.last_name || ''}</p>
                          <p className="text-xs text-muted">{user.email || (user.username ? `@${user.username}` : `@${user.telegram_username || 'unknown'}`)}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 font-mono text-xs text-muted">
                      {user.telegram_id}
                    </td>
                    <td className="px-5 py-3.5">
                      <Badge tone={user.current_plan && user.current_plan !== 'free' ? 'brand' : 'neutral'}>
                        {user.current_plan || 'free'}
                      </Badge>
                    </td>
                    <td className="px-5 py-3.5">
                      {!user.is_banned ? (
                        <Badge tone="success"><CheckCircle className="h-3 w-3" /> Active</Badge>
                      ) : (
                        <Badge tone="danger"><Ban className="h-3 w-3" /> Banned</Badge>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-muted">
                      {new Date(user.created_at).toLocaleDateString()}
                    </td>
                    <td className="relative whitespace-nowrap px-5 py-3.5 text-right">
                      <button 
                        onClick={() => fetchUserDetails(user.id)}
                        className="text-brand-600 hover:text-brand-800 transition-colors p-2 bg-brand-50 rounded-lg mr-2 inline-flex items-center text-xs font-medium"
                      >
                        Details
                      </button>
                      <button 
                        onClick={() => setActionsUser(user)}
                        onMouseDown={(e) => e.stopPropagation()}
                        className="text-muted hover:text-brand-600 transition-colors p-2"
                      >
                        <MoreVertical className="w-5 h-5" />
                      </button>
                      
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <Modal
        open={!!assigningUser}
        onClose={() => setAssigningUser(null)}
        title={assigningUser ? `Assign plan to ${assigningUser.first_name}` : 'Assign plan'}
        subtitle="This immediately replaces the user's active subscription."
        icon={<CreditCard className="h-5 w-5" />}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAssigningUser(null)}>
              Cancel
            </Button>
            <Button type="submit" form="assign-plan-form" loading={assigning}>
              <Save className="h-4 w-4" /> Assign now
            </Button>
          </>
        }
      >
        <form id="assign-plan-form" onSubmit={handleAssignPlan} className="space-y-4">
          <div>
            <label className="input-label">Subscription plan</label>
            <select
              value={selectedPlanId}
              onChange={(e) => setSelectedPlanId(e.target.value)}
              className="input-field"
              required
            >
              {plans.map((plan) => (
                <option key={plan.id} value={plan.id}>
                  {plan.display_name} ({plan.name})
                </option>
              ))}
            </select>
            <p className="mt-2 text-xs text-muted">
              Any existing subscription is replaced immediately.
            </p>
          </div>
        </form>
      </Modal>

      <Modal
        open={!!viewingUserId}
        onClose={() => { setViewingUserId(null); setUserDetails(null); }}
        title="User details"
        subtitle={userDetails ? `${userDetails.first_name} ${userDetails.last_name || ''}` : 'Loading profile...'}
        icon={<UsersIcon className="h-5 w-5" />}
        size="xl"
        footer={
          <Button variant="outline" onClick={() => { setViewingUserId(null); setUserDetails(null); }}>
            Close
          </Button>
        }
      >

              {loadingDetails ? (
                <div className="flex justify-center items-center h-32">
                  <div className="w-8 h-8 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin"></div>
                </div>
              ) : userDetails ? (
                <div className="space-y-8">
                  <div className="flex items-center space-x-4">
                    <div className="w-16 h-16 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center font-bold text-2xl">
                      {userDetails.first_name.charAt(0)}
                    </div>
                    <div>
                      <h3 className="text-xl font-bold text-ink">{userDetails.first_name} {userDetails.last_name || ''}</h3>
                      <p className="text-muted">@{userDetails.telegram_username || 'unknown'} • ID: <span className="font-mono text-muted">{userDetails.telegram_id}</span></p>
                      <p className="text-xs text-muted mt-1">Joined: {new Date(userDetails.created_at).toLocaleDateString()}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-3 gap-4">
                    <div className="bg-canvas p-4 rounded-xl border border-line">
                      <div className="text-xs font-medium text-muted uppercase tracking-wider mb-1">Plan Usage</div>
                      <div className="text-2xl font-bold text-ink">
                        {userDetails.subscription?.monthly_messages_used || 0} <span className="text-sm font-normal text-muted">/ {userDetails.subscription?.monthly_messages_limit > 0 ? userDetails.subscription.monthly_messages_limit : '∞'} msgs</span>
                      </div>
                      <div className="text-sm text-brand-600 font-medium mt-1 uppercase">{userDetails.subscription?.plan_name}</div>
                    </div>
                    <div className="bg-canvas p-4 rounded-xl border border-line">
                      <div className="text-xs font-medium text-muted uppercase tracking-wider mb-1">Validity</div>
                      <div className="text-2xl font-bold text-ink">
                        {userDetails.subscription?.current_period_end 
                          ? `${Math.max(0, Math.floor((new Date(userDetails.subscription.current_period_end).getTime() - Date.now()) / (1000 * 60 * 60 * 24)))} Days`
                          : (userDetails.subscription?.validity_days ? `${userDetails.subscription.validity_days} Days` : 'Lifetime')}
                      </div>
                      <div className="text-sm text-muted mt-1">
                        {userDetails.subscription?.current_period_end 
                          ? `Expires: ${new Date(userDetails.subscription.current_period_end).toLocaleDateString()}` 
                          : 'No expiration'}
                      </div>
                    </div>
                    <div className="bg-canvas p-4 rounded-xl border border-line">
                      <div className="text-xs font-medium text-muted uppercase tracking-wider mb-1">Conversations</div>
                      <div className="text-2xl font-bold text-ink">{userDetails.conversations_count}</div>
                      <div className="text-sm text-muted mt-1">Total Active Chats</div>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-md font-bold text-ink mb-3 flex items-center">
                      <Search className="w-4 h-4 mr-2 text-brand-500" /> Conversations List
                    </h4>
                    {!userDetails.conversations || userDetails.conversations.length === 0 ? (
                      <div className="p-4 bg-canvas rounded-lg text-muted text-sm text-center">No conversations found.</div>
                    ) : (
                      <div className="border border-line rounded-xl overflow-hidden max-h-60 overflow-y-auto">
                        <table className="w-full text-left text-sm">
                          <thead className="bg-canvas sticky top-0">
                            <tr>
                              <th className="py-2 px-4 font-medium text-muted">Title</th>
                              <th className="py-2 px-4 font-medium text-muted">Total</th>
                              <th className="py-2 px-4 font-medium text-muted">User</th>
                              <th className="py-2 px-4 font-medium text-muted">Agent</th>
                              <th className="py-2 px-4 font-medium text-muted">Started At</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {userDetails.conversations.map((conv: any) => (
                              <tr key={conv.id} className="hover:bg-canvas">
                                <td className="py-2 px-4 text-ink font-medium truncate max-w-[200px]" title={conv.title}>{conv.title}</td>
                                <td className="py-2 px-4 font-mono text-muted">{conv.total_messages}</td>
                                <td className="py-2 px-4 font-mono text-brand-600">{conv.user_messages || 0}</td>
                                <td className="py-2 px-4 font-mono text-emerald-600">{conv.agent_messages || 0}</td>
                                <td className="py-2 px-4 text-muted">{new Date(conv.started_at).toLocaleDateString()}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </div>

                  <div>
                    <h4 className="text-md font-bold text-ink mb-3 flex items-center">
                      <ShieldCheck className="w-4 h-4 mr-2 text-brand-500" /> Usage Limits & Quota
                    </h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-canvas p-4 rounded-xl border border-line flex flex-col justify-center items-center text-center">
                        <div className="text-xs font-medium text-muted uppercase tracking-wider mb-1">Daily Limit</div>
                        <div className="text-2xl font-bold text-ink">
                          {userDetails.subscription?.daily_messages_used || 0} <span className="text-sm font-normal text-muted">/ {userDetails.subscription?.daily_messages_limit > 0 ? userDetails.subscription.daily_messages_limit : '∞'}</span>
                        </div>
                        <div className="w-full bg-line rounded-full h-1.5 mt-3 overflow-hidden">
                          <div className={`h-1.5 rounded-full ${((userDetails.subscription?.daily_messages_used || 0) / (userDetails.subscription?.daily_messages_limit || 1)) > 0.9 ? 'bg-red-500' : 'bg-brand-500'}`} style={{ width: `${userDetails.subscription?.daily_messages_limit > 0 ? Math.min(100, ((userDetails.subscription?.daily_messages_used || 0) / userDetails.subscription.daily_messages_limit) * 100) : 0}%` }}></div>
                        </div>
                      </div>
                      <div className="bg-canvas p-4 rounded-xl border border-line flex flex-col justify-center items-center text-center">
                        <div className="text-xs font-medium text-muted uppercase tracking-wider mb-1">Monthly Limit</div>
                        <div className="text-2xl font-bold text-ink">
                          {userDetails.subscription?.monthly_messages_used || 0} <span className="text-sm font-normal text-muted">/ {userDetails.subscription?.monthly_messages_limit > 0 ? userDetails.subscription.monthly_messages_limit : '∞'}</span>
                        </div>
                        <div className="w-full bg-line rounded-full h-1.5 mt-3 overflow-hidden">
                          <div className={`h-1.5 rounded-full ${((userDetails.subscription?.monthly_messages_used || 0) / (userDetails.subscription?.monthly_messages_limit || 1)) > 0.9 ? 'bg-red-500' : 'bg-brand-500'}`} style={{ width: `${userDetails.subscription?.monthly_messages_limit > 0 ? Math.min(100, ((userDetails.subscription?.monthly_messages_used || 0) / userDetails.subscription.monthly_messages_limit) * 100) : 0}%` }}></div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-md font-bold text-ink mb-3 flex items-center">
                      <CreditCard className="w-4 h-4 mr-2 text-brand-500" /> Payment History
                    </h4>
                    {userDetails.payments?.length === 0 ? (
                      <div className="p-4 bg-canvas rounded-lg text-muted text-sm text-center">No payment history found.</div>
                    ) : (
                      <div className="border border-line rounded-xl overflow-hidden">
                        <table className="w-full text-left text-sm">
                          <thead className="bg-canvas">
                            <tr>
                              <th className="py-2 px-4 font-medium text-muted">Date</th>
                              <th className="py-2 px-4 font-medium text-muted">Plan</th>
                              <th className="py-2 px-4 font-medium text-muted">Amount</th>
                              <th className="py-2 px-4 font-medium text-muted">Status</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {userDetails.payments.map((payment: any) => (
                              <tr key={payment.id} className="hover:bg-canvas">
                                <td className="py-2 px-4 text-muted">{new Date(payment.created_at).toLocaleDateString()}</td>
                                <td className="py-2 px-4 text-ink font-medium capitalize">{payment.plan_name}</td>
                                <td className="py-2 px-4 font-mono text-muted">₹{payment.amount}</td>
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
      </Modal>

      <Modal
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="Create user"
        subtitle="A disabled API key is generated and shown once."
        icon={<UserPlus className="h-5 w-5" />}
      >
        <div className="space-y-4">
{createdResult ? (
              <div className="space-y-4 p-5">
                <div className="rounded-lg border border-green-200 bg-success-soft p-3 text-sm text-success">
                  Account created for @{createdResult.user.username}.{' '}
                  {createdResult.setup_email_sent
                    ? 'A set-password email was sent.'
                    : 'Share the password securely.'}
                </div>

                <p className="text-xs text-muted">
                  No API key is created automatically. Use this user's Actions → API access
                  when they need bot access.
                </p>

                <div className="flex justify-end">
                  <Button onClick={() => setCreateOpen(false)}>Done</Button>
                </div>
              </div>
            ) : (
              <form onSubmit={handleCreateUser} className="space-y-4 p-5">
                <Input
                  label="Full name"
                  required
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  placeholder="Full name"
                />
                <Input
                  label="Username"
                  required
                  value={createForm.username}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      username: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''),
                    })
                  }
                  placeholder="username"
                  hint="Lowercase letters, numbers and underscore."
                />
                <Input
                  label="Email"
                  type="email"
                  required
                  value={createForm.email}
                  onChange={(e) => setCreateForm({ ...createForm, email: e.target.value })}
                  placeholder="user@example.com"
                />
                <Input
                  label="Mobile"
                  type="tel"
                  required
                  value={createForm.mobile}
                  onChange={(e) => setCreateForm({ ...createForm, mobile: e.target.value })}
                  placeholder="+91 98765 43210"
                />
                <Input
                  label="Password (optional)"
                  type="password"
                  value={createForm.password}
                  onChange={(e) => setCreateForm({ ...createForm, password: e.target.value })}
                  placeholder="Leave blank to email a setup link"
                  hint="Leave blank and we email a set-password link."
                />
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>
                    Cancel
                  </Button>
                  <Button type="submit" loading={creating}>
                    Create user
                  </Button>
                </div>
              </form>
            )}
        </div>
      </Modal>

      <Modal
        open={!!keyUser}
        onClose={() => setKeyUser(null)}
        title="API access"
        subtitle={keyUser ? `${keyUser.first_name} ${keyUser.last_name || ''}` : undefined}
        icon={<KeyRound className="h-5 w-5" />}
      >
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted">Status</span>
            {keyInfo ? (
              <Badge tone={keyInfo.is_enabled ? 'success' : 'neutral'}>
                {keyInfo.is_enabled ? 'Enabled' : 'Disabled'}
              </Badge>
            ) : (
              <Badge tone="neutral">No key</Badge>
            )}
          </div>

          {keyInfo && (
            <div className="space-y-1 text-sm">
              <div className="flex justify-between border-b border-line py-1.5">
                <span className="text-muted">Key</span>
                <span className="font-mono text-ink">{keyInfo.key_prefix}...</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-muted">Last used</span>
                <span className="text-ink">
                  {keyInfo.last_used_at
                    ? new Date(keyInfo.last_used_at).toLocaleString()
                    : 'Never'}
                </span>
              </div>
            </div>
          )}

          {rawKey && (
            <div className="rounded-lg border border-amber-200 bg-warning-soft p-3">
              <p className="mb-2 text-xs font-medium text-warning">
                Copy this key now - it is shown once.
              </p>
              <code className="block break-all rounded bg-surface p-2 font-mono text-xs text-ink">
                {rawKey}
              </code>
              <Button size="sm" variant="outline" className="mt-2" onClick={copyKey}>
                <Copy className="h-3.5 w-3.5" /> Copy
              </Button>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {keyInfo ? (
              <>
                <Button size="sm" onClick={rotateKey} loading={keyBusy}>
                  <RefreshCw className="h-3.5 w-3.5" /> Rotate key
                </Button>
                <Button size="sm" variant="outline" onClick={toggleKey} disabled={keyBusy}>
                  <KeyRound className="h-3.5 w-3.5" />
                  {keyInfo.is_enabled ? 'Disable' : 'Enable'}
                </Button>
                <Button size="sm" variant="danger" onClick={revokeKey} disabled={keyBusy}>
                  <ShieldOff className="h-3.5 w-3.5" /> Revoke key
                </Button>
              </>
            ) : (
              <Button size="sm" onClick={rotateKey} loading={keyBusy}>
                <KeyRound className="h-3.5 w-3.5" /> Create key
              </Button>
            )}
          </div>

          <p className="text-xs text-muted">
            The bot authenticates with this key after <code className="font-mono">/login</code>.
            Rotating replaces it; revoking deletes it immediately and clears the bot binding.
          </p>
        </div>
      </Modal>

      <Modal
        open={!!actionsUser}
        onClose={() => setActionsUser(null)}
        title={actionsUser ? `${actionsUser.first_name} ${actionsUser.last_name || ''}` : 'User'}
        subtitle="Choose an action for this account."
        icon={<UsersIcon className="h-5 w-5" />}
        size="sm"
      >
        <div className="space-y-2">
          <button
            onClick={() => {
              if (freeMode) {
                toast.error('Plan assignment is disabled in Free mode.');
                return;
              }
              const user = actionsUser;
              setActionsUser(null);
              setAssigningUser(user);
            }}
            disabled={freeMode}
            className="flex w-full items-center gap-3 rounded-lg border border-line px-3 py-3 text-left text-sm text-ink transition-colors hover:bg-canvas disabled:cursor-not-allowed disabled:opacity-50"
          >
            <CreditCard className="h-4 w-4 text-brand-500" /> Assign plan
          </button>
          <button
            onClick={() => {
              const user = actionsUser;
              setActionsUser(null);
              openApiAccess(user);
            }}
            className="flex w-full items-center gap-3 rounded-lg border border-line px-3 py-3 text-left text-sm text-ink transition-colors hover:bg-canvas"
          >
            <KeyRound className="h-4 w-4 text-brand-500" /> API access
          </button>
          <button
            onClick={() => openEditUser(actionsUser)}
            className="flex w-full items-center gap-3 rounded-lg border border-line px-3 py-3 text-left text-sm text-ink transition-colors hover:bg-canvas"
          >
            <Pencil className="h-4 w-4 text-brand-500" /> Edit details
          </button>
          <button
            onClick={() => {
              const user = actionsUser;
              setActionsUser(null);
              toggleStatus(user);
            }}
            className={`flex w-full items-center gap-3 rounded-lg border px-3 py-3 text-left text-sm transition-colors ${
              actionsUser?.is_banned
                ? 'border-green-200 text-green-700 hover:bg-green-50'
                : 'border-red-200 text-red-600 hover:bg-red-50'
            }`}
          >
            {actionsUser?.is_banned ? (
              <>
                <ShieldCheck className="h-4 w-4" /> Unban user
              </>
            ) : (
              <>
                <ShieldAlert className="h-4 w-4" /> Ban user
              </>
            )}
          </button>
          <button
            onClick={() => deleteUser(actionsUser)}
            className="flex w-full items-center gap-3 rounded-lg border border-red-200 px-3 py-3 text-left text-sm text-danger transition-colors hover:bg-danger-soft"
          >
            <Trash2 className="h-4 w-4" /> Delete user
          </button>
        </div>
      </Modal>

      <Modal
        open={!!editingUser}
        onClose={() => setEditingUser(null)}
        title="Edit user"
        subtitle={editingUser ? `@${editingUser.username || editingUser.id.slice(0, 8)}` : undefined}
        icon={<Pencil className="h-5 w-5" />}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditingUser(null)}>
              Cancel
            </Button>
            <Button type="submit" form="edit-user-form" loading={editBusy}>
              <Save className="h-4 w-4" /> Save changes
            </Button>
          </>
        }
      >
        <form id="edit-user-form" onSubmit={saveUserDetails} className="space-y-4">
          <Input
            label="Full name"
            required
            value={editForm.name}
            onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
          />
          <Input
            label="Username"
            value={editForm.username}
            onChange={(e) =>
              setEditForm({
                ...editForm,
                username: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''),
              })
            }
            hint="3-30 lowercase letters, numbers or underscore."
          />
          <Input
            label="Email"
            type="email"
            value={editForm.email}
            onChange={(e) => setEditForm({ ...editForm, email: e.target.value })}
          />
          <Input
            label="Mobile"
            type="tel"
            value={editForm.mobile}
            onChange={(e) => setEditForm({ ...editForm, mobile: e.target.value })}
          />
        </form>
      </Modal>

    </div>
  );
}
