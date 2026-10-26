import { useEffect, useMemo, useState } from 'react';
import {
  Boxes,
  BrainCircuit,
  CheckCircle2,
  Cpu,
  KeyRound,
  Pencil,
  Plus,
  RefreshCw,
  Server,
  Star,
  Trash2,
  X,
} from 'lucide-react';
import toast from 'react-hot-toast';
import api from '../../api';
import PageHeader from '../../components/ui/PageHeader';
import { Card, CardBody, CardHeader } from '../../components/ui/Card';
import Button from '../../components/ui/Button';
import Input from '../../components/ui/Input';
import { Badge } from '../../components/ui/Badge';

interface ModelRow {
  id: string;
  provider_id: string;
  name: string;
  display_name: string;
  kind: 'chat' | 'embedding';
  context_window: number;
  max_output_tokens: number;
  embedding_dimensions: number | null;
  system_prompt: string | null;
  is_default: boolean;
  is_active: boolean;
}

interface Provider {
  id: string;
  name: string;
  adapter: string;
  base_url: string;
  chat_url: string;
  embeddings_url: string;
  models_url: string;
  auth_type: string;
  auth_key_name: string | null;
  auth_username: string | null;
  has_key: boolean;
  api_key_masked: string;
  is_active: boolean;
  models: ModelRow[];
}

interface Defaults {
  vector_dimensions?: number;
  default_system_prompt?: string;
  system_prompt_max_chars?: number;
  system_prompt_max_words?: number;
  chat_error?: string | null;
  embedding_error?: string | null;
  chat: null | {
    provider: string;
    model: string;
    context_window: number;
    max_output_tokens: number;
    system_prompt: string | null;
  };
  embedding: null | {
    provider: string;
    model: string;
    embedding_dimensions: number | null;
  };
}

const AUTH_TYPES = [
  { value: 'bearer', label: 'Bearer token (Authorization)' },
  { value: 'header', label: 'API-key header (x-api-key)' },
  { value: 'query', label: 'Query parameter' },
  { value: 'basic', label: 'Basic auth (username + key)' },
  { value: 'none', label: 'No authentication' },
];

const emptyProvider = {
  name: '',
  adapter: 'openai_compatible',
  base_url: '',
  chat_url: '',
  embeddings_url: '',
  models_url: '',
  auth_type: 'bearer',
  auth_key_name: 'x-api-key',
  auth_username: '',
  api_key: '',
  test_model: '',
  test_kind: 'chat' as 'chat' | 'embedding',
  test_dimensions: '',
  test_context_window: 32000,
  test_max_output_tokens: 1024,
};

const emptyModel = {
  id: '',
  name: '',
  display_name: '',
  kind: 'chat' as 'chat' | 'embedding',
  context_window: 32000,
  max_output_tokens: 1024,
  embedding_dimensions: '',
  system_prompt: '',
};

