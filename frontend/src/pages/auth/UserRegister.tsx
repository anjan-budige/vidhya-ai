import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AtSign, Lock, Mail, Phone, User } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';
import AuthShell from '../../components/auth/AuthShell';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';

export default function UserRegister() {
  const navigate = useNavigate();
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [form, setForm] = useState({
    name: '',
    username: '',
    email: '',
    mobile: '',
    password: '',
    confirm: '',
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api
      .get('/config/public')
      .then((res) => setEnabled(!!res.data.registration_enabled))
      .catch(() => setEnabled(false));
  }, []);

  const update = (key: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [key]: e.target.value }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (form.password !== form.confirm) {
      toast.error('Passwords do not match.');
      return;
    }
    setLoading(true);
    try {
      await api.post('/auth/register', {
        username: form.username.toLowerCase(),
        name: form.name,
        email: form.email,
        mobile: form.mobile,
        password: form.password,
      });
      toast.success('Check your email for the 6-digit code.');
      navigate(`/verify-email?identifier=${encodeURIComponent(form.username.toLowerCase())}`);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      toast.error(typeof detail === 'string' ? detail : 'Registration failed.');
    } finally {
      setLoading(false);
    }
  };

  if (enabled === false) {
    return (
      <AuthShell
        title="Registration is closed"
        subtitle="This platform is not accepting public sign-ups. Ask an administrator for an account."
        footer={
          <Link to="/login" className="font-medium text-brand-500 hover:text-brand-600">
            Back to sign in
          </Link>
        }
      >
        <div className="rounded-lg border border-line bg-canvas p-4 text-sm text-muted">
          If you already have credentials, sign in with your username and password.
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create your account"
      subtitle="We will email a 6-digit code to verify your address."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-medium text-brand-500 hover:text-brand-600">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <Input
          label="Full name"
          name="name"
          required
          value={form.name}
          onChange={update('name')}
          placeholder="Your name"
          icon={<User className="h-4 w-4" />}
        />
        <Input
          label="Username"
          name="username"
          required
          minLength={3}
          maxLength={30}
          value={form.username}
          onChange={(e) =>
            setForm((p) => ({
              ...p,
              username: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, ''),
            }))
          }
          placeholder="yourname"
          hint="Lowercase letters, numbers and underscore."
          icon={<AtSign className="h-4 w-4" />}
        />
        <Input
          label="Email"
          name="email"
          type="email"
          required
          value={form.email}
          onChange={update('email')}
          placeholder="you@example.com"
          icon={<Mail className="h-4 w-4" />}
        />
        <Input
          label="Mobile number"
          name="mobile"
          type="tel"
          required
          value={form.mobile}
          onChange={update('mobile')}
          placeholder="+91 98765 43210"
          icon={<Phone className="h-4 w-4" />}
        />
        <Input
          label="Password"
          name="password"
          type="password"
          required
          minLength={8}
          value={form.password}
          onChange={update('password')}
          placeholder="At least 8 characters"
          icon={<Lock className="h-4 w-4" />}
        />
        <Input
          label="Confirm password"
          name="confirm"
          type="password"
          required
          minLength={8}
          value={form.confirm}
          onChange={update('confirm')}
          placeholder="Repeat your password"
          icon={<Lock className="h-4 w-4" />}
        />
        <Button type="submit" loading={loading} className="w-full">
          Create account
        </Button>
      </form>
    </AuthShell>
  );
}
