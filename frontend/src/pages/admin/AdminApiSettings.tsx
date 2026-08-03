import { useState, useEffect } from 'react';
import { Settings2, Edit2, Check, KeyRound, Save, AlertTriangle, Loader2 } from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';

export default function AdminApiSettings() {
  const [isEditing, setIsEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  
  const [settings, setSettings] = useState({
    mistral_api_key: '',
    mistral_chat_model: '',
    mistral_embed_model: ''
  });
  
  const [maskedKey, setMaskedKey] = useState('');
  
  // Available models from Mistral API
  const [chatModels, setChatModels] = useState<string[]>([]);
  const [embedModels, setEmbedModels] = useState<string[]>([]);
  const [modelsLoaded, setModelsLoaded] = useState(false);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    try {
      const res = await api.get('/admin/settings/api');
      setSettings({
        mistral_api_key: '', // Do not prefill real key
        mistral_chat_model: res.data.mistral_chat_model,
        mistral_embed_model: res.data.mistral_embed_model
      });
      setMaskedKey(res.data.mistral_api_key_masked || 'Not Set');
    } catch (err) {
      toast.error('Failed to fetch API settings');
    }
  };

  const validateApiKey = async () => {
    if (!settings.mistral_api_key) {
      toast.error('Please enter a Mistral API key first');
      return;
    }
    
    setValidating(true);
    try {
      const res = await api.post('/admin/settings/validate-mistral', {
        api_key: settings.mistral_api_key
      });
      
      if (res.data.valid) {
        toast.success('API Key validated! Models fetched successfully.');
        setChatModels(res.data.chat_models);
        setEmbedModels(res.data.embed_models);
        setModelsLoaded(true);
        
        // Auto-select if empty
        if (!settings.mistral_chat_model && res.data.chat_models.length > 0) {
          setSettings(s => ({ ...s, mistral_chat_model: res.data.chat_models[0] }));
        }
        if (!settings.mistral_embed_model && res.data.embed_models.length > 0) {
          setSettings(s => ({ ...s, mistral_embed_model: res.data.embed_models[0] }));
        }
      }
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Invalid API Key or connection failed');
      setModelsLoaded(false);
    } finally {
      setValidating(false);
    }
  };

  const handleSave = async () => {
    if (!settings.mistral_api_key) {
      toast.error("Please provide an API key");
      return;
    }
    if (!modelsLoaded) {
      toast.error("Please validate the API key and select models before saving");
      return;
    }
    
    setSaving(true);
    try {
      const res = await api.put('/admin/settings/api', settings);
      toast.success(res.data.message || 'Settings saved successfully', { duration: 5000 });
      setIsEditing(false);
      fetchSettings();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Failed to save settings');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto space-y-6 animate-in fade-in duration-500">
      <div>
        <h1 className="text-2xl font-bold text-slate-800">API Configurations</h1>
        <p className="text-sm text-slate-500">Manage third-party AI provider connections and models.</p>
      </div>

      {isEditing && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start">
          <AlertTriangle className="w-5 h-5 text-amber-500 mt-0.5 mr-3 shrink-0" />
          <div>
            <h3 className="text-sm font-bold text-amber-800">Backend Restart Required</h3>
            <p className="text-sm text-amber-700 mt-1">
              Saving these settings will update the environment configuration. You must restart the Docker backend containers for changes to take effect.
            </p>
          </div>
        </div>
      )}

      {/* Mistral Section */}
      <div className="glass-card overflow-hidden">
        <div className="border-b border-slate-100 bg-slate-50 p-5 flex justify-between items-center">
          <div className="flex items-center">
            <div className="w-10 h-10 rounded-lg bg-orange-100 flex items-center justify-center mr-4">
              <Settings2 className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800">Mistral AI</h2>
              <p className="text-sm text-slate-500">Configuration for the Mistral API and models.</p>
            </div>
          </div>
          
          {!isEditing ? (
            <button 
              onClick={() => setIsEditing(true)}
              className="p-2 bg-white border border-slate-200 rounded-lg text-slate-600 hover:text-brand-600 hover:border-brand-200 shadow-sm transition-colors flex items-center"
            >
              <Edit2 className="w-4 h-4 mr-2" /> Edit Settings
            </button>
          ) : (
            <button 
              onClick={() => { setIsEditing(false); fetchSettings(); setModelsLoaded(false); }}
              className="p-2 bg-white border border-slate-200 rounded-lg text-slate-600 hover:text-slate-800 shadow-sm transition-colors"
            >
              Cancel
            </button>
          )}
        </div>

        <div className="p-6 space-y-6">
          {/* API Key */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">Mistral API Key</label>
            {!isEditing ? (
              <div className="flex items-center px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-600 font-mono text-sm">
                <KeyRound className="w-4 h-4 mr-3 text-slate-400" />
                {maskedKey}
              </div>
            ) : (
              <div className="flex space-x-3">
                <div className="relative flex-1">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                    <KeyRound className="w-4 h-4 text-slate-400" />
                  </div>
                  <input
                    type="password"
                    value={settings.mistral_api_key}
                    onChange={(e) => setSettings({ ...settings, mistral_api_key: e.target.value })}
                    className="block w-full pl-10 pr-3 py-2.5 border border-slate-300 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 sm:text-sm"
                    placeholder="Enter your Mistral API Key (sk-...)"
                  />
                </div>
                <button
                  onClick={validateApiKey}
                  disabled={validating || !settings.mistral_api_key}
                  className="btn-secondary px-4 py-2.5 rounded-xl flex items-center shrink-0"
                >
                  {validating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                  Verify & Fetch Models
                </button>
              </div>
            )}
            {isEditing && !modelsLoaded && (
              <p className="text-xs text-slate-500 mt-2">You must verify the key to select models.</p>
            )}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2">
            {/* Chat Model */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Chat Generation Model</label>
              {!isEditing ? (
                <div className="px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-700 font-medium">
                  {settings.mistral_chat_model}
                </div>
              ) : (
                <select
                  value={settings.mistral_chat_model}
                  onChange={(e) => setSettings({ ...settings, mistral_chat_model: e.target.value })}
                  disabled={!modelsLoaded}
                  className="block w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 sm:text-sm disabled:bg-slate-100 disabled:text-slate-400"
                >
                  {modelsLoaded ? (
                    chatModels.map(model => (
                      <option key={model} value={model}>{model}</option>
                    ))
                  ) : (
                    <option value="">Fetch models first...</option>
                  )}
                </select>
              )}
            </div>

            {/* Embed Model */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">Embeddings Model</label>
              {!isEditing ? (
                <div className="px-4 py-3 bg-slate-50 border border-slate-200 rounded-xl text-slate-700 font-medium">
                  {settings.mistral_embed_model}
                </div>
              ) : (
                <select
                  value={settings.mistral_embed_model}
                  onChange={(e) => setSettings({ ...settings, mistral_embed_model: e.target.value })}
                  disabled={!modelsLoaded}
                  className="block w-full px-4 py-3 border border-slate-300 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-brand-500 sm:text-sm disabled:bg-slate-100 disabled:text-slate-400"
                >
                  {modelsLoaded ? (
                    embedModels.map(model => (
                      <option key={model} value={model}>{model}</option>
                    ))
                  ) : (
                    <option value="">Fetch models first...</option>
                  )}
                </select>
              )}
            </div>
          </div>

          {isEditing && (
            <div className="pt-6 border-t border-slate-100 flex justify-end">
              <button
                onClick={handleSave}
                disabled={saving || !modelsLoaded}
                className="btn-primary px-8 py-3 rounded-xl flex items-center shadow-md shadow-brand-500/20"
              >
                {saving ? (
                  <Loader2 className="w-5 h-5 animate-spin mr-2" />
                ) : (
                  <Save className="w-5 h-5 mr-2" />
                )}
                Save Configuration
              </button>
            </div>
          )}
        </div>
      </div>
      
      {/* Future Provider Placeholder */}
      <div className="glass-card overflow-hidden opacity-50 grayscale">
        <div className="border-b border-slate-100 bg-slate-50 p-5 flex justify-between items-center">
          <div className="flex items-center">
            <div className="w-10 h-10 rounded-lg bg-slate-200 flex items-center justify-center mr-4">
              <span className="font-bold text-slate-400 text-sm">AI</span>
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-800">Other Provider</h2>
              <p className="text-sm text-slate-500">Coming soon.</p>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
