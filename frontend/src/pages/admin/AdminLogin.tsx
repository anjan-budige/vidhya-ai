import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../api';
import toast from 'react-hot-toast';
import { Lock, User, KeyRound, ArrowRight } from 'lucide-react';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { LogoStacked } from '../../components/brand/Logo';

export default function AdminLogin() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const [requiresTotp, setRequiresTotp] = useState(false);
  const [sessionToken, setSessionToken] = useState('');
  const [totpCode, setTotpCode] = useState('');

  const [loading, setLoading] = useState(false);
  const totpInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const checkAuth = async () => {
      try {
        await api.get('/analytics/dashboard');
        navigate('/admin/dashboard');
      } catch {
        // Not logged in — stay on the login page.
      }
    };
    checkAuth();
  }, [navigate]);

  useEffect(() => {
    if (requiresTotp && totpInputRef.current) {
      totpInputRef.current.focus();
    }
  }, [requiresTotp]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await api.post('/auth/admin/login', { username, password });

      if (response.data.requires_totp) {
        setRequiresTotp(true);
        setSessionToken(response.data.session_token);
        toast.success('Credentials verified. Enter your 2FA code.');
      } else {
        toast.success('Successfully logged in.');
        navigate('/admin/dashboard');
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        toast.error(detail[0].msg || 'Login failed. Invalid input format.');
      } else {
        toast.error(detail || 'Login failed. Please check your credentials.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleTotpVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      await api.post('/auth/admin/totp/verify', {
        session_token: sessionToken,
        totp_code: totpCode,
      });
      toast.success('2FA verified successfully.');
      navigate('/admin/dashboard');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      if (Array.isArray(detail)) {
        toast.error(detail[0].msg || 'Invalid 2FA code format.');
      } else {
        toast.error(detail || 'Invalid 2FA code.');
      }
      setTotpCode('');
      totpInputRef.current?.focus();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas p-6">
      <div className="w-full max-w-[420px]">
        <div className="mb-7 flex justify-center">
          <LogoStacked width={200} />
        </div>

        <div className="card p-8">
          {!requiresTotp ? (
            <>
              <div className="mb-6">
                <h1 className="text-xl font-semibold text-ink">Admin sign in</h1>
                <p className="mt-1 text-sm text-muted">
                  Manage your workspace, users and platform settings.
                </p>
              </div>

              <form onSubmit={handleLogin} className="space-y-4">
                <Input
                  label="Username"
                  type="text"
                  name="username"
                  autoComplete="username"
                  required
                  disabled={loading}
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="admin"
                  icon={<User className="h-4 w-4" />}
                />

                <div>
                  <Input
                    label="Password"
                    type="password"
                    name="password"
                    autoComplete="current-password"
                    required
                    disabled={loading}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    icon={<Lock className="h-4 w-4" />}
                  />
                  <div className="mt-2 text-right">
                    <a
                      href="/admin/forgot-password"
                      className="text-xs font-medium text-brand-500 hover:text-brand-600"
                    >
                      Forgot password?
                    </a>
                  </div>
                </div>

                <Button
                  type="submit"
                  loading={loading}
                  disabled={!username || !password}
                  className="w-full"
                >
                  Continue <ArrowRight className="h-4 w-4" />
                </Button>
              </form>
            </>
          ) : (
            <>
              <div className="mb-6 flex flex-col items-center text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-brand-50">
                  <KeyRound className="h-5 w-5 text-brand-500" />
                </div>
                <h1 className="text-xl font-semibold text-ink">Two-factor authentication</h1>
                <p className="mt-1 text-sm text-muted">
                  Enter the 6-digit code from your authenticator app.
                </p>
              </div>

              <form onSubmit={handleTotpVerify} className="space-y-4">
                <input
                  ref={totpInputRef}
                  type="text"
                  inputMode="numeric"
                  maxLength={6}
                  required
                  disabled={loading}
                  value={totpCode}
                  onChange={(e) => setTotpCode(e.target.value.replace(/[^0-9]/g, ''))}
                  placeholder="000000"
                  className="input-field text-center font-mono text-2xl tracking-[0.5em]"
                />

                <Button
                  type="submit"
                  loading={loading}
                  disabled={totpCode.length !== 6}
                  className="w-full"
                >
                  Verify and sign in
                </Button>

                <Button
                  type="button"
                  variant="ghost"
                  className="w-full"
                  disabled={loading}
                  onClick={() => {
                    setRequiresTotp(false);
                    setTotpCode('');
                    setPassword('');
                  }}
                >
                  Back to login
                </Button>
              </form>
            </>
          )}
        </div>

        <p className="mt-6 text-center text-xs text-muted">
          © {new Date().getFullYear()} Vidhya AI
        </p>
      </div>
    </div>
  );
}
