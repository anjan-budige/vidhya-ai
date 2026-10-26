import { useCallback, useEffect, useState } from 'react';
import {
  Check,
  CircleCheck,
  Clock3,
  Copy,
  KeyRound,
  Link2,
  RefreshCw,
  Send,
  ShieldCheck,
  ShieldOff,
  Smartphone,
} from 'lucide-react';
import { animate, stagger } from 'animejs';
import toast from 'react-hot-toast';
import api from '../../api';
import Button from '../../components/ui/Button';
import ConfirmModal from '../../components/ui/ConfirmModal';
import Switch from '../../components/ui/Switch';
import { useUser } from '../../contexts/UserContext';
import { fmtDateTime } from '../../lib/format';
import { cn } from '../../lib/cn';

interface ApiKeyInfo {
  id: string;
  label: string;
  key_prefix: string;
  is_enabled: boolean;
  last_used_at: string | null;
  created_at: string;
}

export default function UserApiKeys() {
  const { user, refreshUser } = useUser();
  const [keyInfo, setKeyInfo] = useState<ApiKeyInfo | null>(null);
  const [rawKey, setRawKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [confirmRotate, setConfirmRotate] = useState(false);
  const [confirmRevoke, setConfirmRevoke] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await api.get('/users/me/api-key');
      setKeyInfo(res.data ?? null);
    } catch {
      setKeyInfo(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (loading || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    animate('.telegram-reveal', { y: [12, 0], duration: 540, delay: stagger(70), ease: 'outExpo' });
  }, [loading]);

  const issue = async (rotate: boolean) => {
    setBusy(true);
    try {
      const res = await api.post('/users/me/api-key');
      setRawKey(res.data.key);
      setKeyInfo(res.data.info);
      toast.success(rotate ? 'New key issued — the old one no longer works.' : 'Key created. Copy it now.');
      await refreshUser();
    } catch {
      // api.ts surfaces the reason.
    } finally {
      setBusy(false);
      setConfirmRotate(false);
    }
  };

  const setEnabled = async (enabled: boolean) => {
    setBusy(true);
    try {
      const res = await api.patch('/users/me/api-key', { is_enabled: enabled });
      setKeyInfo(res.data);
      toast.success(enabled ? 'Telegram access enabled.' : 'Telegram access paused.');
    } catch {
      // api.ts surfaces the reason.
    } finally {
      setBusy(false);
    }
  };

  const revoke = async () => {
    setBusy(true);
    try {
      await api.delete('/users/me/api-key');
      setKeyInfo(null);
      setRawKey('');
      toast.success('Key revoked and deleted.');
      await refreshUser();
    } catch {
      // api.ts surfaces the reason.
    } finally {
      setBusy(false);
      setConfirmRevoke(false);
    }
  };

  const copy = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label} copied.`);
    } catch {
      toast.error('Copy failed — select the text manually.');
    }
  };

  const bound = Boolean(user?.telegram_id);
  const command = `/login ${rawKey || '<your-key>'}`;

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-6 md:px-7 md:py-8">
      <header className="mb-6">
        <div className="mb-1.5 inline-flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-brand-600">
          <Send className="h-3.5 w-3.5" /> Connected services
        </div>
        <h1 className="user-display text-2xl font-semibold tracking-tight text-ink md:text-[30px]">Vidhya, wherever you study.</h1>
        <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-muted">Connect this account to the Telegram bot with one private key. The same plan, chats and limits follow you there.</p>
      </header>

      <section className="telegram-reveal relative mb-5 overflow-hidden rounded-[22px] bg-[#0d1a2d] p-5 text-white shadow-[0_28px_70px_-42px_rgba(13,26,45,0.9)] md:p-7">
        <div className="pointer-events-none absolute -right-10 -top-16 h-56 w-56 rounded-full bg-[#2AABEE]/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-20 right-1/3 h-44 w-44 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-[#2AABEE] text-white shadow-lg shadow-[#2AABEE]/25">
            <Send className="h-6 w-6" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="user-display text-xl font-semibold text-white">Telegram bot</h2>
              <span className={cn('inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wider', bound ? 'bg-success/20 text-success-soft' : 'bg-white/[0.08] text-slate-300')}>
                {bound ? <><CircleCheck className="h-2.5 w-2.5" /> Connected</> : 'Not connected'}
              </span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-slate-400">
              {bound ? 'This account is linked. You can chat in Telegram with the same study workspace.' : 'Create a key, send one command to @vidhya_hub_bot, and your account is linked.'}
            </p>
          </div>
          <a
            href="https://t.me/vidhya_hub_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-white px-4 py-2.5 text-xs font-semibold text-[#101d31] transition-transform hover:-translate-y-0.5"
          ><Send className="h-3.5 w-3.5" /> Open bot</a>
        </div>
      </section>

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          {rawKey && (
            <section className="telegram-reveal relative overflow-hidden rounded-2xl border border-brand-200 bg-gradient-to-br from-brand-50 via-white to-info-soft p-5">
              <div className="pointer-events-none absolute -right-8 -top-12 h-36 w-36 rounded-full bg-brand-100/70 blur-2xl" />
              <div className="relative">
                <div className="flex items-center gap-2 text-xs font-semibold text-brand-800">
                  <ShieldCheck className="h-4 w-4" /> Copy this key now. It will not be shown again.
                </div>
                <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
                  <code className="min-w-0 flex-1 overflow-x-auto rounded-xl border border-brand-100 bg-white/80 px-4 py-3 font-mono text-sm tracking-tight text-ink shadow-sm">{rawKey}</code>
                  <Button onClick={() => void copy(rawKey, 'Key')} className="glow-brand shrink-0"><Copy className="h-4 w-4" /> Copy key</Button>
                </div>
              </div>
            </section>
          )}

          <section className="telegram-reveal user-card overflow-hidden">
            <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
              <div>
                <h2 className="user-display text-base font-semibold text-ink">Connection key</h2>
                <p className="mt-0.5 text-xs text-muted">Only a hashed copy is stored. A key can be replaced, never recovered.</p>
              </div>
              {keyInfo && (
                <Button variant="outline" size="sm" onClick={() => setConfirmRotate(true)} disabled={busy}>
                  <RefreshCw className="h-3.5 w-3.5" /> Rotate key
                </Button>
              )}
            </div>

            {loading ? (
              <div className="space-y-3 p-5"><div className="h-12 w-2/3 animate-pulse rounded-xl bg-canvas" /><div className="h-5 w-1/3 animate-pulse rounded bg-canvas" /></div>
            ) : keyInfo ? (
              <div className="space-y-5 p-5">
                <div className="flex flex-wrap items-center gap-3 rounded-xl border border-line bg-canvas/70 px-4 py-3.5">
                  <span className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-xl', keyInfo.is_enabled ? 'bg-success-soft text-success' : 'bg-warning-soft text-warning')}><KeyRound className="h-4 w-4" /></span>
                  <code className="min-w-0 flex-1 truncate font-mono text-sm tracking-tight text-ink">{keyInfo.key_prefix}<span className="text-muted">•••••••••••••••••</span></code>
                  <span className={cn('rounded-full px-2 py-1 text-[9px] font-semibold uppercase tracking-wider', keyInfo.is_enabled ? 'bg-success-soft text-success' : 'bg-warning-soft text-warning')}>
                    {keyInfo.is_enabled ? 'Enabled' : 'Paused'}
                  </span>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="rounded-xl border border-line p-3.5">
                    <p className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.13em] text-muted"><Clock3 className="h-3 w-3" /> Created</p>
                    <p className="mt-1.5 text-xs font-medium text-ink">{fmtDateTime(keyInfo.created_at)}</p>
                  </div>
                  <div className="rounded-xl border border-line p-3.5">
                    <p className="flex items-center gap-1.5 text-[9px] font-semibold uppercase tracking-[0.13em] text-muted"><Smartphone className="h-3 w-3" /> Last used</p>
                    <p className="mt-1.5 text-xs font-medium text-ink">{keyInfo.last_used_at ? fmtDateTime(keyInfo.last_used_at) : 'Never used'}</p>
                  </div>
                </div>

                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-4">
                  <div className="flex items-center gap-3">
                    <Switch checked={keyInfo.is_enabled} onChange={(value) => void setEnabled(value)} disabled={busy} label="Telegram access enabled" />
                    <div><p className="text-xs font-medium text-ink">{keyInfo.is_enabled ? 'Bot access is active' : 'Bot access is paused'}</p><p className="text-[10px] text-muted">{keyInfo.is_enabled ? 'Requests from Telegram are accepted.' : 'Requests from Telegram are rejected.'}</p></div>
                  </div>
                  <Button variant="danger" size="sm" onClick={() => setConfirmRevoke(true)} disabled={busy}><ShieldOff className="h-3.5 w-3.5" /> Revoke</Button>
                </div>
              </div>
            ) : (
              <div className="px-5 py-12 text-center">
                <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-canvas text-muted"><KeyRound className="h-5 w-5" /></span>
                <p className="mt-3 text-sm font-semibold text-ink">No connection key yet</p>
                <p className="mx-auto mt-1 max-w-sm text-xs leading-relaxed text-muted">The web app works without a key. Create one only when you want to use Vidhya in Telegram.</p>
                <Button className="mt-4" onClick={() => void issue(false)} loading={busy}>Create connection key</Button>
              </div>
            )}
          </section>
        </div>

        <div className="space-y-5">
          <section className="telegram-reveal user-card p-5">
            <div className="flex items-center gap-2"><Link2 className="h-4 w-4 text-brand-500" /><h2 className="user-display text-base font-semibold text-ink">How to connect</h2></div>
            <ol className="mt-4 space-y-4">
              {[
                ['Create your key', 'Copy it while it is visible.'],
                ['Open the bot', 'Start a chat with @vidhya_hub_bot.'],
                ['Send /login', 'Paste the command below with your key.'],
              ].map(([title, text], index) => (
                <li key={title} className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-[10px] font-bold text-brand-600 ring-1 ring-brand-100">{index + 1}</span>
                  <div><p className="text-xs font-semibold text-ink">{title}</p><p className="mt-0.5 text-[11px] leading-relaxed text-muted">{text}</p></div>
                </li>
              ))}
            </ol>
            <div className="mt-4 flex items-center gap-2 rounded-xl border border-line bg-canvas px-3 py-2.5">
              <code className="min-w-0 flex-1 truncate font-mono text-[11px] text-ink">{command}</code>
              <button onClick={() => void copy(command, 'Command')} className="shrink-0 rounded-md p-1.5 text-muted transition-colors hover:bg-white hover:text-ink" aria-label="Copy login command"><Copy className="h-3.5 w-3.5" /></button>
            </div>
          </section>

          <section className="telegram-reveal user-card p-5">
            <div className="flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-success-soft text-success"><ShieldCheck className="h-4 w-4" /></span>
              <div><p className="text-xs font-semibold text-ink">Keep it private</p><p className="mt-1 text-[11px] leading-relaxed text-muted">Anyone with this key can use your account. Rotate it if it is exposed, or revoke it to disconnect Telegram immediately.</p></div>
            </div>
          </section>

          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1 text-[10px] text-muted">
            <span className="inline-flex items-center gap-1"><Check className="h-3 w-3 text-success" /> Hashed storage</span>
            <span className="inline-flex items-center gap-1"><Check className="h-3 w-3 text-success" /> Instant revoke</span>
          </div>
        </div>
      </div>

      <ConfirmModal
        open={confirmRotate}
        title="Rotate this key?"
        confirmLabel="Rotate"
        tone="primary"
        loading={busy}
        description="The current key is deleted and a new one is issued. Telegram will need /login again with the new key."
        onConfirm={() => void issue(true)}
        onClose={() => setConfirmRotate(false)}
      />

      <ConfirmModal
        open={confirmRevoke}
        title="Revoke Telegram access?"
        confirmLabel="Revoke key"
        loading={busy}
        description="The key is deleted, cached authentication is cleared and the Telegram link is removed. You can create a new key any time."
        onConfirm={() => void revoke()}
        onClose={() => setConfirmRevoke(false)}
      />
    </div>
  );
}
