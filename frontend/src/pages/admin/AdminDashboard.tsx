import { useState, useEffect } from 'react';
import api from '../../api';
import toast from 'react-hot-toast';

export default function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const response = await api.get('/analytics/dashboard');
        // response.data has total_revenue, total_users, active_subscriptions, total_conversations, etc.
        setStats(response.data);
      } catch (err) {
        toast.error('Failed to fetch dashboard stats');
      } finally {
        setLoading(false);
      }
    };
    fetchStats();
  }, []);



  if (loading) {
    return (
      <div className="flex flex-col h-full max-w-7xl mx-auto space-y-6">
        <div className="flex items-center justify-between mb-2">
          <div className="w-48 h-8 bg-slate-200 rounded-md animate-pulse"></div>
          <div className="flex space-x-6">
            <div className="w-64 h-10 bg-slate-200 rounded-xl animate-pulse"></div>
            <div className="w-10 h-10 bg-slate-200 rounded-full animate-pulse"></div>
          </div>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 h-80 bg-white rounded-2xl border border-slate-100 shadow-sm animate-pulse"></div>
          <div className="lg:col-span-1 h-80 bg-white rounded-2xl border border-slate-100 shadow-sm animate-pulse"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-4 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Dashboard Overview</h1>
          <p className="text-sm text-slate-500">Live telemetry and system statistics</p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6">
        
        {/* Users Card */}
        <div className="glass-card p-6 border-l-4 border-l-brand-500">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Users</h2>
            <div className="p-2 bg-brand-50 text-brand-600 rounded-lg">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            </div>
          </div>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-3xl font-bold text-slate-800">{stats?.total_users || 0}</div>
              <div className="text-sm font-medium text-blue-600 mt-1">{stats?.active_users_today || 0} active today</div>
            </div>
          </div>
        </div>

        {/* Subscriptions & Revenue Card */}
        <div className="glass-card p-6 border-l-4 border-l-green-500">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">Revenue</h2>
            <div className="p-2 bg-green-50 text-green-600 rounded-lg">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-3xl font-bold text-slate-800">₹{stats?.total_revenue?.toFixed(2) || '0.00'}</div>
              <div className="text-sm font-medium text-green-600 mt-1">₹{stats?.revenue_this_month?.toFixed(2) || '0.00'} this month</div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-100 flex justify-between items-center text-sm">
            <span className="text-slate-500">Active Subs</span>
            <span className="font-bold text-slate-700">{stats?.active_subscriptions || 0}</span>
          </div>
        </div>

        {/* AI Usage Card */}
        <div className="glass-card p-6 border-l-4 border-l-purple-500">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">AI Usage (Today)</h2>
            <div className="p-2 bg-purple-50 text-purple-600 rounded-lg">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
          </div>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-3xl font-bold text-slate-800">{stats?.total_messages_today || 0}</div>
              <div className="text-sm font-medium text-slate-500 mt-1">Messages</div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-100 flex justify-between items-center text-sm">
            <span className="text-slate-500">Tokens Processed</span>
            <span className="font-bold text-slate-700">{stats?.total_tokens_today?.toLocaleString() || 0}</span>
          </div>
        </div>

        {/* Conversations & Docs Card */}
        <div className="glass-card p-6 border-l-4 border-l-orange-500">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-500 uppercase tracking-wider">System State</h2>
            <div className="p-2 bg-orange-50 text-orange-600 rounded-lg">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
          </div>
          <div className="flex items-end justify-between">
            <div>
              <div className="text-3xl font-bold text-slate-800">{stats?.total_conversations || 0}</div>
              <div className="text-sm font-medium text-slate-500 mt-1">Total Threads</div>
            </div>
          </div>
          <div className="mt-4 pt-4 border-t border-slate-100 flex flex-col space-y-2 text-sm">
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Active Threads</span>
              <span className="font-bold text-orange-600">{stats?.active_conversations || 0}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-slate-500">Knowledge Docs</span>
              <span className="font-bold text-slate-700">{stats?.total_documents || 0}</span>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}
