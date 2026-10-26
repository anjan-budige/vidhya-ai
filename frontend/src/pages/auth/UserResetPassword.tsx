import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Lock } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';
import AuthShell from '../../components/auth/AuthShell';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';

export default function UserResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const token = params.get('token') || '';
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      toast.error('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/reset-password', { token, new_password: password });
      toast.success('Password updated. Sign in with your new password.');
      navigate('/login');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Could not reset the password.');
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <AuthShell title="Invalid link" subtitle="This reset link is missing or expired.">
        <Link to="/forgot-password" className="btn-primary w-full">
          Request a new link
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Set a new password" subtitle="Choose a strong password for your account.">
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="New password"
          name="password"
          type="password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="At least 8 characters"
          icon={<Lock className="h-4 w-4" />}
        />
        <Input
          label="Confirm password"
          name="confirm"
          type="password"
          required
          minLength={8}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
          placeholder="Repeat your password"
          icon={<Lock className="h-4 w-4" />}
        />
        <Button type="submit" loading={loading} className="w-full">
          Update password
        </Button>
      </form>
    </AuthShell>
  );
}
