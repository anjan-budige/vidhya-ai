import { useState, useEffect } from 'react';
import { Server, Database, Box, CheckCircle2, XCircle, RefreshCw, Activity, Cpu, HardDrive } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';

export default function AdminSystemStatus() {
  const [health, setHealth] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const fetchHealth = async () => {
    setRefreshing(true);
    try {
      const response = await api.get('/analytics/system-health');
      setHealth(response.data);
    } catch (err: any) {
      if (err.response?.data) {
        setHealth(err.response.data);
      } else {
        toast.error('Failed to fetch system status');
      }
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds: number) => {
    if (!seconds) return '0s';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    
    if (h > 0) return `${h}h ${m}m`;
    if (m > 0) return `${m}m ${s}s`;
    return `${s}s`;
  };

  const getStatusIcon = (status: string) => {
    if (status === 'connected' || status === 'healthy' || status === 'online') {
      return <CheckCircle2 className="w-6 h-6 text-green-500" />;
    }
    return <XCircle className="w-6 h-6 text-red-500" />;
  };

  const getStatusColor = (status: string) => {
    if (status === 'connected' || status === 'healthy' || status === 'online') {
      return 'border-green-200 bg-green-50/30';
    }
    return 'border-red-200 bg-red-50/30';
  };

  if (loading && !health) {
    return (
      <div className="flex justify-center items-center h-full">
        <div className="w-10 h-10 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin"></div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-800">System Status</h1>
          <p className="text-sm text-slate-500">Live health monitoring of infrastructure components.</p>
        </div>
        
        <button 
          onClick={fetchHealth} 
          disabled={refreshing}
          className="flex items-center text-sm border border-slate-200 px-4 py-2 rounded-xl hover:bg-slate-50 font-medium text-slate-600 transition-colors shadow-sm bg-white disabled:opacity-50"
        >
          <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? 'animate-spin' : ''}`} /> 
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* API Server Card */}
        <div className="glass-card p-6 flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between mb-4">
              <div className="flex items-center space-x-3">
                <div className="p-3 bg-brand-50 text-brand-600 rounded-xl">
                  <Server className="w-6 h-6" />
                </div>
                <div>
                  <h2 className="text-lg font-bold text-slate-800">Core API Server</h2>
                  <p className="text-sm text-slate-500">{health?.service} v{health?.version}</p>
                </div>
              </div>
              {getStatusIcon(health?.status || 'error')}
            </div>
            
            <div className="grid grid-cols-2 gap-4 mt-6">
              <div className="bg-slate-50 rounded-xl p-4">
                <div className="text-xs text-slate-500 font-medium mb-1">Environment</div>
                <div className="font-semibold text-slate-700 capitalize">{health?.environment || 'Unknown'}</div>
              </div>
              <div className="bg-slate-50 rounded-xl p-4">
                <div className="text-xs text-slate-500 font-medium mb-1">Uptime</div>
                <div className="font-semibold text-slate-700">{formatUptime(health?.uptime_seconds)}</div>
              </div>
            </div>
          </div>
          <div className="mt-6 pt-4 border-t border-slate-100 flex items-center justify-between text-xs text-slate-400">
            <span>Last checked: {new Date(health?.timestamp).toLocaleTimeString()}</span>
            <span className="flex items-center"><Activity className="w-3 h-3 mr-1" /> Live</span>
          </div>
        </div>

        {/* PostgreSQL Database */}
        <div className={`glass-card p-6 border-2 transition-colors duration-300 ${getStatusColor(health?.services?.postgres?.status)}`}>
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="p-3 bg-blue-50 text-blue-600 rounded-xl">
                <Database className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-800">PostgreSQL</h2>
                <p className="text-sm text-slate-500">Primary Database (pgvector)</p>
              </div>
            </div>
            {getStatusIcon(health?.services?.postgres?.status)}
          </div>
          
          <div className="grid grid-cols-2 gap-4 mt-6">
            <div className="bg-white/60 rounded-xl p-4">
              <div className="text-xs text-slate-500 font-medium mb-1 flex items-center">
                <Activity className="w-3 h-3 mr-1" /> Latency
              </div>
              <div className="font-semibold text-slate-700">
                {health?.services?.postgres?.latency_ms ? `${health.services.postgres.latency_ms} ms` : 'N/A'}
              </div>
            </div>
            <div className="bg-white/60 rounded-xl p-4">
              <div className="text-xs text-slate-500 font-medium mb-1 flex items-center">
                <Box className="w-3 h-3 mr-1" /> Total Tables
              </div>
              <div className="font-semibold text-slate-700">{health?.services?.postgres?.tables || 'Unknown'}</div>
            </div>
          </div>
          
          {health?.services?.postgres?.error && (
            <div className="mt-4 p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-100 font-mono">
              {health.services.postgres.error}
            </div>
          )}
        </div>

        {/* Redis Cache */}
        <div className={`glass-card p-6 border-2 transition-colors duration-300 ${getStatusColor(health?.services?.redis?.status)}`}>
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="p-3 bg-red-50 text-red-600 rounded-xl">
                <HardDrive className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-800">Redis Cache</h2>
                <p className="text-sm text-slate-500">Rate limiting & Session storage</p>
              </div>
            </div>
            {getStatusIcon(health?.services?.redis?.status)}
          </div>
          
          <div className="grid grid-cols-2 gap-4 mt-6">
            <div className="bg-white/60 rounded-xl p-4">
              <div className="text-xs text-slate-500 font-medium mb-1 flex items-center">
                <Activity className="w-3 h-3 mr-1" /> Latency
              </div>
              <div className="font-semibold text-slate-700">
                {health?.services?.redis?.latency_ms ? `${health.services.redis.latency_ms} ms` : 'N/A'}
              </div>
            </div>
            <div className="bg-white/60 rounded-xl p-4">
              <div className="text-xs text-slate-500 font-medium mb-1 flex items-center">
                <Cpu className="w-3 h-3 mr-1" /> Memory Used
              </div>
              <div className="font-semibold text-slate-700">{health?.services?.redis?.used_memory || 'Unknown'}</div>
            </div>
          </div>
          
          {health?.services?.redis?.error && (
            <div className="mt-4 p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-100 font-mono">
              {health.services.redis.error}
            </div>
          )}
        </div>

        {/* Mistral API */}
        <div className={`glass-card p-6 border-2 transition-colors duration-300 ${getStatusColor(health?.services?.mistral?.status)}`}>
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="p-3 bg-purple-50 text-purple-600 rounded-xl">
                <Cpu className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-800">Mistral API Engine</h2>
                <p className="text-sm text-slate-500">Inference & Embeddings</p>
              </div>
            </div>
            {getStatusIcon(health?.services?.mistral?.status)}
          </div>
          
          <div className="grid grid-cols-2 gap-4 mt-6">
            <div className="bg-white/60 rounded-xl p-4">
              <div className="text-xs text-slate-500 font-medium mb-1 flex items-center">
                <Activity className="w-3 h-3 mr-1" /> Latency
              </div>
              <div className="font-semibold text-slate-700">
                {health?.services?.mistral?.latency_ms ? `${health.services.mistral.latency_ms} ms` : 'N/A'}
              </div>
            </div>
            <div className="bg-white/60 rounded-xl p-4">
              <div className="text-xs text-slate-500 font-medium mb-1 flex items-center">
                <Box className="w-3 h-3 mr-1" /> Models Discovered
              </div>
              <div className="font-semibold text-slate-700 truncate" title={health?.services?.mistral?.models_loaded?.join(', ')}>
                {health?.services?.mistral?.models_loaded?.length > 0 
                  ? `${health.services.mistral.model_count} total models`
                  : '0 models'}
              </div>
            </div>
          </div>
          
          {health?.services?.mistral?.error && (
            <div className="mt-4 p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-100 font-mono">
              {health.services.mistral.error}
            </div>
          )}
        </div>

      </div>
      
      {/* ── Additional Services Row ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
        {/* Celery Workers */}
        <div className={`glass-card p-6 border-2 transition-colors duration-300 ${getStatusColor(health?.services?.celery?.status)}`}>
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center space-x-3">
              <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl">
                <Activity className="w-6 h-6" />
              </div>
              <div>
                <h2 className="text-lg font-bold text-slate-800">Celery Workers</h2>
                <p className="text-sm text-slate-500">Background Tasks & Processing</p>
              </div>
            </div>
            {getStatusIcon(health?.services?.celery?.status)}
          </div>
          
          <div className="grid grid-cols-2 gap-4 mt-6">
            <div className="bg-white/60 rounded-xl p-4">
              <div className="text-xs text-slate-500 font-medium mb-1 flex items-center">
                <Activity className="w-3 h-3 mr-1" /> Latency
              </div>
              <div className="font-semibold text-slate-700">
                {health?.services?.celery?.latency_ms ? `${health.services.celery.latency_ms} ms` : 'N/A'}
              </div>
            </div>
            <div className="bg-white/60 rounded-xl p-4">
              <div className="text-xs text-slate-500 font-medium mb-1 flex items-center">
                <Server className="w-3 h-3 mr-1" /> Active Workers
              </div>
              <div className="font-semibold text-slate-700">{health?.services?.celery?.workers_online ?? '0'}</div>
            </div>
          </div>
          
          {health?.services?.celery?.error && (
            <div className="mt-4 p-3 bg-red-50 text-red-700 text-xs rounded-lg border border-red-100 font-mono">
              {health.services.celery.error}
            </div>
          )}
          {health?.services?.celery?.message && (
            <div className="mt-4 p-3 bg-yellow-50 text-yellow-700 text-xs rounded-lg border border-yellow-100 font-mono">
              {health.services.celery.message}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
