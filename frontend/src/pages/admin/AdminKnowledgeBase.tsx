import { useState, useEffect } from 'react';
import { Upload, FileText, Trash2, Database, Search, Download } from 'lucide-react';
import api from '../../api';
import toast from 'react-hot-toast';

export default function AdminKnowledgeBase() {
  const [files, setFiles] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [tags, setTags] = useState('');
  const [reindex, setReindex] = useState<any>(null);
  
  const fetchDocuments = async (silent = false) => {
    try {
      const response = await api.get('/documents/');
      setFiles(response.data);
    } catch (err) {
      if (!silent) toast.error('Failed to fetch documents');
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const fetchReindex = async () => {
    try {
      const response = await api.get('/admin/ai/reindex/status');
      setReindex(response.data);
    } catch {
      // Status is informational.
    }
  };

  useEffect(() => {
    fetchDocuments();
    fetchReindex();

    const reindexPoll = setInterval(fetchReindex, 5000);

    // Auto-poll every 5 seconds if any document is processing
    const interval = setInterval(() => {
      setFiles(currentFiles => {
        const needsPolling = currentFiles.some(f => f.status === 'chunked' || f.status === 'processing' || f.status === 'uploaded');
        if (needsPolling) {
          fetchDocuments(true);
        }
        return currentFiles;
      });
    }, 5000);
    
    return () => {
      clearInterval(interval);
      clearInterval(reindexPoll);
    };
  }, []);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    
    setUploading(true);
    const formData = new FormData();
    formData.append('file', e.target.files[0]);
    formData.append('subject', subject || 'General');
    if (description) formData.append('description', description);
    if (tags) formData.append('tags', tags);
    
    try {
      await api.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      toast.success('Document uploaded successfully. Processing in background...');
      await fetchDocuments();
    } catch (err) {
      toast.error('Failed to upload document');
    } finally {
      setUploading(false);
      if (e.target) e.target.value = '';
    }
  };

  const handleDelete = async (id: string) => {
    if (!window.confirm('Are you sure you want to delete this document?')) return;
    try {
      await api.delete(`/documents/${id}`);
      setFiles(files.filter(f => f.id !== id));
      toast.success('Document deleted successfully');
    } catch (err) {
      toast.error('Failed to delete document');
    }
  };

  const handleDownload = async (id: string, filename: string) => {
    try {
      const response = await api.get(`/documents/${id}/download`, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      
      link.parentNode?.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      toast.success('Download started');
    } catch (err) {
      toast.error('Failed to download document');
    }
  };

  return (
    <div className="flex flex-col h-full max-w-7xl mx-auto space-y-6 animate-in fade-in duration-500">
      <div className="flex items-center justify-between mb-2">
        <div>
          <h1 className="text-xl font-semibold text-ink">Knowledge Base</h1>
          <p className="mt-1 text-sm text-muted">Manage RAG documents and platform intelligence</p>
        </div>
      </div>

      {reindex && reindex.status !== 'idle' && (
        <div className="card border-2 border-brand-100 p-5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-ink">Re-embedding documents</h2>
              <p className="text-xs text-muted">
                {reindex.target_model ? `Model: ${reindex.target_model}` : 'Preparing…'}
                {' · '}runs automatically in the background
              </p>
            </div>
            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${
              reindex.status === 'completed'
                ? 'bg-success-soft text-success'
                : reindex.status === 'failed'
                  ? 'bg-danger-soft text-danger'
                  : 'bg-warning-soft text-warning'
            }`}>
              {reindex.status}
            </span>
          </div>
          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            <span>
              {reindex.documents_embedded ?? 0} / {reindex.documents_total ?? 0} documents embedded
            </span>
            <span>{reindex.chunks_embedded ?? 0} / {reindex.chunks_total ?? 0} chunks</span>
            {reindex.failed > 0 && <span className="text-danger">{reindex.failed} failed</span>}
          </div>
          {(reindex.documents_total ?? 0) > 0 && (
            <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-canvas">
              <div
                className="h-2 rounded-full bg-brand-500 transition-all"
                style={{
                  width: `${Math.round(
                    ((reindex.documents_embedded ?? 0) /
                      Math.max(1, reindex.documents_total ?? 0)) *
                      100
                  )}%`,
                }}
              />
            </div>
          )}
          {reindex.error && <p className="mt-2 text-xs text-danger">{reindex.error}</p>}
          <p className="mt-3 text-[11px] text-muted">
            Only chunks embedded by the active model are used for document search.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="glass-card p-6 lg:col-span-1 h-fit flex flex-col space-y-4">
          <h2 className="text-lg font-bold text-slate-800 flex items-center">
            <Database className="w-5 h-5 mr-2 text-brand-600" />
            Ingest New Content
          </h2>
          
          <div className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Subject / Course Name</label>
              <input 
                type="text" 
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-brand-500" 
                placeholder="e.g. Physics 101" 
                value={subject} 
                onChange={e => setSubject(e.target.value)} 
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Description (Optional)</label>
              <input 
                type="text" 
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-brand-500" 
                placeholder="Brief description" 
                value={description} 
                onChange={e => setDescription(e.target.value)} 
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Tags (Comma separated)</label>
              <input 
                type="text" 
                className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:border-brand-500" 
                placeholder="e.g. chapter1, mechanics" 
                value={tags} 
                onChange={e => setTags(e.target.value)} 
              />
            </div>
          </div>

          <div className="border-2 border-dashed border-slate-200 rounded-xl p-6 flex flex-col items-center justify-center text-center bg-slate-50 hover:bg-slate-100 transition-colors cursor-pointer relative mt-2">
            <input 
              type="file" 
              accept=".pdf,.txt,.md,.markdown,.csv,.json,.log" 
              className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
              onChange={handleFileUpload}
              disabled={uploading}
            />
            {uploading ? (
              <div className="flex flex-col items-center">
                <div className="w-10 h-10 border-4 border-brand-200 border-t-brand-600 rounded-full animate-spin mb-4"></div>
                <p className="font-medium text-slate-700">Uploading to Celery Queue...</p>
              </div>
            ) : (
              <>
                <div className="w-12 h-12 bg-brand-100 text-brand-600 rounded-full flex items-center justify-center mb-3">
                  <Upload className="w-6 h-6" />
                </div>
                <p className="font-medium text-slate-700 mb-1 text-sm">Select a document to upload</p>
                <p className="text-xs text-slate-500">PDF, TXT, MD, CSV, JSON, LOG</p>
              </>
            )}
          </div>
        </div>

        <div className="glass-card p-6 lg:col-span-2">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-lg font-bold text-slate-800">Indexed Documents</h2>
            
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 h-4 w-4" />
              <input 
                type="text" 
                placeholder="Search files..." 
                className="pl-10 pr-4 py-1.5 bg-slate-50 rounded-lg border border-slate-200 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 w-48"
              />
            </div>
          </div>

          {loading ? (
            <div className="py-12 text-center text-slate-500">Loading documents...</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-slate-100">
                    <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Document</th>
                    <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Size</th>
                    <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Uploaded</th>
                    <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase">Status</th>
                    <th className="py-3 px-4 text-xs font-semibold text-slate-500 uppercase text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {files.map((file) => (
                    <tr key={file.id} className="border-b border-slate-50 hover:bg-slate-50/50 transition-colors">
                      <td className="py-3 px-4">
                        <div className="flex items-center">
                          <FileText className="w-5 h-5 text-slate-400 mr-3" />
                          <span className="font-medium text-slate-700 text-sm">{file.original_filename || file.filename}</span>
                        </div>
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-500">
                        {file.file_size ? `${(file.file_size / 1024 / 1024).toFixed(2)} MB` : 'Unknown'}
                      </td>
                      <td className="py-3 px-4 text-sm text-slate-500">
                        {file.created_at ? new Date(file.created_at).toLocaleDateString() : 'Unknown'}
                      </td>
                      <td className="py-3 px-4">
                        {file.status === 'chunked' ? (
                          <div className="flex flex-col space-y-1.5 w-48">
                            <div className="flex justify-between items-center text-xs">
                              <span className="font-semibold text-blue-700">Embedding...</span>
                              <span className="text-slate-500 font-medium">
                                {file.processed_chunks || 0} / {file.total_chunks || 0}
                              </span>
                            </div>
                            <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                              <div 
                                className="bg-blue-500 h-1.5 rounded-full transition-all duration-500" 
                                style={{ width: `${file.total_chunks ? Math.min(100, ((file.processed_chunks || 0) / file.total_chunks) * 100) : 0}%` }}
                              ></div>
                            </div>
                            <div className="text-[10px] text-slate-400 text-right">
                              ETA: ~{file.total_chunks ? Math.ceil(((file.total_chunks - (file.processed_chunks || 0)) * 1.5) / 60) : 0} mins
                            </div>
                          </div>
                        ) : (
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            file.status === 'processed' ? 'bg-green-100 text-green-800' : 
                            'bg-yellow-100 text-yellow-800'
                          }`}>
                            {file.status === 'processed' ? 'Ready to Use' : 
                             file.status === 'uploaded' ? 'Uploaded' :
                             file.status === 'processing' ? 'Processing' : file.status}
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right space-x-3">
                        <button 
                          onClick={() => handleDownload(file.id, file.original_filename || file.filename)}
                          className="text-slate-400 hover:text-brand-500 transition-colors"
                          title="Download file"
                        >
                          <Download className="w-4 h-4 inline" />
                        </button>
                        <button 
                          onClick={() => handleDelete(file.id)}
                          className="text-slate-400 hover:text-red-500 transition-colors"
                          title="Delete file"
                        >
                          <Trash2 className="w-4 h-4 inline" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
