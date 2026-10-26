import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import type { ReactNode } from 'react';
import { useNavigate } from 'react-router-dom';
import api from '../api';
import { usePlatformConfig } from '../hooks/usePlatformConfig';
import type { PlatformConfig } from '../hooks/usePlatformConfig';

export interface Me {
  id: string;
  username?: string | null;
  email?: string | null;
  mobile?: string | null;
  first_name: string;
  last_name?: string | null;
  auth_provider: string;
  email_verified_at?: string | null;
  telegram_id?: number | null;
}

export interface Quota {
  can_send: boolean;
  daily_messages_used: number;
  daily_messages_limit: number;
  monthly_messages_used: number;
  monthly_messages_limit: number;
  daily_remaining: number;
  monthly_remaining: number;
  sessions_used: number;
  max_sessions: number;
  plan_name: string;
}

export interface Conversation {
  id: string;
  title?: string | null;
  total_messages: number;
  started_at: string;
  last_activity_at: string;
}

interface UserContextValue {
  user: Me | null;
  quota: Quota | null;
  config: PlatformConfig | null;
  freeMode: boolean;
  billingEnabled: boolean;
  loading: boolean;
  conversations: Conversation[];
  conversationsLoading: boolean;
  activeId: string | null;
  displayName: string;
  fullDisplay: string;
  setActiveId: (id: string | null) => void;
  loadConversations: () => Promise<Conversation[]>;
  createConversation: (title?: string) => Promise<Conversation | null>;
  renameConversation: (id: string, title: string) => Promise<boolean>;
  deleteConversation: (id: string) => Promise<boolean>;
  refreshQuota: () => Promise<void>;
  refreshUser: () => Promise<void>;
  logout: () => Promise<void>;
}

const UserContext = createContext<UserContextValue | null>(null);

export function UserProvider({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const { config, freeMode, billingEnabled } = usePlatformConfig();
  const [user, setUser] = useState<Me | null>(null);
  const [quota, setQuota] = useState<Quota | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationsLoading, setConversationsLoading] = useState(true);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const loadAccount = useCallback(async () => {
    let me;
    try {
      me = await api.get('/auth/me');
    } catch (error: any) {
      // Only an expired session sends the user back to sign in.
      if (mounted.current && error?.response?.status === 401) navigate('/login');
      return;
    }
    if (!mounted.current) return;
    setUser(me.data);
    setLoading(false);

    try {
      const quotaRes = await api.get('/ai/quota');
      if (mounted.current) setQuota(quotaRes.data);
    } catch {
    }
  }, [navigate]);

  const loadConversations = useCallback(async () => {
    try {
      const res = await api.get('/conversations/', { params: { page: 1, page_size: 100 } });
      const list: Conversation[] = res.data ?? [];
      if (mounted.current) setConversations(list);
      return list;
    } catch {
      if (mounted.current) setConversations([]);
      return [];
    } finally {
      if (mounted.current) setConversationsLoading(false);
    }
  }, []);

  const refreshQuota = useCallback(async () => {
    try {
      const res = await api.get('/ai/quota');
      if (mounted.current) setQuota(res.data);
    } catch {
    }
  }, []);

  useEffect(() => {
    // The global 401 event fires for any request in the app, including ones that
    const handleUnauthorized = async () => {
      try {
        await api.get('/auth/me');
      } catch (error: any) {
        if (error?.response?.status === 401 && mounted.current) navigate('/login');
      }
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);
    void loadAccount();
    void loadConversations();
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized);
  }, [loadAccount, loadConversations, navigate]);

  const createConversation = useCallback(
    async (title?: string) => {
      try {
        const res = await api.post('/conversations/', title ? { title } : {});
        const created: Conversation = {
          id: res.data.id,
          title: res.data.title,
          total_messages: res.data.total_messages ?? 0,
          started_at: res.data.started_at,
          last_activity_at: res.data.last_activity_at,
        };
        setConversations((current) => [created, ...current]);
        setActiveId(created.id);
        await refreshQuota();
        return created;
      } catch {
        return null;
      }
    },
    [refreshQuota]
  );

  const renameConversation = useCallback(async (id: string, title: string) => {
    try {
      const res = await api.patch(`/conversations/${id}`, { title });
      setConversations((current) =>
        current.map((item) => (item.id === id ? { ...item, title: res.data.title } : item))
      );
      return true;
    } catch {
      return false;
    }
  }, []);

  const deleteConversation = useCallback(
    async (id: string) => {
      try {
        await api.delete(`/conversations/${id}`);
        setConversations((current) => current.filter((item) => item.id !== id));
        setActiveId((current) => (current === id ? null : current));
        await refreshQuota();
        return true;
      } catch {
        return false;
      }
    },
    [refreshQuota]
  );

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout');
    } catch {
      // The UI still returns to login if the request fails.
    }
    navigate('/login');
  }, [navigate]);

  const displayName = user ? user.first_name : '';
  const fullDisplay = user
    ? [user.first_name, user.last_name].filter(Boolean).join(' ') || user.username || 'Learner'
    : '';

  const value = useMemo<UserContextValue>(
    () => ({
      user,
      quota,
      config,
      freeMode,
      billingEnabled,
      loading,
      conversations,
      conversationsLoading,
      activeId,
      displayName,
      fullDisplay,
      setActiveId,
      loadConversations,
      createConversation,
      renameConversation,
      deleteConversation,
      refreshQuota,
      refreshUser: loadAccount,
      logout,
    }),
    [
      user,
      quota,
      config,
      freeMode,
      billingEnabled,
      loading,
      conversations,
      conversationsLoading,
      activeId,
      displayName,
      fullDisplay,
      loadConversations,
      createConversation,
      renameConversation,
      deleteConversation,
      refreshQuota,
      loadAccount,
      logout,
    ]
  );

  return <UserContext.Provider value={value}>{children}</UserContext.Provider>;
}

export function useUser(): UserContextValue {
  const context = useContext(UserContext);
  if (!context) throw new Error('useUser must be used inside UserProvider');
  return context;
}
