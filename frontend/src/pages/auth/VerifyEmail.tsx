import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import api from '../../api';
import AuthShell from '../../components/auth/AuthShell';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';

export default function VerifyEmail() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [identifier, setIdentifier] = useState(params.get('identifier') || '');
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);

  useEffect(() => {
    if (cooldown <= 0) return;
    const timer = setTimeout(() => setCooldown((v) => v - 1), 1000);
    return () => clearTimeout(timer);
  }, [cooldown]);

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post('/auth/verify-email', { identifier, code });
      toast.success('Email verified.');
      navigate('/chat');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Invalid code.');
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async () => {
    try {
      await api.post('/auth/resend-otp', { identifier });
      setCooldown(60);
      toast.success('A new code is on its way.');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Could not resend the code.');
    }
  };

  return (
    <AuthShell
      title="Verify your email"
      subtitle="Enter the 6-digit code we sent you to activate your account."
      footer={
        <Link to="/login" className="font-medium text-brand-500 hover:text-brand-600">
          Back to sign in
        </Link>
      }
    >
      <form onSubmit={handleVerify} className="space-y-4">
        {!params.get('identifier') && (
          <Input
            label="Username or email"
            name="identifier"
            required
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="yourname"
          />
        )}

        <input
          type="text"
          inputMode="numeric"
          maxLength={6}
          required
          value={code}
          onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, ''))}
          placeholder="000000"
          className="input-field text-center font-mono text-2xl tracking-[0.5em]"
        />

        <Button
          type="submit"
          loading={loading}
          disabled={code.length !== 6 || !identifier}
          className="w-full"
        >
          Verify email
        </Button>

        <Button
          type="button"
          variant="ghost"
          className="w-full"
          disabled={cooldown > 0}
          onClick={handleResend}
        >
          {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend code'}
        </Button>
      </form>
    </AuthShell>
  );
}
