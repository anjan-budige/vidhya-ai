import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
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
import AdminAiProviders from './pages/admin/AdminAiProviders';
import AdminAuditLogs from './pages/admin/AdminAuditLogs';
import Chat from './pages/user/ChatApp';
import UserPlans from './pages/user/UserPlans';
import UserApiKeys from './pages/user/UserApiKeys';
import UserSettings from './pages/user/UserSettings';
import PaymentStatus from './pages/user/PaymentStatus';
import UserLogin from './pages/auth/UserLogin';
import UserRegister from './pages/auth/UserRegister';
import VerifyEmail from './pages/auth/VerifyEmail';
import UserForgotPassword from './pages/auth/UserForgotPassword';
import UserResetPassword from './pages/auth/UserResetPassword';
import AdminLayout from './components/admin/AdminLayout';
import UserLayout from './components/user/UserAppLayout';
import { UserProvider } from './contexts/UserContext';

function UserApp() {
  return (
    <UserProvider>
      <UserLayout />
    </UserProvider>
  );
}

function App() {
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
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<UserLogin />} />
        <Route path="/register" element={<UserRegister />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        <Route path="/forgot-password" element={<UserForgotPassword />} />
        <Route path="/reset-password" element={<UserResetPassword />} />
        <Route path="/payment/status" element={<PaymentStatus />} />
        <Route path="/admin/login" element={<AdminLogin />} />
        <Route path="/admin/forgot-password" element={<AdminForgotPassword />} />
        <Route path="/admin/reset-password" element={<AdminResetPassword />} />

        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<Navigate to="/admin/dashboard" replace />} />
          <Route path="dashboard" element={<AdminDashboard />} />
          <Route path="knowledge-base" element={<AdminKnowledgeBase />} />
          <Route path="users" element={<AdminUsers />} />
          <Route path="plans" element={<AdminPlans />} />
          <Route path="payments" element={<AdminPayments />} />
          <Route path="system-status" element={<AdminSystemStatus />} />
          <Route path="audit-logs" element={<AdminAuditLogs />} />
          <Route path="ai-providers" element={<AdminAiProviders />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>

        <Route element={<UserApp />}>
          <Route path="/chat/:conversationId?" element={<Chat />} />
          <Route path="/plans" element={<UserPlans />} />
          <Route path="/api-keys" element={<UserApiKeys />} />
          <Route path="/profile" element={<UserSettings />} />
        </Route>

        <Route path="/keys" element={<Navigate to="/api-keys" replace />} />
        <Route path="/settings" element={<Navigate to="/profile" replace />} />
        <Route path="/account" element={<Navigate to="/profile" replace />} />
        <Route path="/user" element={<Navigate to="/chat" replace />} />
        <Route path="/user/dashboard" element={<Navigate to="/chat" replace />} />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
