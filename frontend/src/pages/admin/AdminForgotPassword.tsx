import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Mail } from 'lucide-react';
import api from '../../api';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { LogoStacked } from '../../components/brand/Logo';

export default function AdminForgotPassword() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setMessage('');
    setError('');

    try {
      const response = await api.post('/auth/admin/forgot-password', { email });
      setMessage(response.data.message || 'A reset link has been sent to your email.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to send reset link. Please try again.');
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
            <h1 className="text-xl font-semibold text-ink">Forgot password</h1>
            <p className="mt-1 text-sm text-muted">
              Enter the email linked to your admin account and we will send a reset link.
            </p>
          </div>

          {error && (
            <div className="mb-5 rounded-lg border border-red-200 bg-danger-soft p-3 text-sm text-danger">
              {error}
            </div>
          )}

          {message ? (
            <div className="space-y-5">
              <div className="rounded-lg border border-green-200 bg-success-soft p-3 text-sm text-success">
                {message}
              </div>
              <Link
                to="/admin/login"
                className="inline-flex text-sm font-medium text-brand-500 hover:text-brand-600"
              >
                Return to login
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <Input
                label="Email address"
                id="email"
                type="email"
                autoComplete="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="admin@yourdomain.com"
                icon={<Mail className="h-4 w-4" />}
              />

              <Button type="submit" loading={loading} className="w-full">
                Send reset link
              </Button>
            </form>
          )}

          {!message && (
            <div className="mt-5 text-center">
              <Link to="/admin/login" className="text-xs font-medium text-muted hover:text-ink">
                Back to login
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
