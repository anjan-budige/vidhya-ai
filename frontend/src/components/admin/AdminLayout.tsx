import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { 
  LayoutDashboard, 
  Database, 
  Settings, 
  LogOut, 
  CreditCard,
  Users,
  IndianRupee,
  Activity,
  Menu,
  X,
  Shield,
  Settings2
} from 'lucide-react';
import api from '../../api';

export default function AdminLayout() {
  const navigate = useNavigate();
  const [checkingAuth, setCheckingAuth] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);

  useEffect(() => {
    // Listen for unauthorized events to force logout
    const handleUnauthorized = () => navigate('/admin/login');
    window.addEventListener('auth:unauthorized', handleUnauthorized);

    // Initial check (ping a protected admin endpoint)
    api.get('/analytics/dashboard')
      .then(() => setCheckingAuth(false))
      .catch(() => navigate('/admin/login'));

    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [navigate]);

  const handleLogout = async () => {
    try {
      await api.post('/auth/logout');
    } catch (e) {}
    navigate('/admin/login');
  };

  if (checkingAuth) {
    return (
      <div className="min-h-screen bg-[#f4f7fa] flex">
        {/* Skeleton Sidebar */}
        <aside className="hidden md:flex w-64 bg-white border-r border-slate-200 flex-col fixed h-full z-10 p-4 shadow-sm">
          <div className="flex items-center mb-8 p-2">
            <div className="w-8 h-8 rounded-lg bg-slate-200 animate-pulse mr-3"></div>
            <div className="w-32 h-6 bg-slate-200 rounded-md animate-pulse"></div>
          </div>
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="flex items-center p-3 mb-2">
              <div className="w-5 h-5 bg-slate-200 rounded animate-pulse mr-3"></div>
              <div className="w-24 h-4 bg-slate-200 rounded animate-pulse"></div>
            </div>
          ))}
        </aside>
        {/* Skeleton Main Content */}
        <main className="flex-1 md:ml-64 p-4 md:p-8">
          <div className="w-48 h-8 bg-slate-200 rounded-md animate-pulse mb-8"></div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-2 h-64 bg-white rounded-2xl border border-slate-100 shadow-sm animate-pulse"></div>
            <div className="lg:col-span-1 h-64 bg-white rounded-2xl border border-slate-100 shadow-sm animate-pulse"></div>
          </div>
        </main>
      </div>
    );
  }

  const navItems = [
    { name: 'Dashboard', path: '/admin/dashboard', icon: LayoutDashboard },
    { name: 'System Status', path: '/admin/system-status', icon: Activity },
    { name: 'Knowledge Base', path: '/admin/knowledge-base', icon: Database },
    { name: 'Users', path: '/admin/users', icon: Users },
    { name: 'Plans', path: '/admin/plans', icon: CreditCard },
    { name: 'Payments', path: '/admin/payments', icon: IndianRupee },
    { name: 'Audit Logs', path: '/admin/audit-logs', icon: Shield },
    { name: 'API Settings', path: '/admin/api-settings', icon: Settings2 },
    { name: 'Settings', path: '/admin/settings', icon: Settings },
  ];

  return (
    <div className="min-h-screen bg-slate-50 font-sans flex">
      {/* Mobile Topbar */}
      <div className="md:hidden fixed top-0 left-0 right-0 h-16 bg-white/70 backdrop-blur-xl border-b border-white/20 z-20 flex items-center justify-between px-4 shadow-sm">
        <div className="flex items-center">
          <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-purple-600 rounded-xl mr-3 flex items-center justify-center shadow-lg text-white font-bold">V</div>
          <span className="font-bold text-lg text-slate-800 tracking-tight">Vidhya Hub</span>
        </div>
        <button onClick={() => setIsSidebarOpen(!isSidebarOpen)} className="p-2 text-slate-600">
          {isSidebarOpen ? <X size={24} /> : <Menu size={24} />}
        </button>
      </div>

      {/* Mobile Sidebar Overlay */}
      {isSidebarOpen && (
        <div 
          className="md:hidden fixed inset-0 bg-slate-900/20 backdrop-blur-sm z-30"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`fixed md:sticky top-0 h-screen w-64 bg-white/60 backdrop-blur-2xl border-r border-white/40 flex flex-col z-40 shadow-xl md:shadow-glass transition-transform duration-300 ease-in-out ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}>
        <div className="p-6 border-b border-slate-200/50 flex items-center justify-between md:justify-start">
          <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-purple-600 rounded-xl mr-3 flex items-center justify-center shadow-lg text-white font-bold text-lg">
            V
          </div>
          <span className="font-bold text-xl text-slate-800 tracking-tight">Vidhya Admin</span>
          <button className="md:hidden text-slate-500" onClick={() => setIsSidebarOpen(false)}>
            <X size={20} />
          </button>
        </div>
        
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.name}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center px-4 py-3 text-sm font-semibold rounded-xl transition-all duration-300 ${
                  isActive 
                    ? 'bg-gradient-to-r from-brand-50 to-purple-50 text-brand-700 shadow-sm border border-brand-100/50' 
                    : 'text-slate-500 hover:bg-white/60 hover:text-slate-800 hover:shadow-sm'
                }`
              }
            >
              <item.icon className="mr-3 h-5 w-5" />
              {item.name}
            </NavLink>
          ))}
        </nav>

        <div className="p-4 border-t border-slate-200/50">
          <button
            onClick={handleLogout}
            className="flex w-full items-center px-4 py-3 text-sm font-semibold text-slate-500 rounded-xl hover:bg-red-50 hover:text-red-600 hover:shadow-sm transition-all duration-300"
          >
            <LogOut className="mr-3 h-5 w-5" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 w-full md:w-auto md:ml-0 p-4 md:p-8 pt-20 md:pt-8 overflow-x-hidden">
        <Outlet />
      </main>
    </div>
  );
}