export default function AdminAiProviders() {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [defaults, setDefaults] = useState<Defaults | null>(null);
  const [loading, setLoading] = useState(true);

  const [addOpen, setAddOpen] = useState(false);
  const [editingProvider, setEditingProvider] = useState<Provider | null>(null);
  const [form, setForm] = useState({ ...emptyProvider });
  const [remoteModels, setRemoteModels] = useState<
    { id: string; display_name: string; context_window?: number; max_output_tokens?: number }[]
  >([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testPassed, setTestPassed] = useState(false);
  const [testAnswer, setTestAnswer] = useState('');
  const [saving, setSaving] = useState(false);
  const [reindex, setReindex] = useState<any>(null);
  const [postAddNotice, setPostAddNotice] = useState<{
    provider: Provider;
    model: ModelRow | null;
    kind: 'chat' | 'embedding';
    context: number;
    output: number;
    usedDefaults: boolean;
  } | null>(null);

  const [modelProvider, setModelProvider] = useState<Provider | null>(null);
  const [modelForm, setModelForm] = useState({ ...emptyModel });
  const [savingModel, setSavingModel] = useState(false);

  const [pendingModel, setPendingModel] = useState<ModelRow | null>(null);
  const [pendingDocs, setPendingDocs] = useState(0);
  const [noticeOpen, setNoticeOpen] = useState(false);

  const promptWordCount = modelForm.system_prompt
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
  const promptOverLimit =
    modelForm.kind === 'chat' &&
    (modelForm.system_prompt.length >
      (defaults?.system_prompt_max_chars ?? 8000) ||
      promptWordCount > (defaults?.system_prompt_max_words ?? 1200));

  const loadReindex = async () => {
    try {
      const res = await api.get('/admin/ai/reindex/status');
      setReindex(res.data);
    } catch {
      // Informational only.
    }
  };

  const load = async () => {
    try {
      const [p, d] = await Promise.all([
        api.get('/admin/ai/providers'),
        api.get('/admin/ai/defaults'),
      ]);
      setProviders(p.data);
      setDefaults(d.data);
    } catch {
      toast.error('Could not load AI providers.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    loadReindex();
  }, []);


  useEffect(() => {
    if (!reindex || !['queued', 'running'].includes(reindex.status)) return;
    const timer = setInterval(loadReindex, 3000);
    return () => clearInterval(timer);
  }, [reindex?.status]);

  const authNeedsName = form.auth_type === 'header' || form.auth_type === 'query';
  const isCustom = form.adapter === 'custom';

  const openAdd = (kind: 'chat' | 'embedding') => {
    setEditingProvider(null);
    setForm({ ...emptyProvider, test_kind: kind });
    setRemoteModels([]);
    setTestPassed(false);
    setTestAnswer('');
    setAddOpen(true);
  };

  const openEdit = (provider: Provider) => {
    setEditingProvider(provider);
    setForm({
      ...emptyProvider,
      name: provider.name,
      adapter: provider.adapter,
      base_url: provider.base_url,
      chat_url: provider.chat_url || '',
      embeddings_url: provider.embeddings_url || '',
      models_url: provider.models_url || '',
      auth_type: provider.auth_type,
      auth_key_name: provider.auth_key_name || 'x-api-key',
      auth_username: provider.auth_username || '',
      api_key: '',
      test_kind: provider.models.some((m) => m.kind === 'embedding') ? 'embedding' : 'chat',
    });
    setRemoteModels([]);
    setTestPassed(false);
    setTestAnswer('');
    setAddOpen(true);
  };

  const updateForm = (key: keyof typeof form, value: any) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    if (
      key === 'base_url' ||
      key === 'auth_type' ||
      key === 'api_key' ||
      key === 'test_model' ||
      key === 'test_kind' ||
      key === 'test_dimensions' ||
      key === 'adapter' ||
      key === 'chat_url' ||
      key === 'embeddings_url' ||
      key === 'models_url'
    ) {
      setTestPassed(false);
      setTestAnswer('');
    }
  };

  const fetchModels = async () => {
    if (isCustom ? !form.models_url : !form.base_url) {
      toast.error(isCustom ? 'Enter the models endpoint URL first.' : 'Enter the base URL first.');
      return;
    }
    setLoadingModels(true);
    try {
      const res = await api.post('/admin/ai/providers/models/remote', {
        adapter: form.adapter,
        base_url: form.base_url || form.models_url,
        models_url: isCustom ? form.models_url : null,
        auth_type: form.auth_type,
        api_key: form.api_key || null,
        auth_key_name: authNeedsName ? form.auth_key_name : null,
        auth_username: form.auth_type === 'basic' ? form.auth_username : null,
      });
      const models = (res.data.models || []).map((m: any) =>
        typeof m === 'string'
          ? { id: m, display_name: m }
          : {
              id: m.id,
              display_name: m.display_name || m.id,
              context_window: m.context_window,
              max_output_tokens: m.max_output_tokens,
            }
      );
      setRemoteModels(models);
      if (models.length && !form.test_model) {
        applyRemoteModel(models[0]);
      }
      toast.success(`${models.length} model(s) loaded.`);
    } catch (err: any) {
      setRemoteModels([]);
      toast.error(
        err.response?.data?.detail ||
          'Unable to load models. Type the model name manually if this provider has no model list.'
      );
    } finally {
      setLoadingModels(false);
    }
  };

  const applyRemoteModel = (model: {
    id: string;
    context_window?: number;
    max_output_tokens?: number;
  }) => {
    setForm((prev) => ({
      ...prev,
      test_model: model.id,
      test_context_window: model.context_window || prev.test_context_window,
      test_max_output_tokens:
        model.max_output_tokens || prev.test_max_output_tokens,
    }));
    setTestPassed(false);
    setTestAnswer('');
  };

  const testProvider = async () => {
    const endpoint =
      form.test_kind === 'embedding' ? form.embeddings_url : form.chat_url;
    if ((isCustom ? !endpoint : !form.base_url) || !form.test_model) {
      toast.error(
        isCustom
          ? `Enter the ${form.test_kind === 'embedding' ? 'embeddings' : 'chat'} endpoint and model.`
          : 'Base URL and model are required for the test.'
      );
      return;
    }
    setTesting(true);
    setTestPassed(false);
    setTestAnswer('');
    try {
      const res = await api.post('/admin/ai/providers/test', {
        adapter: form.adapter,
        base_url: form.base_url || form.chat_url || form.embeddings_url,
        chat_url: isCustom ? form.chat_url || null : null,
        embeddings_url: isCustom ? form.embeddings_url || null : null,
        models_url: isCustom ? form.models_url || null : null,
        auth_type: form.auth_type,
        api_key: form.api_key || null,
        auth_key_name: authNeedsName ? form.auth_key_name : null,
        auth_username: form.auth_type === 'basic' ? form.auth_username : null,
        model: form.test_model,
        kind: form.test_kind,
        expected_dimensions:
          form.test_kind === 'embedding'
            ? Number(form.test_dimensions) || null
            : null,
      });
      if (form.test_kind === 'embedding') {
        setTestAnswer(`Embedding OK — ${res.data.dimensions} dimensions`);
      } else {
        setTestAnswer(res.data.answer);
      }
      setTestPassed(true);
      toast.success(`Provider responded in ${res.data.latency_ms ?? 0} ms.`);
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Provider test failed.');
    } finally {
      setTesting(false);
    }
  };

  const saveProvider = async () => {
    if (!editingProvider && !testPassed) {
      toast.error('Run a successful test before adding the provider.');
      return;
    }
    setSaving(true);
    try {
      const payload: Record<string, unknown> = {
        name: form.name,
        adapter: form.adapter,
        base_url: form.base_url || form.chat_url || form.embeddings_url,
        chat_url: isCustom ? form.chat_url || null : null,
        embeddings_url: isCustom ? form.embeddings_url || null : null,
        models_url: isCustom ? form.models_url || null : null,
        auth_type: form.auth_type,
        auth_key_name: authNeedsName ? form.auth_key_name : null,
        auth_username: form.auth_type === 'basic' ? form.auth_username : null,
        api_key: form.api_key || null,
        test_model: form.test_model,
        test_kind: form.test_kind,
        test_dimensions:
          form.test_kind === 'embedding'
            ? Number(form.test_dimensions) || null
            : null,
        test_context_window: Number(form.test_context_window) || 32000,
        test_max_output_tokens: Number(form.test_max_output_tokens) || 1024,
      };

      if (editingProvider) {
        const update = { ...payload };
        for (const key of ['test_model', 'test_kind', 'test_dimensions']) {
          delete update[key];
        }
        if (!update.api_key) delete update.api_key;
        await api.put(`/admin/ai/providers/${editingProvider.id}`, update);
        toast.success('Provider updated.');
      } else {
        const res = await api.post('/admin/ai/providers', payload);
        const created = res.data as Provider;
        const createdModel =
          created.models.find(
            (m) => m.kind === form.test_kind && m.name === form.test_model
          ) || null;
        const context = Number(form.test_context_window) || 32000;
        const output = Number(form.test_max_output_tokens) || 1024;
        setPostAddNotice({
          provider: created,
          model: createdModel,
          kind: form.test_kind,
          context,
          output,
          usedDefaults:
            form.test_kind === 'chat' && context === 32000 && output === 1024,
        });
        toast.success(
          form.test_kind === 'chat'
            ? `Provider added and ${form.test_model} tested — context ${context.toLocaleString()}, max output ${output.toLocaleString()}.`
            : `Embedding provider added and ${form.test_model} verified.`
        );
      }
      setAddOpen(false);
      setEditingProvider(null);
      setForm({ ...emptyProvider });
      setRemoteModels([]);
      setTestPassed(false);
      setTestAnswer('');
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not save the provider.');
    } finally {
      setSaving(false);
    }
  };

  const toggleProvider = async (provider: Provider) => {
    try {
      await api.put(`/admin/ai/providers/${provider.id}`, {
        is_active: !provider.is_active,
      });
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not update the provider.');
    }
  };

  const deleteProvider = async (provider: Provider) => {
    const hasDefault = provider.models.some((m) => m.kind === 'chat' && m.is_default);
    const hasActiveEmbedding = provider.models.some(
      (m) => m.kind === 'embedding' && m.is_active
    );
    const warning =
      hasDefault || hasActiveEmbedding
        ? `\n\nThis provider contains the ${
            hasDefault ? 'default chat model' : ''
          }${hasDefault && hasActiveEmbedding ? ' and ' : ''}${
            hasActiveEmbedding ? 'active embedding model (its vectors will be deleted)' : ''
          }. AI${hasActiveEmbedding ? ' and document search' : ''} will be disabled until you configure another.`
        : '';
    if (!window.confirm(`Delete provider "${provider.name}" and all its models?${warning}`)) {
      return;
    }
    try {
      await api.delete(`/admin/ai/providers/${provider.id}?force=true`);
      toast.success('Provider and its models deleted.');
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not delete the provider.');
    }
  };

  const openModelForm = (
    provider: Provider,
    model?: ModelRow,
    kind: 'chat' | 'embedding' = 'chat'
  ) => {
    setModelProvider(provider);
    if (model) {
      setModelForm({
        id: model.id,
        name: model.name,
        display_name: model.display_name,
        kind: model.kind,
        context_window: model.context_window,
        max_output_tokens: model.max_output_tokens,
        embedding_dimensions: model.embedding_dimensions
          ? String(model.embedding_dimensions)
          : '',
        system_prompt: model.system_prompt ?? '',
      });
    } else {
      setModelForm({ ...emptyModel, kind });
    }
  };

  const saveModel = async () => {
    if (!modelProvider) return;
    setSavingModel(true);
    try {
      const payload = {
        name: modelForm.name,
        display_name: modelForm.display_name || modelForm.name,
        kind: modelForm.kind,
        context_window: Number(modelForm.context_window),
        max_output_tokens: Number(modelForm.max_output_tokens),
        embedding_dimensions:
          modelForm.kind === 'embedding'
            ? Number(modelForm.embedding_dimensions)
            : null,
        system_prompt:
          modelForm.kind === 'chat' ? modelForm.system_prompt.trim() : undefined,
      };
      if (modelForm.id) {
        await api.put(`/admin/ai/models/${modelForm.id}`, {
          display_name: payload.display_name,
          context_window: payload.context_window,
          max_output_tokens: payload.max_output_tokens,
          embedding_dimensions: payload.embedding_dimensions,
          system_prompt: payload.system_prompt,
        });
      } else {
        const res = await api.post(
          `/admin/ai/providers/${modelProvider.id}/models`,
          payload
        );
        const created = res.data as ModelRow;
        const context = Number(modelForm.context_window);
        const output = Number(modelForm.max_output_tokens);
        setPostAddNotice({
          provider: modelProvider,
          model: created,
          kind: modelForm.kind,
          context,
          output,
          usedDefaults:
            modelForm.kind === 'chat' && context === 32000 && output === 1024,
        });
      }
      toast.success(modelForm.id ? 'Model updated.' : 'Model added and verified.');
      setModelProvider(null);
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not save the model.');
    } finally {
      setSavingModel(false);
    }
  };

  const toggleModel = async (model: ModelRow) => {
    if (model.kind === 'embedding') {
      toast.error('Only one embedding model can be active. Use Activate on another model to switch.');
      return;
    }
    try {
      await api.put(`/admin/ai/models/${model.id}`, {
        is_active: !model.is_active,
      });
      toast.success(model.is_active ? 'Model disabled.' : 'Model enabled.');
      await load();
      await loadReindex();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not update the model.');
    }
  };

  const setDefault = async (model: ModelRow) => {
    try {
      const res = await api.post(`/admin/ai/models/${model.id}/default`, {
        confirm_reindex: false,
      });
      if (res.data.status === 'reindex_required') {
        setPendingModel(model);
        setPendingDocs(res.data.documents || 0);
        setNoticeOpen(true);
        return;
      }
      toast.success(`${model.display_name} is now the default ${model.kind} model.`);
      await load();
      await loadReindex();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not set the default.');
    }
  };

  const confirmEmbeddingChange = async () => {
    if (!pendingModel) return;
    try {
      const res = await api.post(`/admin/ai/models/${pendingModel.id}/default`, {
        confirm_reindex: true,
      });
      if (res.data.status === 'queued') {
        toast.success(
          `Re-indexing ${res.data.documents} document(s) queued in the background.`
        );
      } else {
        toast.success('Default embedding model changed.');
      }
      setNoticeOpen(false);
      setPendingModel(null);
      await load();
      await loadReindex();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not change the embedding model.');
    }
  };

  const testModel = async (model: ModelRow) => {
    try {
      const res = await api.post(
        `/admin/ai/providers/${model.provider_id}/test?model=${encodeURIComponent(
          model.name
        )}&kind=${model.kind}`
      );
      toast.success(
        model.kind === 'embedding'
          ? `Embedding OK — ${res.data.dimensions} dimensions`
          : res.data.answer
      );
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Model test failed.');
    }
  };

  const deleteModel = async (model: ModelRow) => {
    const warning =
      model.kind === 'chat' && model.is_default
        ? '\n\nThis is the default chat model. Chat will be disabled until you choose another default.'
        : model.kind === 'embedding' && model.is_active
          ? '\n\nThis is the active embedding model. Its vectors will be deleted and document search will be disabled.'
          : '';
    if (!window.confirm(`Delete model "${model.display_name}"?${warning}`)) return;
    try {
      await api.delete(`/admin/ai/models/${model.id}?force=true`);
      toast.success('Model deleted.');
      await load();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || 'Could not delete the model.');
    }
  };

  const selectOptions = useMemo(
    () => (
      <>
        <option value="">Select a model…</option>
        {remoteModels.map((model) => (
          <option key={model.id} value={model.id}>
            {model.display_name}
            {model.context_window ? ` · ${model.context_window.toLocaleString()} tokens` : ''}
          </option>
        ))}
      </>
    ),
    [remoteModels]
  );

  return (
    <div className="mx-auto flex max-w-6xl flex-col space-y-5">
      <PageHeader
        title="AI Providers"
        subtitle="Providers, base URLs, auth methods and models. Keys are encrypted at rest."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => openAdd('embedding')}>
              <Boxes className="h-4 w-4" /> New embedding provider
            </Button>
            <Button onClick={() => openAdd('chat')}>
              <BrainCircuit className="h-4 w-4" /> New chat provider
            </Button>
          </div>
        }
      />

      {postAddNotice && (
        <Card className={postAddNotice.usedDefaults ? 'border-amber-200' : 'border-green-200'}>
          <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex gap-3">
              <span
                className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                  postAddNotice.usedDefaults
                    ? 'bg-warning-soft text-warning'
                    : 'bg-success-soft text-success'
                }`}
              >
                <CheckCircle2 className="h-4 w-4" />
              </span>
              <div>
                <p className="text-sm font-semibold text-ink">
                  Provider added and{' '}
                  {postAddNotice.kind === 'embedding' ? 'embedding verified' : 'model tested'}
                </p>
                {postAddNotice.kind === 'chat' ? (
                  <p className="mt-0.5 text-xs text-muted">
                    {postAddNotice.model?.name || 'The first model'} is set to context{' '}
                    {postAddNotice.context.toLocaleString()} · max output{' '}
                    {postAddNotice.output.toLocaleString()}.
                  </p>
                ) : (
                  <p className="mt-0.5 text-xs text-muted">
                    Verify the dimensions, activate it, then re-index documents.
                  </p>
                )}
                {postAddNotice.usedDefaults && (
                  <p className="mt-1 text-xs font-medium text-warning">
                    You used the default 32,000 / 1,024. Open the model and set the
                    provider's real context window and output limit before going live.
                  </p>
                )}
                <p className="mt-1 text-xs text-muted">
                  Review the model's system prompt and default status next.
                </p>
              </div>
            </div>
            <div className="flex shrink-0 flex-wrap gap-2">
              {postAddNotice.model && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => openModelForm(postAddNotice.provider, postAddNotice.model!)}
                >
                  <Pencil className="h-3.5 w-3.5" /> Edit model
                </Button>
              )}
              <Button size="sm" variant="ghost" onClick={() => setPostAddNotice(null)}>
                Dismiss
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardBody className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {[
            {
              title: '1. Chat provider',
              body: 'New chat provider → base URL, auth, key → live test → save. The first chat model is created automatically.',
            },
            {
              title: '2. Models',
              body: 'Under a provider, add chat or embedding models. Set context/output, then Set default for the chat model to use.',
            },
            {
              title: '3. System prompt',
              body: 'Edit a chat model. Blank means the built-in default; the placeholder shows it. Saved per model.',
            },
            {
              title: '4. Embeddings',
              body: 'New embedding provider or Add embedding model under an existing one → test dimensions → Activate → re-index documents.',
            },
          ].map((step) => (
            <div key={step.title} className="rounded-lg border border-line bg-canvas/50 p-3">
              <p className="text-xs font-semibold text-ink">{step.title}</p>
              <p className="mt-1 text-[11px] leading-relaxed text-muted">{step.body}</p>
            </div>
          ))}
        </CardBody>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Default chat model" subtitle="Used for chat and summaries." />
          <CardBody className="text-sm">
            {defaults?.chat ? (
              <div className="space-y-1">
                <p className="font-medium text-ink">{defaults.chat.model}</p>
                <p className="text-muted">{defaults.chat.provider}</p>
                <p className="text-xs text-muted">
                  Context window {defaults.chat.context_window.toLocaleString()} · max output{' '}
                  {defaults.chat.max_output_tokens.toLocaleString()}
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                <p className="text-muted">Not configured.</p>
                {defaults?.chat_error && (
                  <p className="text-xs text-danger">{defaults.chat_error}</p>
                )}
              </div>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Default embedding model" subtitle="Used for document vectors." />
          <CardBody className="text-sm">
            {defaults?.embedding ? (
              <div className="space-y-1">
                <p className="font-medium text-ink">{defaults.embedding.model}</p>
                <p className="text-muted">{defaults.embedding.provider}</p>
                <p className="text-xs text-muted">
                  {defaults.embedding.embedding_dimensions ?? '?'} dimensions · database
                  column {defaults.vector_dimensions ?? '?'}
                </p>
              </div>
            ) : (
              <div className="space-y-1">
                <p className="text-muted">Not configured.</p>
                {defaults?.embedding_error && (
                  <p className="text-xs text-danger">{defaults.embedding_error}</p>
                )}
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      <Card>
        <CardHeader
          title="Document embeddings"
          subtitle="Embedded documents for the active model."
          actions={<Badge tone="neutral">runs automatically</Badge>}
        />
        <CardBody className="space-y-3 text-sm">
          {reindex ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Badge
                  tone={
                    reindex.status === 'running' || reindex.status === 'queued'
                      ? 'warning'
                      : reindex.status === 'completed'
                        ? 'success'
                        : reindex.status === 'failed'
                          ? 'danger'
                          : 'neutral'
                  }
                >
                  {reindex.status}
                </Badge>
                {reindex.target_model && (
                  <span className="text-muted">Model: {reindex.target_model}</span>
                )}
                <span className="text-muted">
                  {reindex.documents_embedded ?? 0} / {reindex.documents_total ?? 0}{' '}
                  documents embedded
                </span>
                <span className="text-muted">
                  {reindex.chunks_embedded ?? 0} / {reindex.chunks_total ?? 0} chunks
                </span>
                {reindex.failed > 0 && (
                  <span className="text-danger">{reindex.failed} failed</span>
                )}
              </div>

              {(reindex.documents_total ?? 0) > 0 && (
                <div className="h-2 w-full overflow-hidden rounded-full bg-canvas">
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
              {['queued', 'running'].includes(reindex.status) && reindex.total > 0 && (
                <p className="text-xs text-muted">
                  Re-index job: {reindex.done} / {reindex.total} documents processed
                </p>
              )}

              {reindex.error && (
                <p className="text-xs text-danger">{reindex.error}</p>
              )}
              <p className="text-xs text-muted">
                Switching the embedding model queues this automatically. Only chunks
                embedded by the active model are used for search.
              </p>
            </>
          ) : (
            <p className="text-muted">Loading status…</p>
          )}
        </CardBody>
      </Card>

      {loading ? (
        <div className="h-40 animate-pulse rounded-xl bg-surface" />
      ) : providers.length === 0 ? (
        <Card>
          <CardBody className="py-12 text-center text-sm text-muted">
            No provider configured. Add one and run the live test to enable AI.
          </CardBody>
        </Card>
      ) : (
        providers.map((provider) => (
          <Card key={provider.id}>
            <CardHeader
              title={
                <span className="inline-flex items-center gap-2">
                  <Server className="h-4 w-4 text-brand-500" />
                  {provider.name}
                </span>
              }
              subtitle={`${provider.base_url} · ${provider.auth_type}`}
              actions={
                <div className="flex items-center gap-2">
                  <Badge tone={provider.is_active ? 'success' : 'neutral'}>
                    {provider.is_active ? 'Active' : 'Disabled'}
                  </Badge>
                  <button
                    onClick={() => openEdit(provider)}
                    className="text-xs font-medium text-brand-600 hover:text-brand-700"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => toggleProvider(provider)}
                    className="text-xs font-medium text-muted hover:text-ink"
                  >
                    {provider.is_active ? 'Disable' : 'Enable'}
                  </button>
                </div>
              }
            />
            <CardBody className="space-y-4">
              <div className="flex flex-wrap items-center gap-3 text-xs text-muted">
                <span className="inline-flex items-center gap-1">
                  <KeyRound className="h-3.5 w-3.5" />
                  {provider.has_key ? provider.api_key_masked : 'no key'}
                </span>
                {provider.auth_key_name && <span>key field: {provider.auth_key_name}</span>}
              </div>

              <div className="divide-y divide-line rounded-lg border border-line">
                {provider.models.length === 0 && (
                  <p className="px-4 py-3 text-sm text-muted">No models yet.</p>
                )}
                {provider.models.map((model) => (
                  <div
                    key={model.id}
                    className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div>
                      <p className="flex items-center gap-2 text-sm font-medium text-ink">
                        {model.display_name}
                        <Badge tone={model.kind === 'chat' ? 'brand' : 'info'}>
                          {model.kind}
                        </Badge>
                        <Badge tone={model.is_active ? 'success' : 'neutral'}>
                          {model.kind === 'embedding'
                            ? model.is_active
                              ? 'active'
                              : 'stored'
                            : model.is_active
                              ? 'active'
                              : 'disabled'}
                        </Badge>
                        {model.kind === 'chat' && model.is_default && (
                          <Badge tone="success">
                            <Star className="h-3 w-3" /> default
                          </Badge>
                        )}
                      </p>
                      <p className="mt-0.5 font-mono text-xs text-muted">{model.name}</p>
                      <p className="text-xs text-muted">
                        {model.kind === 'chat'
                          ? `window ${model.context_window.toLocaleString()} · output ${model.max_output_tokens.toLocaleString()}`
                          : `${model.embedding_dimensions ?? '?'} dimensions`}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      <Button size="sm" variant="ghost" onClick={() => testModel(model)}>
                        Test
                      </Button>
                      {!model.is_default && (
                        <Button size="sm" variant="ghost" onClick={() => setDefault(model)}>
                          {model.kind === 'embedding' ? 'Activate' : 'Set default'}
                        </Button>
                      )}
                      {model.kind === 'chat' && (
                        <Button size="sm" variant="ghost" onClick={() => toggleModel(model)}>
                          {model.is_active ? 'Disable' : 'Enable'}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => openModelForm(provider, model)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => deleteModel(model)}>
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => openModelForm(provider, undefined, 'chat')}>
                  <Plus className="h-3.5 w-3.5" /> Add chat model
                </Button>
                <Button size="sm" variant="outline" onClick={() => openModelForm(provider, undefined, 'embedding')}>
                  <Plus className="h-3.5 w-3.5" /> Add embedding model
                </Button>
                <Button size="sm" variant="ghost" onClick={() => deleteProvider(provider)}>
                  <Trash2 className="h-3.5 w-3.5" /> Delete provider
                </Button>
              </div>
            </CardBody>
          </Card>
        ))
      )}

      {addOpen && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-4">
          <div className="my-8 w-full max-w-2xl rounded-xl border border-line bg-surface">
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <div>
                <h2 className="text-base font-semibold text-ink">
                  {editingProvider
                    ? `Edit ${editingProvider.name}`
                    : form.test_kind === 'embedding'
                      ? 'Add embedding model'
                      : 'Add AI provider'}
                </h2>
                <p className="text-xs text-muted">
                  {editingProvider
                    ? 'Update endpoints or re-save the API key. Leave the key blank to keep it.'
                    : form.test_kind === 'embedding'
                      ? 'Connect a provider and verify its embedding dimensions before saving.'
                      : 'Connect a provider and verify a live chat response before saving.'}
                </p>
              </div>
              <button onClick={() => setAddOpen(false)} className="text-muted hover:text-ink">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 p-5">
              <div className="grid gap-4 md:grid-cols-2">
                <Input
                  label="Name"
                  value={form.name}
                  onChange={(e) => updateForm('name', e.target.value)}
                  placeholder="Mistral, OpenAI, local gateway…"
                />
                <div>
                  <label className="input-label">Adapter</label>
                  <select
                    value={form.adapter}
                    onChange={(e) => updateForm('adapter', e.target.value)}
                    className="input-field"
                  >
                    <option value="openai_compatible">OpenAI-compatible</option>
                    <option value="custom">Custom endpoints</option>
                  </select>
                </div>
              </div>

              <Input
                label={isCustom ? 'Reference base URL' : 'Base URL'}
                value={form.base_url}
                onChange={(e) => updateForm('base_url', e.target.value)}
                placeholder="https://api.mistral.ai/v1"
                hint={
                  isCustom
                    ? 'Required for display. The full endpoint URLs below are used for requests.'
                    : 'Include /v1. The app calls /chat/completions, /embeddings and /models.'
                }
              />

              {isCustom && (
                <div className="space-y-3 rounded-lg border border-line bg-canvas/60 p-4">
                  <div>
                    <p className="text-sm font-medium text-ink">Custom endpoints</p>
                    <p className="text-xs text-muted">
                      Use the exact URLs your provider exposes. No path is appended.
                    </p>
                  </div>
                  <Input
                    label="Chat completions URL"
                    value={form.chat_url}
                    onChange={(e) => updateForm('chat_url', e.target.value)}
                    placeholder="https://api.example.com/v1/chat/completions"
                    hint={
                      form.test_kind === 'chat'
                        ? 'Required for this chat provider.'
                        : 'Optional; used if this provider also serves chat.'
                    }
                  />
                  <Input
                    label="Embeddings URL"
                    value={form.embeddings_url}
                    onChange={(e) => updateForm('embeddings_url', e.target.value)}
                    placeholder="https://api.example.com/v1/embeddings"
                    hint={
                      form.test_kind === 'embedding'
                        ? 'Required for this embedding model.'
                        : 'Optional; used if this provider also serves embeddings.'
                    }
                  />
                  <Input
                    label="Models URL"
                    value={form.models_url}
                    onChange={(e) => updateForm('models_url', e.target.value)}
                    placeholder="https://api.example.com/v1/models"
                    hint="Used by Load models for discovery."
                  />
                </div>
              )}

              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="input-label">Authentication</label>
                  <select
                    value={form.auth_type}
                    onChange={(e) => updateForm('auth_type', e.target.value)}
                    className="input-field"
                  >
                    {AUTH_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                {form.auth_type === 'basic' ? (
                  <Input
                    label="Username"
                    value={form.auth_username}
                    onChange={(e) => updateForm('auth_username', e.target.value)}
                  />
                ) : authNeedsName ? (
                  <Input
                    label={form.auth_type === 'query' ? 'Query parameter name' : 'Header name'}
                    value={form.auth_key_name}
                    onChange={(e) => updateForm('auth_key_name', e.target.value)}
                    placeholder={form.auth_type === 'query' ? 'key' : 'x-api-key'}
                  />
                ) : (
                  <div />
                )}
              </div>

              {form.auth_type !== 'none' && (
                <Input
                  label="API key"
                  type="password"
                  value={form.api_key}
                  onChange={(e) => updateForm('api_key', e.target.value)}
                  placeholder="Stored encrypted; shown masked afterwards"
                />
              )}

              <div className="rounded-lg border border-line p-4">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-medium text-ink">Test a model</p>
                  <Button size="sm" variant="outline" loading={loadingModels} onClick={fetchModels}>
                    <RefreshCw className="h-3.5 w-3.5" /> Load models
                  </Button>
                </div>

                <div className="grid gap-3 md:grid-cols-2">
                  <div>
                    <label className="input-label">Model</label>
                    <input
                      value={form.test_model}
                      onChange={(e) => updateForm('test_model', e.target.value)}
                      className="input-field"
                      placeholder="mistral-small-latest"
                    />
                    {remoteModels.length > 0 && (
                      <select
                        className="input-field mt-2"
                        value={
                          remoteModels.some((m) => m.id === form.test_model)
                            ? form.test_model
                            : ''
                        }
                        onChange={(e) => {
                          const selected = remoteModels.find((m) => m.id === e.target.value);
                          if (selected) applyRemoteModel(selected);
                        }}
                      >
                        {selectOptions}
                      </select>
                    )}
                    <p className="mt-1 text-xs text-muted">
                      If model discovery fails, type the model name manually.
                    </p>
                  </div>
                  <div className="flex items-end">
                    <Badge tone={form.test_kind === 'embedding' ? 'info' : 'brand'}>
                      {form.test_kind === 'embedding' ? 'Embedding model' : 'Chat provider'}
                    </Badge>
                  </div>
                </div>

                {form.test_kind === 'chat' && !editingProvider && (
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <Input
                      label="Context window"
                      type="number"
                      value={String(form.test_context_window)}
                      onChange={(e) =>
                        updateForm('test_context_window', Number(e.target.value))
                      }
                      hint="Total tokens the model can accept. Auto-filled when the provider exposes it."
                    />
                    <Input
                      label="Max output tokens"
                      type="number"
                      value={String(form.test_max_output_tokens)}
                      onChange={(e) =>
                        updateForm('test_max_output_tokens', Number(e.target.value))
                      }
                      hint="Maximum tokens generated per reply."
                    />
                  </div>
                )}

                {form.test_kind === 'embedding' && (
                  <Input
                    label="Expected dimensions"
                    type="number"
                    value={form.test_dimensions}
                    onChange={(e) => updateForm('test_dimensions', e.target.value)}
                    placeholder="1024"
                    hint="The provider must return exactly this many values; the test fails otherwise."
                  />
                )}

                <div className="mt-3 flex flex-wrap items-center gap-2">
                  <Button size="sm" onClick={testProvider} loading={testing}>
                    <Cpu className="h-3.5 w-3.5" />
                    {form.test_kind === 'embedding' ? 'Test embedding' : 'Ask “What is the capital of India?”'}
                  </Button>
                  {testPassed && (
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
                      <CheckCircle2 className="h-3.5 w-3.5" /> passed
                    </span>
                  )}
                </div>

                {testAnswer && (
                  <div className="mt-3 rounded-lg border border-green-200 bg-success-soft p-3 text-sm text-success">
                    {testAnswer}
                  </div>
                )}
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setAddOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={saveProvider}
                  loading={saving}
                  disabled={!editingProvider && !testPassed}
                >
                  {editingProvider
                    ? 'Save changes'
                    : form.test_kind === 'embedding'
                      ? 'Add embedding model'
                      : 'Add AI provider'}
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {modelProvider && (
        <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-ink/40 p-4">
          <div className="my-8 w-full max-w-lg rounded-xl border border-line bg-surface">
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <div>
                <h2 className="text-base font-semibold text-ink">
                  {modelForm.id ? 'Edit model' : 'Add custom model'}
                </h2>
                <p className="text-xs text-muted">{modelProvider.name}</p>
              </div>
              <button
                onClick={() => setModelProvider(null)}
                className="text-muted hover:text-ink"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-4 p-5">
              <div className="grid gap-4 md:grid-cols-2">
                <Input
                  label="Model name"
                  value={modelForm.name}
                  onChange={(e) => setModelForm({ ...modelForm, name: e.target.value })}
                  placeholder="mistral-small-latest"
                  disabled={!!modelForm.id}
                />
                <Input
                  label="Display name"
                  value={modelForm.display_name}
                  onChange={(e) =>
                    setModelForm({ ...modelForm, display_name: e.target.value })
                  }
                />
              </div>

              <div>
                <label className="input-label">Kind</label>
                <select
                  value={modelForm.kind}
                  onChange={(e) =>
                    setModelForm({
                      ...modelForm,
                      kind: e.target.value as 'chat' | 'embedding',
                    })
                  }
                  className="input-field"
                  disabled={!!modelForm.id}
                >
                  <option value="chat">Chat</option>
                  <option value="embedding">Embedding</option>
                </select>
              </div>

              {modelForm.kind === 'chat' ? (
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label="Context window"
                    type="number"
                    value={String(modelForm.context_window)}
                    onChange={(e) =>
                      setModelForm({ ...modelForm, context_window: Number(e.target.value) })
                    }
                    hint="From the provider's model documentation."
                  />
                  <Input
                    label="Max output tokens"
                    type="number"
                    value={String(modelForm.max_output_tokens)}
                    onChange={(e) =>
                      setModelForm({
                        ...modelForm,
                        max_output_tokens: Number(e.target.value),
                      })
                    }
                  />
                </div>
              ) : null}

              {modelForm.kind === 'chat' && (
                <p className="rounded-md border border-line bg-canvas/60 px-3 py-2 text-xs text-muted">
                  These limits must cover every plan: context ≥ plan input + response + 128,
                  and max output ≥ the largest plan response.
                </p>
              )}

              {modelForm.kind === 'chat' && (
                <div>
                  <div className="mb-1.5 flex items-center justify-between">
                    <label className="input-label mb-0">System prompt</label>
                    <button
                      type="button"
                      className="text-xs font-medium text-brand hover:underline"
                      onClick={() =>
                        setModelForm({
                          ...modelForm,
                          system_prompt: defaults?.default_system_prompt ?? '',
                        })
                      }
                    >
                      Use default
                    </button>
                  </div>
                  <textarea
                    rows={8}
                    value={modelForm.system_prompt}
                    onChange={(e) =>
                      setModelForm({ ...modelForm, system_prompt: e.target.value })
                    }
                    placeholder={
                      defaults?.default_system_prompt ||
                      'Leave blank to use the built-in default prompt.'
                    }
                    className={`input-field font-mono text-xs leading-relaxed ${
                      promptOverLimit ? 'border-red-300' : ''
                    }`}
                  />
                  <div className="mt-1 flex items-center justify-between gap-3 text-xs">
                    <span className="text-muted">
                      Used for every chat on this model. Leave blank for the default.
                    </span>
                    <span
                      className={
                        promptOverLimit
                          ? 'shrink-0 text-danger'
                          : 'shrink-0 text-muted'
                      }
                    >
                      {promptWordCount}/
                      {defaults?.system_prompt_max_words ?? 1200} words ·{' '}
                      {modelForm.system_prompt.length}/
                      {defaults?.system_prompt_max_chars ?? 8000} chars
                    </span>
                  </div>
                </div>
              )}

              {modelForm.kind === 'embedding' && (
                <Input
                  label="Embedding dimensions"
                  type="number"
                  value={modelForm.embedding_dimensions}
                  onChange={(e) =>
                    setModelForm({
                      ...modelForm,
                      embedding_dimensions: e.target.value,
                    })
                  }
                  hint={`Must match the database vector column (${
                    defaults?.vector_dimensions ?? 1024
                  }).`}
                />
              )}

              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setModelProvider(null)}>
                  Cancel
                </Button>
                <Button
                  onClick={saveModel}
                  loading={savingModel}
                  disabled={!modelForm.name || promptOverLimit}
                >
                  Save model
                </Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {noticeOpen && pendingModel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="w-full max-w-lg rounded-xl border border-line bg-surface">
            <div className="flex items-center justify-between border-b border-line px-5 py-4">
              <h2 className="text-base font-semibold text-ink">
                Change embedding model?
              </h2>
              <button
                onClick={() => {
                  setNoticeOpen(false);
                  setPendingModel(null);
                }}
                className="text-muted hover:text-ink"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-3 p-5 text-sm text-ink">
              <p>
                Switching to <strong>{pendingModel.display_name}</strong> will re-index{' '}
                <strong>{pendingDocs}</strong> document(s) from MinIO.
              </p>
              <p className="text-muted">
                Existing vectors were produced by the previous model and are not
                comparable. Each document is excluded from RAG until its new vectors are
                ready. Chat keeps working during the job.
              </p>
              <p className="text-xs text-muted">
                The job runs in the background. Progress appears on this page.
              </p>
            </div>

            <div className="flex justify-end gap-2 border-t border-line px-5 py-4">
              <Button
                variant="ghost"
                onClick={() => {
                  setNoticeOpen(false);
                  setPendingModel(null);
                }}
              >
                Cancel
              </Button>
              <Button onClick={confirmEmbeddingChange}>Change and re-index</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
