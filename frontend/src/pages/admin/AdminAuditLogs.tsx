import { useEffect, useState } from 'react';
import { Shield, Clock, Search, Server, User, FileText, AlertTriangle, RefreshCw, LogIn } from 'lucide-react';
import api from '../../api';

interface AuditLog {
  id: string;
  admin_id: string | null;
  admin_username: string | null;
  action: string;
  resource_type: string | null;
  resource_id: string | null;
  details: any;
  ip_address: string | null;
  created_at: string;
}

export default function AdminAuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const pageSize = 100;

  useEffect(() => {
    fetchLogs(page);
  }, [page]);

  const fetchLogs = async (currentPage: number = 1) => {
    try {
      setLoading(true);
      const res = await api.get(`/audit/?page=${currentPage}&page_size=${pageSize}`);
      setLogs(res.data.items);
      setTotal(res.data.total);
      setError(null);
    } catch (err: any) {
      setError(err.message || 'Failed to fetch audit logs');
    } finally {
      setLoading(false);
    }
  };

  const getActionBadge = (action: string) => {
    if (action.includes('login')) return 'bg-blue-50 text-blue-700 border-blue-200';
    if (action.includes('created') || action.includes('uploaded')) return 'bg-green-50 text-green-700 border-green-200';
    if (action.includes('deleted') || action.includes('banned')) return 'bg-red-50 text-red-700 border-red-200';
    if (action.includes('updated') || action.includes('assigned')) return 'bg-amber-50 text-amber-700 border-amber-200';
    return 'bg-slate-100 text-slate-600 border-slate-200';
  };

  const getResourceIcon = (type: string | null) => {
    switch (type) {
      case 'user': return <User className="w-4 h-4 text-brand-500" />;
      case 'plan': return <Shield className="w-4 h-4 text-brand-500" />;
      case 'document': return <FileText className="w-4 h-4 text-amber-500" />;
      case 'subscription': return <Server className="w-4 h-4 text-green-500" />;
      case 'admin': return <LogIn className="w-4 h-4 text-blue-500" />;
      default: return <AlertTriangle className="w-4 h-4 text-slate-400" />;
    }
  };

  const filteredLogs = logs.filter(log =>
    !search ||
    log.action.toLowerCase().includes(search.toLowerCase()) ||
    (log.admin_username || '').toLowerCase().includes(search.toLowerCase()) ||
    (log.resource_type || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="flex flex-col h-full max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-semibold text-ink">
            <Shield className="h-5 w-5 text-brand-500" />
            Security Audit Logs
          </h1>
          <p className="mt-1 text-sm text-muted">
            Immutable record of all administrative actions and system events.
          </p>
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <div className="relative flex-1 sm:flex-none">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 h-4 w-4" />
            <input
              type="text"
              placeholder="Search logs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-10 pr-4 py-2 bg-white rounded-xl border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 shadow-sm w-full sm:w-64"
            />
          </div>
          <button
            onClick={() => fetchLogs(page)}
            className="flex items-center text-sm bg-white border border-slate-200 px-4 py-2 rounded-xl hover:bg-slate-50 font-medium text-slate-600 shadow-sm transition-colors"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {[
          { label: 'Total Events', value: total, color: 'text-slate-800' },
          { label: 'Login Events', value: logs.filter(l => l.action.includes('login')).length, color: 'text-blue-600' },
          { label: 'Create Events', value: logs.filter(l => l.action.includes('created') || l.action.includes('uploaded')).length, color: 'text-green-600' },
          { label: 'Delete Events', value: logs.filter(l => l.action.includes('deleted') || l.action.includes('banned')).length, color: 'text-red-600' },
        ].map(stat => (
          <div key={stat.label} className="glass-card p-4">
            <p className="text-xs text-slate-500 font-medium mb-1">{stat.label}</p>
            <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      <div className="glass-card overflow-visible">
        {loading ? (
          <div className="p-12 flex flex-col items-center justify-center text-slate-400">
            <div className="w-10 h-10 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin mb-4" />
            Loading audit logs...
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <AlertTriangle className="w-10 h-10 text-red-400 mx-auto mb-3" />
            <p className="text-red-500 font-medium">{error}</p>
            <button onClick={() => fetchLogs(page)} className="mt-4 text-sm text-brand-600 hover:underline">Try again</button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse min-w-[900px]">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-100">
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Timestamp</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Admin</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Action</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Resource</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">Details</th>
                  <th className="py-4 px-6 text-xs font-semibold text-slate-500 uppercase tracking-wider">IP Address</th>
                </tr>
              </thead>
              <tbody>
                {filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-16 text-center">
                      <Shield className="w-10 h-10 text-slate-200 mx-auto mb-3" />
                      <p className="text-slate-500 font-medium">No audit logs found</p>
                      <p className="text-xs text-slate-400 mt-1">Actions performed by admins will appear here.</p>
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map((log) => (
                    <tr key={log.id} className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
                      <td className="py-4 px-6 whitespace-nowrap">
                        <div className="flex items-center gap-2 text-slate-500 text-sm">
                          <Clock className="w-3.5 h-3.5 shrink-0" />
                          <div>
                            <p className="text-slate-700 font-medium text-xs">
                              {new Date(log.created_at).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                            </p>
                            <p className="text-slate-400 text-xs">
                              {new Date(log.created_at).toLocaleTimeString('en-IN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                            </p>
                          </div>
                        </div>
                      </td>

                      <td className="py-4 px-6 whitespace-nowrap">
                        {log.admin_username ? (
                          <div className="flex items-center gap-2">
                            <div className="w-7 h-7 rounded-full bg-brand-100 text-brand-600 flex items-center justify-center font-bold text-xs shrink-0">
                              {log.admin_username.charAt(0).toUpperCase()}
                            </div>
                            <span className="font-medium text-slate-800 text-sm">{log.admin_username}</span>
                          </div>
                        ) : (
                          <span className="text-slate-400 text-sm italic">System</span>
                        )}
                      </td>

                      <td className="py-4 px-6 whitespace-nowrap">
                        <span className={`inline-flex px-2.5 py-1 rounded-full text-xs font-medium border ${getActionBadge(log.action)}`}>
                          {log.action}
                        </span>
                      </td>

                      <td className="py-4 px-6 whitespace-nowrap">
                        <div className="flex items-center gap-2 text-sm">
                          {getResourceIcon(log.resource_type)}
                          <span className="capitalize text-slate-700">{log.resource_type || 'System'}</span>
                          {log.resource_id && (
                            <span className="text-slate-400 text-xs font-mono" title={log.resource_id}>
                              #{log.resource_id.split('-')[0]}
                            </span>
                          )}
                        </div>
                      </td>

                      <td className="py-4 px-6">
                        {log.details && Object.keys(log.details).length > 0 ? (
                          <pre className="text-xs text-slate-500 bg-slate-50 p-2 rounded-lg border border-slate-100 overflow-x-auto max-w-[200px] font-mono">
                            {JSON.stringify(log.details, null, 2)}
                          </pre>
                        ) : (
                          <span className="text-slate-400 text-xs">—</span>
                        )}
                      </td>

                      <td className="py-4 px-6 whitespace-nowrap text-slate-500 font-mono text-xs">
                        {log.ip_address || (
                          <span className="text-slate-400 italic">Internal</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            
            {total > pageSize && (
              <div className="flex items-center justify-between px-6 py-4 border-t border-slate-100 bg-white">
                <div className="text-sm text-slate-500">
                  Showing <span className="font-medium text-slate-700">{(page - 1) * pageSize + 1}</span> to <span className="font-medium text-slate-700">{Math.min(page * pageSize, total)}</span> of <span className="font-medium text-slate-700">{total}</span> results
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="px-3 py-1.5 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(p => p + 1)}
                    disabled={page * pageSize >= total}
                    className="px-3 py-1.5 text-sm font-medium text-slate-600 bg-white border border-slate-200 rounded-lg hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
