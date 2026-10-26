import { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { Lock } from 'lucide-react';
import api from '../../api';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { LogoStacked } from '../../components/brand/Logo';

export default function AdminResetPassword() {
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [token, setToken] = useState('');

  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const queryParams = new URLSearchParams(location.search);
    const tokenParam = queryParams.get('token');
    if (tokenParam) {
      setToken(tokenParam);
    } else {
      setError('Invalid or missing reset token.');
    }
  }, [location]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setLoading(true);
    setMessage('');
    setError('');

    try {
      await api.post('/auth/admin/reset-password', {
        token,
        new_password: password,
      });
      setMessage('Your password has been reset. Two-factor authentication was disabled.');
      setTimeout(() => navigate('/admin/login'), 3000);
    } catch (err: any) {
      setError(
        err.response?.data?.detail || 'Failed to reset password. The token may be expired.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-canvas p-6">
      <div className="w-full max-w-[420px]">
        <div className="mb-7 flex justify-center">
          <LogoStacked width={180} />
        </div>

        <div className="card p-8">
          <div className="mb-6">
            <h1 className="text-xl font-semibold text-ink">Set a new password</h1>
            <p className="mt-1 text-sm text-muted">
              Choose a strong password for your admin account.
            </p>
          </div>

          {error && (
            <div className="mb-5 rounded-lg border border-red-200 bg-danger-soft p-3 text-sm text-danger">
              {error}
            </div>
          )}

          {message ? (
            <div className="space-y-4">
              <div className="rounded-lg border border-green-200 bg-success-soft p-3 text-sm text-success">
                {message}
              </div>
              <p className="text-sm text-muted">Redirecting to login…</p>
              <Link
                to="/admin/login"
                className="inline-flex text-sm font-medium text-brand-500 hover:text-brand-600"
              >
                Go to login now
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="New password"
                id="password"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                icon={<Lock className="h-4 w-4" />}
              />

              <Input
                label="Confirm new password"
                id="confirmPassword"
                type="password"
                autoComplete="new-password"
                required
                minLength={8}
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••"
                icon={<Lock className="h-4 w-4" />}
              />

              <Button type="submit" loading={loading} disabled={!token} className="w-full">
                Reset password
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
