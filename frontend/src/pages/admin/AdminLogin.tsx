import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../../api';
import toast from 'react-hot-toast';
import { ShieldAlert, Lock, User, KeyRound, Loader2, ArrowRight } from 'lucide-react';

export default function AdminLogin() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  
  // 2FA state
  const [requiresTotp, setRequiresTotp] = useState(false);
  const [sessionToken, setSessionToken] = useState('');
  const [totpCode, setTotpCode] = useState('');
  
  const [loading, setLoading] = useState(false);
  const totpInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    // If the user already has a valid session cookie, redirect them automatically
    const checkAuth = async () => {
      try {
        await api.get('/analytics/dashboard');
        navigate('/admin/dashboard');
      } catch (err) {
        // Not logged in, stay on login page
      }
    };
    checkAuth();
  }, [navigate]);

  // Auto-focus TOTP input when it appears
  useEffect(() => {
    if (requiresTotp && totpInputRef.current) {
      totpInputRef.current.focus();
    }
  }, [requiresTotp]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const response = await api.post('/auth/admin/login', {
        username,
        password
      });
      
      if (response.data.requires_totp) {
        setRequiresTotp(true);
        setSessionToken(response.data.session_token);
        toast.success('Credentials verified. Please enter your 2FA code.');
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
        totp_code: totpCode
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
      setTotpCode(''); // Clear on failure
      if (totpInputRef.current) totpInputRef.current.focus();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden bg-slate-900">
      <div className="absolute top-[20%] left-[20%] w-[40%] h-[40%] bg-brand-500/10 rounded-full blur-[120px] -z-10"></div>
      <div className="absolute bottom-[10%] right-[10%] w-[30%] h-[30%] bg-purple-500/10 rounded-full blur-[100px] -z-10"></div>
      
      <div className="glass-card-dark max-w-md w-full p-8 relative overflow-hidden shadow-2xl border border-slate-700/50">
        {/* Top accent line */}
        <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-brand-500 via-purple-500 to-pink-500"></div>
        
        <div className="flex flex-col items-center mb-8">
          <div className="w-16 h-16 bg-slate-800 rounded-full flex items-center justify-center mb-4 shadow-[0_0_20px_rgba(59,130,246,0.15)] border border-slate-700">
            <ShieldAlert className="text-brand-400 w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">Admin Portal</h2>
          <p className="text-slate-400 text-sm mt-1">Secure Management Access</p>
        </div>

        <div className="relative">
          {/* We use a container that prevents height jumps during transition */}
          <div className={`transition-all duration-500 transform ${requiresTotp ? '-translate-x-full opacity-0 absolute inset-0 pointer-events-none' : 'translate-x-0 opacity-100'}`}>
            <form onSubmit={handleLogin} className="space-y-5">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Username</label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none transition-colors group-focus-within:text-brand-400 text-slate-500">
                    <User className="h-5 w-5" />
                  </div>
                  <input
                    type="text"
                    required
                    disabled={loading}
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="block w-full pl-11 pr-3 py-3 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:bg-slate-800 transition-all disabled:opacity-50"
                    placeholder="admin"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">Password</label>
                <div className="relative group">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none transition-colors group-focus-within:text-brand-400 text-slate-500">
                    <Lock className="h-5 w-5" />
                  </div>
                  <input
                    type="password"
                    required
                    disabled={loading}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="block w-full pl-11 pr-3 py-3 bg-slate-800/80 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-brand-500 focus:bg-slate-800 transition-all disabled:opacity-50"
                    placeholder="••••••••"
                  />
                </div>
                <div className="mt-2 text-right">
                  <a href="/admin/forgot-password" className="text-sm text-brand-400 hover:text-brand-300 transition-colors">
                    Forgot Password?
                  </a>
                </div>
              </div>

              <button
                type="submit"
                disabled={loading || !username || !password}
                className="w-full btn-primary mt-6 py-3 rounded-xl flex justify-center items-center shadow-[0_0_15px_rgba(59,130,246,0.3)] hover:shadow-[0_0_25px_rgba(59,130,246,0.5)] transition-all disabled:opacity-50 disabled:shadow-none"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin text-white" />
                ) : (
                  <>
                    Continue <ArrowRight className="w-4 h-4 ml-2" />
                  </>
                )}
              </button>
            </form>
          </div>

          <div className={`transition-all duration-500 transform ${!requiresTotp ? 'translate-x-full opacity-0 absolute inset-0 pointer-events-none' : 'translate-x-0 opacity-100'}`}>
            <form onSubmit={handleTotpVerify} className="space-y-5">
              <div className="text-center mb-6">
                <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-brand-500/10 mb-4">
                  <KeyRound className="text-brand-400 w-6 h-6" />
                </div>
                <h3 className="text-lg font-medium text-white">Two-Factor Authentication</h3>
                <p className="text-sm text-slate-400 mt-2 px-4">
                  Enter the 6-digit verification code generated by your authenticator app.
                </p>
              </div>

              <div>
                <div className="relative group">
                  <input
                    ref={totpInputRef}
                    type="text"
                    required
                    disabled={loading}
                    maxLength={6}
                    value={totpCode}
                    onChange={(e) => setTotpCode(e.target.value.replace(/[^0-9]/g, ''))}
                    className="block w-full px-4 py-4 bg-slate-800/90 border-2 border-slate-700 rounded-xl text-white focus:outline-none focus:ring-0 focus:border-brand-500 transition-all text-center tracking-[0.5em] font-mono text-2xl disabled:opacity-50"
                    placeholder="000000"
                  />
                </div>
              </div>
              
              <button
                type="submit"
                disabled={loading || totpCode.length !== 6}
                className="w-full btn-primary mt-6 py-3 rounded-xl flex justify-center items-center shadow-[0_0_15px_rgba(59,130,246,0.3)] hover:shadow-[0_0_25px_rgba(59,130,246,0.5)] transition-all disabled:opacity-50 disabled:shadow-none"
              >
                {loading ? (
                  <Loader2 className="w-5 h-5 animate-spin text-white" />
                ) : (
                  'Verify & Sign In'
                )}
              </button>
              
              <button 
                type="button"
                disabled={loading}
                onClick={() => {
                  setRequiresTotp(false);
                  setTotpCode('');
                  setPassword('');
                }}
                className="w-full py-3 text-sm text-slate-400 hover:text-white transition-colors"
              >
                Back to Login
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
