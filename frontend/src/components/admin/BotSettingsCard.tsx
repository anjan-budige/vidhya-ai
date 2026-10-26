import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import api from '../../api';
import { Card, CardBody, CardHeader } from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import Switch from '../ui/Switch';

interface BotSettings {
  welcome_title: string;
  welcome_message: string;
  login_hint: string;
  register_hint: string;
  show_register_link: boolean;
  session_prompt_text: string;
  session_limit_text: string;
  session_started_text: string;
  idle_prompt_minutes: number;
}

const empty: BotSettings = {
  welcome_title: '',
  welcome_message: '',
  login_hint: '',
  register_hint: '',
  show_register_link: true,
  session_prompt_text: '',
  session_limit_text: '',
  session_started_text: '',
  idle_prompt_minutes: 25,
};

export default function BotSettingsCard() {
  const [form, setForm] = useState<BotSettings>(empty);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .get('/admin/platform/bot')
      .then((res) => setForm({ ...empty, ...res.data }))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const update = (key: keyof BotSettings, value: string | boolean | number) =>
    setForm((prev) => ({ ...prev, [key]: value }));

  const save = async () => {
    setSaving(true);
    try {
      const res = await api.patch('/admin/platform/bot', {
        ...form,
        idle_prompt_minutes: Number(form.idle_prompt_minutes) || 25,
      });
      setForm({ ...empty, ...res.data });
      toast.success('Bot settings saved.');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not save bot settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader
        title="Telegram bot"
        subtitle="Copy shown in the bot. Use {register_url} inside the register hint."
      />
      <CardBody className="space-y-5">
        {loading ? (
          <div className="h-24 animate-pulse rounded-lg bg-canvas" />
        ) : (
          <>
            <Input
              label="Welcome title"
              value={form.welcome_title}
              onChange={(e) => update('welcome_title', e.target.value)}
              placeholder="Welcome to Vidhya AI"
            />

            <div>
              <label className="input-label">Welcome message</label>
              <textarea
                value={form.welcome_message}
                onChange={(e) => update('welcome_message', e.target.value)}
                rows={4}
                className="input-field resize-y"
                placeholder="Your institution's AI learning assistant..."
              />
            </div>

            <Input
              label="Login hint"
              value={form.login_hint}
              onChange={(e) => update('login_hint', e.target.value)}
              placeholder="Use /login <api-key> to connect your account."
            />

            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Register hint"
                value={form.register_hint}
                onChange={(e) => update('register_hint', e.target.value)}
                placeholder="No account? Register here: {register_url}"
              />
              <Input
                label="Idle prompt (minutes)"
                type="number"
                min={5}
                value={String(form.idle_prompt_minutes)}
                onChange={(e) => update('idle_prompt_minutes', Number(e.target.value))}
                hint="Ask Continue/New after this much inactivity."
              />
            </div>

            <div className="flex items-start justify-between gap-6 rounded-lg border border-line px-4 py-3">
              <div>
                <p className="text-sm font-medium text-ink">Show the register link</p>
                <p className="mt-0.5 text-xs text-muted">
                  Only rendered while public registration is enabled.
                </p>
              </div>
              <Switch
                checked={form.show_register_link}
                onChange={(value) => update('show_register_link', value)}
                label="Show register link"
              />
            </div>

            <div>
              <label className="input-label">Session prompt</label>
              <textarea
                value={form.session_prompt_text}
                onChange={(e) => update('session_prompt_text', e.target.value)}
                rows={3}
                className="input-field resize-y"
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="input-label">Session limit message</label>
                <textarea
                  value={form.session_limit_text}
                  onChange={(e) => update('session_limit_text', e.target.value)}
                  rows={3}
                  className="input-field resize-y"
                />
              </div>
              <Input
                label="New session confirmation"
                value={form.session_started_text}
                onChange={(e) => update('session_started_text', e.target.value)}
                placeholder="New session started."
              />
            </div>

            <div className="flex justify-end">
              <Button onClick={save} loading={saving}>
                Save bot settings
              </Button>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}
