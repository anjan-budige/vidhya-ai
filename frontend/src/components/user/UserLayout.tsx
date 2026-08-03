import { Outlet } from 'react-router-dom';

// The /user route is always the Telegram Mini App.
// We do NOT gate on Telegram detection here because localtunnel's interstitial
// redirect destroys the URL hash (#tgWebAppData, #tgWebAppVersion) that Telegram injects.
// Auth is handled entirely inside UserDashboard via initData / session cookie.
export default function UserLayout() {
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <header className="bg-white/80 backdrop-blur-xl border-b border-white/20 px-4 py-3 flex items-center sticky top-0 z-20 shadow-sm transition-all">
        <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-purple-600 rounded-xl mr-3 flex items-center justify-center shadow-md text-white font-bold text-sm">
          V
        </div>
        <span className="font-bold text-lg text-slate-800 tracking-tight">Vidhya Hub</span>
      </header>
      <main className="flex-1 p-4 pb-20 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  );
}
