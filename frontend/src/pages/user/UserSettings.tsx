import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AtSign,
  Check,
  CreditCard,
  KeyRound,
  LockKeyhole,
  LogOut,
  Mail,
  MessageSquare,
  Phone,
  Save,
  ShieldCheck,
  UserRound,
} from 'lucide-react';
import { animate, stagger } from 'animejs';
import toast from 'react-hot-toast';
import api from '../../api';
import Avatar from '../../components/ui/Avatar';
import { Badge } from '../../components/ui/Badge';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { useUser } from '../../contexts/UserContext';
import { fmtDateTime, fmtLimit } from '../../lib/format';
import { cn } from '../../lib/cn';

export default function UserSettings() {
  const navigate = useNavigate();
  const { user, quota, fullDisplay, refreshUser, logout } = useUser();
  const [name, setName] = useState('');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [mobile, setMobile] = useState('');
  const [saving, setSaving] = useState(false);
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changing, setChanging] = useState(false);

  useEffect(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animate('.profile-reveal', { y: [12, 0], duration: 560, delay: stagger(70), ease: 'outExpo' });
  }, []);

  useEffect(() => {
    if (!user) return;
    setName([user.first_name, user.last_name].filter(Boolean).join(' '));
    setUsername(user.username ?? '');
    setEmail(user.email ?? '');
    setMobile(user.mobile ?? '');
  }, [user]);

  const unverified = Boolean(user?.email && !user.email_verified_at);
  const completion = [
    Boolean(name.trim()),
    Boolean(username.trim()),
    Boolean(email.trim()),
    Boolean(mobile.trim()),
    Boolean(user?.email_verified_at),
  ];
  const completionPercent = Math.round((completion.filter(Boolean).length / completion.length) * 100);

  const saveProfile = async () => {
    setSaving(true);
    try {
      const payload: Record<string, string> = {};
      if (name.trim() && name.trim() !== fullDisplay) payload.name = name.trim();
      if (username.trim() && username.trim() !== (user?.username ?? '')) payload.username = username.trim();
      if (email.trim() && email.trim() !== (user?.email ?? '')) payload.email = email.trim();
      if (mobile.trim() && mobile.trim() !== (user?.mobile ?? '')) payload.mobile = mobile.trim();
      if (!Object.keys(payload).length) {
        toast('Nothing to update.');
        return;
      }
      await api.patch('/auth/me', payload);
      await refreshUser();
      toast.success(payload.email ? 'Profile updated. Verify your new email address.' : 'Profile updated.');
    } catch {
      // api.ts surfaces the reason.
    } finally {
      setSaving(false);
    }
  };

  const changePassword = async () => {
    if (newPassword.length < 8) {
      toast.error('Use at least 8 characters for the new password.');
      return;
    }
    if (newPassword !== confirmPassword) {
      toast.error('New password and confirmation do not match.');
      return;
    }
    setChanging(true);
    try {
      await api.post('/auth/change-password', {
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      toast.success('Password updated.');
    } catch {
      // api.ts surfaces the reason.
    } finally {
      setChanging(false);
    }
  };

  const resendVerification = async () => {
    try {
      await api.post('/auth/resend-otp', { identifier: user?.email });
      toast.success('A new code is on its way.');
    } catch {
      // api.ts surfaces the reason.
    }
  };

  return (
    <div className="mx-auto max-w-[1120px] px-4 py-6 md:px-7 md:py-8">
      <header className="mb-6">
        <div className="mb-1.5 inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-brand-600">
          <UserRound className="h-3.5 w-3.5" /> Account
        </div>
        <h1 className="user-display text-2xl font-semibold tracking-tight text-ink md:text-[30px]">Your space, your details.</h1>
        <p className="mt-1.5 text-sm text-muted">Keep your profile current and your account secure.</p>
      </header>

      <section className="profile-reveal relative mb-5 overflow-hidden rounded-[22px] bg-[#0d1a2d] p-5 text-white shadow-[0_28px_70px_-42px_rgba(13,26,45,0.9)] md:p-7">
        <div className="pointer-events-none absolute -right-10 -top-20 h-60 w-60 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-24 left-1/4 h-48 w-48 rounded-full bg-info/15 blur-3xl" />
        <div className="pointer-events-none absolute inset-0 user-noise" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
          <span className="rounded-2xl ring-4 ring-white/10"><Avatar name={fullDisplay || 'Learner'} size="lg" className="!h-14 !w-14 !text-lg" /></span>
          <div className="min-w-0 flex-1">
            <h2 className="user-display truncate text-xl font-semibold tracking-tight text-white md:text-2xl">{fullDisplay || 'Learner'}</h2>
            <p className="mt-0.5 truncate text-xs text-slate-400">{user?.email || user?.username || 'Web account'}</p>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-white/10 bg-white/[0.07] px-2.5 py-1 text-[9px] font-semibold text-slate-200">{quota?.plan_name ?? 'Free'} plan</span>
              <span className={cn('inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[9px] font-semibold', user?.email_verified_at ? 'bg-success/20 text-success-soft' : 'bg-warning/20 text-warning-soft')}>
                {user?.email_verified_at ? <><Check className="h-2.5 w-2.5" /> Email verified</> : 'Email needs verification'}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-4 rounded-2xl border border-white/[0.08] bg-white/[0.045] px-4 py-3">
            <div className="relative h-12 w-12">
              <svg viewBox="0 0 36 36" className="ring-progress h-12 w-12">
                <circle cx="18" cy="18" r="15" fill="none" stroke="rgba(255,255,255,.1)" strokeWidth="3" />
                <circle cx="18" cy="18" r="15" fill="none" stroke="#6293FF" strokeWidth="3" strokeLinecap="round" strokeDasharray={`${(completionPercent / 100) * 94.2} 94.2`} />
              </svg>
              <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-white">{completionPercent}%</span>
            </div>
            <div><p className="text-xs font-semibold">Profile strength</p><p className="mt-0.5 text-[10px] text-slate-400">{completionPercent === 100 ? 'Everything is complete' : 'Complete the remaining details'}</p></div>
          </div>
        </div>
      </section>

      {unverified && (
        <div className="profile-reveal mb-5 flex flex-wrap items-center gap-3 rounded-xl border border-amber-200 bg-warning-soft px-4 py-3 text-xs text-warning">
          <ShieldCheck className="h-4 w-4 shrink-0" />
          <span className="min-w-48 flex-1">Verify {user?.email} to use it for sign-in and account recovery.</span>
          <Button size="sm" variant="outline" onClick={() => void resendVerification()}>Resend code</Button>
          <Button size="sm" onClick={() => navigate(`/verify-email?identifier=${encodeURIComponent(user?.email ?? '')}`)}>Verify now</Button>
        </div>
      )}

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_330px]">
        <div className="space-y-5">
          <section className="profile-reveal user-card overflow-hidden">
            <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
              <div><h2 className="user-display text-base font-semibold text-ink">Personal information</h2><p className="mt-0.5 text-xs text-muted">Used across your web workspace and Telegram.</p></div>
              <span className="hidden h-9 w-9 items-center justify-center rounded-xl bg-brand-50 text-brand-600 sm:flex"><UserRound className="h-4 w-4" /></span>
            </div>
            <form onSubmit={(event) => { event.preventDefault(); void saveProfile(); }}>
              <div className="grid gap-4 p-5 sm:grid-cols-2">
                <Input label="Full name" name="profile_name" value={name} onChange={(event) => setName(event.target.value)} icon={<UserRound className="h-4 w-4" />} />
                <Input label="Username" name="profile_username" value={username} onChange={(event) => setUsername(event.target.value)} icon={<AtSign className="h-4 w-4" />} hint="Lowercase letters, numbers and underscore." />
                <Input label="Email" name="profile_email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} icon={<Mail className="h-4 w-4" />} hint="Changing this starts verification again." />
                <Input label="Mobile" name="profile_mobile" value={mobile} onChange={(event) => setMobile(event.target.value)} icon={<Phone className="h-4 w-4" />} hint="Digits only, 7 to 20 characters." />
              </div>
              <div className="flex justify-end border-t border-line bg-canvas/40 px-5 py-3.5">
                <Button type="submit" loading={saving}><Save className="h-4 w-4" /> Save changes</Button>
              </div>
            </form>
          </section>

          <section className="profile-reveal user-card overflow-hidden">
            <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
              <div><h2 className="user-display text-base font-semibold text-ink">Password & security</h2><p className="mt-0.5 text-xs text-muted">Update the password used to sign in to this account.</p></div>
              <span className="hidden h-9 w-9 items-center justify-center rounded-xl bg-canvas text-muted sm:flex"><LockKeyhole className="h-4 w-4" /></span>
            </div>
            <form onSubmit={(event) => { event.preventDefault(); void changePassword(); }}>
              <div className="grid gap-4 p-5 sm:grid-cols-2">
                <div className="sm:col-span-2"><Input label="Current password" name="current_password" type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} autoComplete="current-password" /></div>
                <Input label="New password" name="new_password" type="password" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} autoComplete="new-password" hint="Minimum 8 characters." />
                <Input label="Confirm new password" name="confirm_password" type="password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} autoComplete="new-password" />
              </div>
              <div className="flex justify-end border-t border-line bg-canvas/40 px-5 py-3.5">
                <Button type="submit" loading={changing} disabled={!currentPassword || !newPassword || !confirmPassword}><KeyRound className="h-4 w-4" /> Update password</Button>
              </div>
            </form>
          </section>
        </div>

        <div className="space-y-4">
          <section className="profile-reveal user-card p-5">
            <div className="flex items-center gap-2"><CreditCard className="h-4 w-4 text-brand-500" /><h2 className="user-display text-sm font-semibold text-ink">Plan snapshot</h2></div>
            <div className="mt-4 flex items-center gap-3 rounded-xl border border-brand-100 bg-brand-50/70 p-3">
              <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-white text-brand-600 shadow-sm"><CreditCard className="h-4 w-4" /></span>
              <div><p className="text-sm font-semibold capitalize text-ink">{quota?.plan_name ?? 'Free'}</p><p className="text-[10px] text-muted">Current membership</p></div>
            </div>
            <div className="mt-3 space-y-2.5 text-xs">
              <div className="flex justify-between gap-3"><span className="text-muted">Messages today</span><span className="font-semibold text-ink">{quota?.daily_messages_used ?? 0} / {fmtLimit(quota?.daily_messages_limit)}</span></div>
              <div className="flex justify-between gap-3"><span className="text-muted">Saved chats</span><span className="font-semibold text-ink">{quota?.sessions_used ?? 0} / {fmtLimit(quota?.max_sessions)}</span></div>
            </div>
            <Button variant="outline" size="sm" className="mt-4 w-full" onClick={() => navigate('/plans')}>View plans & usage</Button>
          </section>

          <section className="profile-reveal user-card p-5">
            <h2 className="user-display text-sm font-semibold text-ink">Connected accounts</h2>
            <div className="mt-3 space-y-2">
              <div className="flex items-center gap-3 rounded-xl border border-line p-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-success-soft text-success"><ShieldCheck className="h-4 w-4" /></span>
                <div className="min-w-0 flex-1"><p className="text-xs font-semibold text-ink">This browser</p><p className="truncate text-[10px] text-muted">Signed in as {user?.username ?? user?.email}</p></div>
                <Badge tone="success">Active</Badge>
              </div>
              <div className="flex items-center gap-3 rounded-xl border border-line p-3">
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#2AABEE]/10 text-[#2AABEE]"><MessageSquare className="h-4 w-4" /></span>
                <div className="min-w-0 flex-1"><p className="text-xs font-semibold text-ink">Telegram</p><p className="text-[10px] text-muted">{user?.telegram_id ? 'Account linked' : 'Not connected'}</p></div>
                <Badge tone={user?.telegram_id ? 'brand' : 'neutral'}>{user?.telegram_id ? 'Linked' : 'Unlinked'}</Badge>
              </div>
            </div>
            <Button variant="outline" size="sm" className="mt-3 w-full" onClick={() => navigate('/api-keys')}>Manage Telegram access</Button>
          </section>

          <section className="profile-reveal user-card p-4">
            <p className="text-[10px] leading-relaxed text-muted">
              Signed in with {user?.auth_provider ?? 'web'} authentication{user?.email_verified_at ? ` · verified ${fmtDateTime(user.email_verified_at)}` : ''}.
            </p>
            <button onClick={() => void logout()} className="mt-3 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-xs font-medium text-danger transition-colors hover:bg-danger-soft"><LogOut className="h-3.5 w-3.5" /> Sign out of this browser</button>
          </section>
        </div>
      </div>
    </div>
  );
}
