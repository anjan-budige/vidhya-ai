import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { useEffect } from 'react';
import { Toaster } from 'react-hot-toast';
import Landing from './pages/Landing';
import AdminLogin from './pages/admin/AdminLogin';
import AdminDashboard from './pages/admin/AdminDashboard';
import AdminForgotPassword from './pages/admin/AdminForgotPassword';
import AdminResetPassword from './pages/admin/AdminResetPassword';
import AdminKnowledgeBase from './pages/admin/AdminKnowledgeBase';
import AdminUsers from './pages/admin/AdminUsers';
import AdminPlans from './pages/admin/AdminPlans';
import AdminPayments from './pages/admin/AdminPayments';
import AdminSystemStatus from './pages/admin/AdminSystemStatus';
import AdminSettings from './pages/admin/AdminSettings';
import AdminApiSettings from './pages/admin/AdminApiSettings';
import AdminAuditLogs from './pages/admin/AdminAuditLogs';
import UserDashboard from './pages/user/UserDashboard';
import PaymentStatus from './pages/user/PaymentStatus';
import AdminLayout from './components/admin/AdminLayout';
import UserLayout from './components/user/UserLayout';
import twa from '@twa-dev/sdk';

function App() {

  useEffect(() => {
    // Signal Telegram WebApp is ready (if in Telegram environment)
    try {
      const win = window as any;
      if (win.Telegram?.WebApp?.ready) win.Telegram.WebApp.ready();
      if (win.Telegram?.WebApp?.expand) win.Telegram.WebApp.expand();
    } catch {}
    try { twa.ready(); } catch {}
    try { twa.expand(); } catch {}
  }, []);

  return (
    <BrowserRouter>
      <Toaster 
        position="top-right" 
        toastOptions={{
          duration: 4000,
          style: {
            background: '#1e293b',
            color: '#fff',
            borderRadius: '12px',
            border: '1px solid #334155',
            boxShadow: '0 10px 25px -5px rgba(0, 0, 0, 0.3)',
          },
          success: {
            iconTheme: {
              primary: '#22c55e',
              secondary: '#fff',
            },
          },
          error: {
            iconTheme: {
              primary: '#ef4444',
              secondary: '#fff',
            },
          },
        }}
      />
      <Routes>
        {/* Public Routes */}
        <Route path="/" element={<Landing />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin/forgot-password" element={<AdminForgotPassword />} />
        <Route path="/admin/reset-password" element={<AdminResetPassword />} />

        {/* Admin Routes - Wrapped in Layout */}
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="dashboard" element={<AdminDashboard />} />
          <Route path="knowledge-base" element={<AdminKnowledgeBase />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="plans" element={<AdminPlans />} />
          <Route path="payments" element={<AdminPayments />} />
          <Route path="system-status" element={<AdminSystemStatus />} />
          <Route path="audit-logs" element={<AdminAuditLogs />} />
          <Route path="api-settings" element={<AdminApiSettings />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>

        {/* User Routes - Mini App View */}
        <Route path="/user" element={<UserLayout />}>
          <Route index element={<Navigate to="/user/dashboard" replace />} />
          <Route path="dashboard" element={<UserDashboard />} />
        </Route>

        <Route path="/payment/status" element={<PaymentStatus />} />

        {/* Fallback */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
