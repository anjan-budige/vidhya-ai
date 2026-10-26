import { useState, useEffect } from 'react';
import { Settings, Save, ShieldCheck, Mail, Smartphone, CheckCircle2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';
import PlatformModeCard from '../../components/admin/PlatformModeCard';
import AccessSettingsCard from '../../components/admin/AccessSettingsCard';
import BotSettingsCard from '../../components/admin/BotSettingsCard';

type Tab = 'general' | 'security';

export default function AdminSettings() {
  const [activeTab, setActiveTab] = useState<Tab>('general');
  const [loading, setLoading] = useState(false);

  // 2FA State
  const [setupData, setSetupData] = useState<{ secret: string; qr_code_base64: string } | null>(null);
  const [totpCode, setTotpCode] = useState('');
  const [is2FAEnabled, setIs2FAEnabled] = useState(false);
  const [adminId, setAdminId] = useState<string | null>(null);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordLoading, setPasswordLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [emailLoading, setEmailLoading] = useState(false);

  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await api.get('/auth/admin/me');
        setIs2FAEnabled(res.data.totp_enabled);
        setAdminId(res.data.id);
        if (res.data.email) {
          setEmail(res.data.email);
        }
      } catch (err) {
        console.error("Failed to load admin profile", err);
      }
    };
    fetchProfile();
  }, []);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setTimeout(() => {
      toast.success('Settings saved successfully!');
      setLoading(false);
    }, 800);
  };

  const handleSetup2FA = async () => {
    try {
      const res = await api.get('/auth/admin/totp/setup');
      setSetupData(res.data);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to setup 2FA');
    }
  };

  const handleVerify2FA = async () => {
    try {
      await api.post('/auth/admin/totp/confirm', { code: totpCode });
      toast.success('2FA successfully enabled!');
      setIs2FAEnabled(true);
      setSetupData(null);
      setTotpCode('');
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Invalid TOTP code');
    }
  };

  const handleDisable2FA = async () => {
    if (!adminId) return;
    try {
      await api.post('/auth/admin/totp/disable', { admin_id: adminId });
      toast.success('2FA successfully disabled!');
      setIs2FAEnabled(false);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail) ? detail.map((d: any) => d.msg).join(', ') : (detail || 'Failed to disable 2FA');
      toast.error(msg);
    }
  };

  const handleUpdatePassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error('New passwords do not match');
      return;
    }
    if (currentPassword.length < 6) {
      toast.error('Current password must be at least 6 characters');
      return;
    }
    if (newPassword.length < 6) {
      toast.error('New password must be at least 6 characters');
      return;
    }
    setPasswordLoading(true);
    try {
      await api.post('/auth/admin/update-password', {
        current_password: currentPassword,
        new_password: newPassword
      });
      toast.success('Password updated successfully!');
      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail) 
        ? detail.map((d: any) => d.msg).join(', ') 
        : (typeof detail === 'string' ? detail : 'Failed to update password');
      toast.error(msg);
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleUpdateEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    setEmailLoading(true);
    try {
      await api.post('/auth/admin/update-email', { email });
      toast.success('Email updated successfully!');
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const msg = Array.isArray(detail) ? detail.map((d: any) => d.msg).join(', ') : (detail || 'Failed to update email');
      toast.error(msg);
    } finally {
      setEmailLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto space-y-6 animate-in fade-in duration-500">
      <div className="mb-2">
        <h1 className="text-xl font-semibold text-ink">Platform Settings</h1>
        <p className="mt-1 text-sm text-muted">Configure global application variables and security.</p>
      </div>

      <PlatformModeCard />
      <AccessSettingsCard />
      <BotSettingsCard />

      <div className="glass-card overflow-hidden">
        <div className="flex border-b border-slate-100 overflow-x-auto no-scrollbar">
          <button 
            onClick={() => setActiveTab('general')}
            className={`px-6 py-4 text-sm font-medium flex items-center transition-colors whitespace-nowrap ${activeTab === 'general' ? 'text-brand-600 border-b-2 border-brand-600 bg-brand-50/50' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'}`}
          >
            <Settings className="w-4 h-4 mr-2" /> General
          </button>
          <button 
            onClick={() => setActiveTab('security')}
            className={`px-6 py-4 text-sm font-medium flex items-center transition-colors whitespace-nowrap ${activeTab === 'security' ? 'text-brand-600 border-b-2 border-brand-600 bg-brand-50/50' : 'text-slate-500 hover:text-slate-700 hover:bg-slate-50'}`}
          >
            <ShieldCheck className="w-4 h-4 mr-2" /> Security
          </button>
        </div>

        <div className="p-8">
          {activeTab === 'general' && (
            <form onSubmit={handleSave} className="space-y-8 animate-in slide-in-from-right-4 duration-300">
            
            <div>
              <h3 className="text-lg font-bold text-slate-800 mb-4">Account Profile</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">Administrator Email</label>
                  <div className="relative">
                    <Mail className="w-5 h-5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                    <input 
                      type="email" 
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="admin@vidhya.com" 
                      className="w-full pl-10 pr-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500" 
                    />
                  </div>
                </div>
                <div className="flex items-end">
                  <button 
                    type="button" 
                    onClick={handleUpdateEmail}
                    disabled={emailLoading || !email}
                    className="btn-primary flex items-center px-6 py-2.5 rounded-xl shadow-sm disabled:opacity-50 h-[42px]"
                  >
                    {emailLoading ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                    ) : (
                      <Save className="w-4 h-4 mr-2" />
                    )}
                    Update Email
                  </button>
                </div>
              </div>
            </div>

            <div className="flex justify-end pt-4">
              <button 
                type="submit" 
                disabled={loading}
                className="btn-primary flex items-center px-6 py-2.5 rounded-xl shadow-sm"
              >
                {loading ? (
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                ) : (
                  <Save className="w-4 h-4 mr-2" />
                )}
                Save Settings
              </button>
            </div>
          </form>
          )}

          {activeTab === 'security' && (
            <div className="space-y-8 animate-in slide-in-from-right-4 duration-300">
              <div>
                <h3 className="text-lg font-bold text-slate-800 mb-2">Two-Factor Authentication (2FA)</h3>
                <p className="text-sm text-slate-500 mb-6">Enhance your admin account security by requiring an authenticator app (e.g. Google Authenticator, Authy) to login.</p>
                
                {is2FAEnabled ? (
                  <div className="bg-green-50 border border-green-200 rounded-xl p-6 flex items-center">
                    <CheckCircle2 className="w-8 h-8 text-green-500 mr-4" />
                    <div>
                      <h4 className="font-bold text-green-800">2FA is Enabled</h4>
                      <p className="text-sm text-green-600">Your account is secured with two-factor authentication.</p>
                      <button 
                        onClick={handleDisable2FA}
                        className="mt-4 px-4 py-2 bg-white border border-red-200 text-red-600 hover:bg-red-50 rounded-lg text-sm font-medium transition-colors"
                      >
                        Disable 2FA
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="bg-slate-50 border border-slate-200 rounded-xl p-6">
                    {!setupData ? (
                      <div className="flex items-center justify-between">
                        <div className="flex items-center">
                          <div className="w-12 h-12 bg-white rounded-full flex items-center justify-center shadow-sm border border-slate-200 mr-4">
                            <Smartphone className="w-6 h-6 text-slate-600" />
                          </div>
                          <div>
                            <h4 className="font-bold text-slate-800">Authenticator App</h4>
                            <p className="text-sm text-slate-500">Not configured</p>
                          </div>
                        </div>
                        <button 
                          onClick={handleSetup2FA}
                          className="btn-primary px-4 py-2 rounded-lg text-sm"
                        >
                          Setup 2FA
                        </button>
                      </div>
                    ) : (
                      <div className="space-y-6">
                        <h4 className="font-bold text-slate-800 border-b border-slate-200 pb-2">Setup Instructions</h4>
                        <ol className="list-decimal pl-5 space-y-2 text-sm text-slate-600 mb-6">
                          <li>Install an authenticator app like Google Authenticator or Authy on your phone.</li>
                          <li>Scan the QR code below with your app.</li>
                          <li>Enter the 6-digit code generated by the app to verify.</li>
                        </ol>
                        
                        <div className="flex flex-col md:flex-row gap-8 items-start">
                          <div className="p-4 bg-white rounded-xl shadow-sm border border-slate-200">
                            <img src={`data:image/png;base64,${setupData.qr_code_base64}`} alt="2FA QR Code" className="w-48 h-48" />
                          </div>
                          <div className="flex-1 w-full max-w-sm">
                            <label className="block text-sm font-medium text-slate-700 mb-1">Enter Verification Code</label>
                            <input 
                              type="text" 
                              maxLength={6}
                              value={totpCode}
                              onChange={(e) => setTotpCode(e.target.value.replace(/\D/g, ''))}
                              placeholder="123456" 
                              className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500 mb-4 text-center tracking-widest text-lg font-mono" 
                            />
                            <div className="flex space-x-3">
                              <button 
                                onClick={handleVerify2FA}
                                disabled={totpCode.length !== 6}
                                className="flex-1 btn-primary py-2.5 rounded-lg font-medium disabled:opacity-50"
                              >
                                Verify & Enable
                              </button>
                              <button 
                                onClick={() => { setSetupData(null); setTotpCode(''); }}
                                className="px-4 py-2 border border-slate-200 text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
                              >
                                Cancel
                              </button>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              <hr className="border-slate-100" />

              <div>
                <h3 className="text-lg font-bold text-slate-800 mb-2">Update Password</h3>
                <p className="text-sm text-slate-500 mb-6">Change your administrator login password.</p>
                <form onSubmit={handleUpdatePassword} className="space-y-4 max-w-md">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Current Password</label>
                    <input 
                      type="password" 
                      required
                      value={currentPassword}
                      onChange={e => setCurrentPassword(e.target.value)}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500" 
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">New Password</label>
                    <input 
                      type="password" 
                      required
                      minLength={8}
                      value={newPassword}
                      onChange={e => setNewPassword(e.target.value)}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500" 
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 mb-1">Confirm New Password</label>
                    <input 
                      type="password" 
                      required
                      minLength={8}
                      value={confirmPassword}
                      onChange={e => setConfirmPassword(e.target.value)}
                      className="w-full px-4 py-2 border border-slate-200 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-brand-500" 
                    />
                  </div>
                  <button 
                    type="submit"
                    disabled={passwordLoading || !currentPassword || !newPassword || !confirmPassword}
                    className="btn-primary mt-4 px-6 py-2 rounded-lg disabled:opacity-50 flex items-center"
                  >
                    {passwordLoading ? (
                      <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>
                    ) : (
                      <Save className="w-4 h-4 mr-2" />
                    )}
                    Update Password
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
