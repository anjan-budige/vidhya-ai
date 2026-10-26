import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Loader2, Lock, User } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';
import AuthShell from '../../components/auth/AuthShell';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';

export default function UserLogin() {
  const navigate = useNavigate();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [registrationEnabled, setRegistrationEnabled] = useState(false);

  const [requiresOtp, setRequiresOtp] = useState(false);
  const [otpToken, setOtpToken] = useState('');
  const [code, setCode] = useState('');
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    api
      .get('/config/public')
      .then((res) => setRegistrationEnabled(!!res.data.registration_enabled))
      .catch(() => {});

    const checkExistingSession = async () => {
      try {
        await api.get('/auth/admin/me');
        navigate('/admin/dashboard', { replace: true });
        return;
      } catch {
        // Continue to the normal user session check.
      }

      try {
        await api.get('/auth/me');
        navigate('/chat', { replace: true });
      } catch {
        setChecking(false);
      }
    };

    checkExistingSession();
  }, [navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await api.post('/auth/login', { identifier, password });
      if (res.data.requires_otp) {
        setRequiresOtp(true);
        setOtpToken(res.data.otp_token);
        toast.success('Enter the code sent to your email.');
      } else {
        toast.success('Signed in.');
        navigate('/chat');
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Sign in failed.');
    } finally {
      setLoading(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await api.post('/auth/login/verify-otp', { otp_token: otpToken, code });
      toast.success('Signed in.');
      navigate('/chat');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Invalid code.');
    } finally {
      setLoading(false);
    }
  };

  if (checking) {
    return (
      <AuthShell title="Signing in" subtitle="Checking your session…">
        <div className="flex justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin text-brand-500" />
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title={requiresOtp ? 'Enter your code' : 'Sign in'}
      subtitle={
        requiresOtp
          ? 'We sent a 6-digit code to the email on your account.'
          : 'Use your username or email to continue.'
      }
      footer={
        !requiresOtp && registrationEnabled ? (
          <>
            New here?{' '}
            <Link to="/register" className="font-medium text-brand-500 hover:text-brand-600">
              Create an account
            </Link>
          </>
        ) : null
      }
    >
      {!requiresOtp ? (
        <form onSubmit={handleLogin} className="space-y-4">
          <Input
            label="Username or email"
            name="identifier"
            autoComplete="username"
            required
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            placeholder="yourname"
            icon={<User className="h-4 w-4" />}
          />
          <div>
            <Input
              label="Password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              icon={<Lock className="h-4 w-4" />}
            />
            <div className="mt-2 text-right">
              <Link
                to="/forgot-password"
                className="text-xs font-medium text-brand-500 hover:text-brand-600"
              >
                Forgot password?
              </Link>
            </div>
          </div>
          <Button type="submit" loading={loading} className="w-full">
            Sign in
          </Button>
        </form>
      ) : (
        <form onSubmit={handleVerify} className="space-y-4">
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
            disabled={code.length !== 6}
            className="w-full"
          >
            Verify and sign in
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="w-full"
            onClick={() => {
              setRequiresOtp(false);
              setCode('');
            }}
          >
            Back
          </Button>
        </form>
      )}
    </AuthShell>
  );
}
