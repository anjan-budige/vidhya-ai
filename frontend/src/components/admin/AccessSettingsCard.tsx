import { useEffect, useState } from 'react';
import toast from 'react-hot-toast';
import api from '../../api';
import { Card, CardBody, CardHeader } from '../ui/Card';
import Switch from '../ui/Switch';

export default function AccessSettingsCard() {
  const [registration, setRegistration] = useState(false);
  const [otpLogin, setOtpLogin] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .get('/admin/platform/access')
      .then((res) => {
        setRegistration(!!res.data.registration_enabled);
        setOtpLogin(!!res.data.email_otp_login);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const save = async (patch: { registration_enabled?: boolean; email_otp_login?: boolean }) => {
    const previous = { registration, otpLogin };
    if (patch.registration_enabled !== undefined) setRegistration(patch.registration_enabled);
    if (patch.email_otp_login !== undefined) setOtpLogin(patch.email_otp_login);

    setSaving(true);
    try {
      const res = await api.patch('/admin/platform/access', patch);
      setRegistration(!!res.data.registration_enabled);
      setOtpLogin(!!res.data.email_otp_login);
      toast.success('Access settings updated.');
    } catch (err: any) {
      setRegistration(previous.registration);
      setOtpLogin(previous.otpLogin);
      toast.error(err.response?.data?.detail || 'Could not update access settings.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader
        title="Account access"
        subtitle="Control who can create an account and how they sign in."
      />
      <CardBody className="divide-y divide-line p-0">
        <div className="flex items-start justify-between gap-6 px-5 py-4">
          <div>
            <p className="text-sm font-medium text-ink">Allow public registration</p>
            <p className="mt-0.5 text-xs text-muted">
              Show the sign-up form at <code className="font-mono">/register</code>. When off,
              only administrators can create accounts.
            </p>
          </div>
          <Switch
            checked={registration}
            disabled={loading || saving}
            onChange={(value) => save({ registration_enabled: value })}
          />
        </div>

        <div className="flex items-start justify-between gap-6 px-5 py-4">
          <div>
            <p className="text-sm font-medium text-ink">
              Require an email code on every sign-in
            </p>
            <p className="mt-0.5 text-xs text-muted">
              After the password, send a 6-digit code. Email verification at sign-up is always
              required.
            </p>
          </div>
          <Switch
            checked={otpLogin}
            disabled={loading || saving}
            onChange={(value) => save({ email_otp_login: value })}
          />
        </div>
      </CardBody>
    </Card>
  );
}
