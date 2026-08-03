import { useState, useEffect } from 'react';
import {
  Zap,
  MessageSquare,
  Clock,
  Crown,
  BookOpen,
  AlertCircle,
  CheckCircle2,
  Sparkles,
  ArrowUpRight,
  LayoutDashboard,
  CreditCard,
  MessageCircle,
  Calendar
} from 'lucide-react';

declare global {
  interface Window {
    Telegram?: any;
  }
}

import api from '../../api';

interface QuotaData {
  daily_messages_used: number;
  daily_messages_limit: number;
  monthly_messages_used: number;
  monthly_messages_limit: number;
  total_tokens_consumed: number;
  can_query: boolean;
  reset_at: string;
}

interface SubscriptionData {
  plan_name: string;
  status: string;
  expires_at: string | null;
  started_at: string | null;
  total_messages_used: number;
  total_conversations: number;
  active_conversations: number;
  plan_snapshot: {
    display_name: string;
    max_daily_messages: number;
    max_monthly_messages: number;
    max_documents: number;
  };
}

interface PaymentHistory {
  id: string;
  merchant_txn_id: string;
  phonepe_txn_id: string | null;
  amount_inr: number;
  currency: string;
  status: string;
  payment_method: string | null;
  plan_name: string | null;
  initiated_at: string;
  completed_at: string | null;
  created_at: string;
}

interface ConversationList {
  id: string;
  title: string | null;
  status: string;
  total_messages: number;
  started_at: string;
  last_activity_at: string;
  closed_at: string | null;
}

type TabType = 'overview' | 'billing' | 'conversations';

export default function UserDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');
  const [quota, setQuota] = useState<QuotaData | null>(null);
  const [subscription, setSubscription] = useState<SubscriptionData | null>(null);
  const [payments, setPayments] = useState<PaymentHistory[]>([]);
  const [conversations, setConversations] = useState<ConversationList[]>([]);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState(false);
  const [noTelegram, setNoTelegram] = useState(false);

  // Telegram WebApp
  const tg = window.Telegram?.WebApp;

  useEffect(() => {
    const init = async () => {
      try {
        console.log('Telegram WebApp:', tg);

        // Check Telegram environment
        if (!tg) {
          console.log('Telegram WebApp SDK not found');
          setNoTelegram(true);
          return;
        }

        // Initialize Telegram Mini App
        tg.ready();
        tg.expand();

        console.log('Init Data:', tg.initData);
        console.log('Unsafe Data:', tg.initDataUnsafe);

        // Get Telegram user
        const telegramUser = tg.initDataUnsafe?.user;

        if (!telegramUser || !tg.initData) {
          console.log('No Telegram user data');
          setNoTelegram(true);
          return;
        }

        // Authenticate backend
        await api.post('/auth/telegram/login', {
          init_data: tg.initData,
        });

        // Load dashboard data
        const [subRes, quotaRes, paymentsRes, convRes] = await Promise.all([
          api.get('/subscriptions/me'),
          api.get('/ai/quota'),
          api.get('/payments/history'),
          api.get('/conversations/?page=1&page_size=50')
        ]);

        setSubscription(subRes.data);
        setQuota(quotaRes.data);
        setPayments(paymentsRes.data);
        setConversations(convRes.data);

      } catch (err) {
        console.error(err);
        setAuthError(true);
      } finally {
        setLoading(false);
      }
    };

    init();
  }, []);

  const tgUser = tg?.initDataUnsafe?.user;

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="w-14 h-14 bg-gradient-to-br from-brand-500 to-purple-500 rounded-2xl flex items-center justify-center shadow-lg animate-pulse">
          <Sparkles className="text-white w-7 h-7" />
        </div>

        <div className="space-y-2 text-center">
          <div className="w-8 h-8 border-[3px] border-brand-200 border-t-brand-600 rounded-full animate-spin mx-auto"></div>
          <p className="text-slate-500 font-medium text-sm">
            Setting up your dashboard...
          </p>
        </div>
      </div>
    );
  }

  if (noTelegram) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-4">
        <div className="bg-amber-50 border border-amber-100 rounded-2xl p-6 text-center max-w-sm w-full">
          <AlertCircle className="w-10 h-10 text-amber-400 mx-auto mb-3" />

          <h3 className="font-bold text-slate-800 mb-2">
            Open Inside Telegram
          </h3>

          <p className="text-slate-500 text-sm mb-4">
            This dashboard only works inside Telegram Mini Apps.
          </p>

          <a
            href="https://t.me/vidhya_hub_bot"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-primary w-full inline-block text-sm text-center"
          >
            Open in Telegram
          </a>
        </div>
      </div>
    );
  }

  if (authError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] p-4">
        <div className="bg-red-50 border border-red-100 rounded-2xl p-6 text-center max-w-sm w-full">
          <AlertCircle className="w-10 h-10 text-red-400 mx-auto mb-3" />

          <h3 className="font-bold text-slate-800 mb-2">
            Authentication Failed
          </h3>

          <p className="text-slate-500 text-sm mb-4">
            Unable to connect your Telegram account.
          </p>

          <button
            onClick={() => window.location.reload()}
            className="btn-primary w-full text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  const dailyUsed = quota?.daily_messages_used ?? 0;
  const dailyMax = quota?.daily_messages_limit ?? 1;
  const dailyPct = Math.min((dailyUsed / dailyMax) * 100, 100);

  const isFreePlan = subscription?.plan_name === 'free' || !subscription?.plan_name;
  const planDisplayName = subscription?.plan_snapshot?.display_name || 'Free Plan';

  const expiresAt = subscription?.expires_at ? new Date(subscription.expires_at) : null;
  const daysLeft = expiresAt ? Math.max(0, Math.floor((expiresAt.getTime() - Date.now()) / (1000 * 60 * 60 * 24))) : null;

  const barColor =
    dailyPct > 90
      ? 'bg-red-500'
      : dailyPct > 70
        ? 'bg-orange-400'
        : 'bg-gradient-to-r from-brand-500 to-purple-500';

  const renderTabNavigation = () => (
    <div className="flex p-1 bg-slate-100 rounded-xl mb-4 overflow-x-auto no-scrollbar">
      <button
        onClick={() => setActiveTab('overview')}
        className={`flex items-center justify-center py-2 px-3 rounded-lg text-sm font-medium transition-all flex-1 whitespace-nowrap ${activeTab === 'overview' ? 'bg-white text-brand-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
      >
        <LayoutDashboard className="w-4 h-4 mr-2 shrink-0" />
        Overview
      </button>
      <button
        onClick={() => setActiveTab('billing')}
        className={`flex items-center justify-center py-2 px-3 rounded-lg text-sm font-medium transition-all flex-1 whitespace-nowrap ${activeTab === 'billing' ? 'bg-white text-brand-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
      >
        <CreditCard className="w-4 h-4 mr-2 shrink-0" />
        Billing
      </button>
      <button
        onClick={() => setActiveTab('conversations')}
        className={`flex items-center justify-center py-2 px-3 rounded-lg text-sm font-medium transition-all flex-1 whitespace-nowrap ${activeTab === 'conversations' ? 'bg-white text-brand-600 shadow-sm' : 'text-slate-500 hover:text-slate-700'
          }`}
      >
        <MessageCircle className="w-4 h-4 mr-2 shrink-0" />
        Chats
      </button>
    </div>
  );

  return (
    <div className="space-y-4 animate-in fade-in duration-500 pb-6 p-4">

      {/* HERO */}
      <div className="relative bg-gradient-to-br from-brand-600 via-purple-600 to-indigo-700 rounded-2xl p-5 text-white shadow-xl overflow-hidden mb-2">
        <div className="absolute top-0 right-0 w-36 h-36 bg-white/10 rounded-full -mr-12 -mt-12 blur-2xl" />
        <div className="absolute bottom-0 left-0 w-24 h-24 bg-white/5 rounded-full -ml-8 -mb-8 blur-xl" />

        <div className="relative z-10">
          <div className="flex items-start justify-between mb-4">
            <div>
              <p className="text-brand-100 text-xs font-medium uppercase tracking-widest mb-1">
                Welcome back
              </p>
              <h1 className="text-2xl font-bold leading-tight">
                {tgUser?.first_name || 'Student'} {tgUser?.last_name || ''}
              </h1>
              {tgUser?.username && (
                <p className="text-brand-200 text-sm mt-0.5">
                  @{tgUser.username}
                </p>
              )}
            </div>
            <div className="w-12 h-12 bg-white/20 backdrop-blur-md rounded-xl flex items-center justify-center border border-white/30 shrink-0">
              <Crown className="w-6 h-6 text-yellow-300" />
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 mt-2">
            <span className="inline-flex items-center bg-white/20 backdrop-blur-md px-3 py-1.5 rounded-lg text-xs font-semibold border border-white/30">
              <Sparkles className="w-3 h-3 mr-1.5 text-yellow-300" />
              {planDisplayName.toUpperCase()}
            </span>

            {subscription?.status === 'active' && (
              <span className="inline-flex items-center bg-green-500/20 px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-green-400/30">
                <CheckCircle2 className="w-3 h-3 mr-1 text-green-300" />
                Active
              </span>
            )}

            {daysLeft !== null && daysLeft <= 5 && daysLeft > 0 && (
              <span className="inline-flex items-center bg-orange-500/30 px-2.5 py-1.5 rounded-lg text-xs font-semibold border border-orange-400/30 text-white">
                <Clock className="w-3 h-3 mr-1" />
                {daysLeft}d left
              </span>
            )}
          </div>
        </div>
      </div>

      {renderTabNavigation()}

      {activeTab === 'overview' && (
        <div className="space-y-4 animate-in slide-in-from-right-4 duration-300">
          {/* DAILY LIMIT */}
          <div className="glass-card p-5">
            <div className="flex items-center justify-between mb-3">
              <h2 className="font-bold text-slate-800 flex items-center text-sm">
                <Zap className="w-4 h-4 mr-2 text-orange-500" />
                Today's AI Messages
              </h2>
              <span className="text-sm font-bold text-slate-700">
                {dailyUsed}
                <span className="text-slate-400 font-normal">
                  {' '} / {dailyMax}
                </span>
              </span>
            </div>
            <div className="w-full bg-slate-100 rounded-full h-2.5 overflow-hidden border border-slate-200 mb-2">
              <div
                className={`h-2.5 rounded-full transition-all duration-1000 ${barColor}`}
                style={{ width: `${dailyPct}%` }}
              />
            </div>
            <div className="flex justify-between mt-2 text-xs text-slate-500">
              <span>{Math.round(dailyPct)}% used</span>
              <span>Resets daily at midnight IST</span>
            </div>
          </div>

          {/* STATS */}
          <div className="grid grid-cols-2 gap-3">
            <div className="glass-card p-4">
              <div className="w-9 h-9 rounded-xl bg-blue-50 text-blue-500 flex items-center justify-center mb-3">
                <MessageSquare className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-500 font-medium">Total Messages</p>
              <p className="text-2xl font-bold text-slate-800 mt-0.5">
                {subscription?.total_messages_used ?? 0}
              </p>
            </div>

            <div className="glass-card p-4">
              <div className="w-9 h-9 rounded-xl bg-purple-50 text-purple-500 flex items-center justify-center mb-3">
                <BookOpen className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-500 font-medium">Conversations</p>
              <p className="text-2xl font-bold text-slate-800 mt-0.5">
                {subscription?.active_conversations ?? 0}
              </p>
            </div>

            <div className="glass-card p-4">
              <div className="w-9 h-9 rounded-xl bg-green-50 text-green-500 flex items-center justify-center mb-3">
                <Calendar className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-500 font-medium">Validity</p>
              {isFreePlan ? (
                <p className="text-xl font-bold text-slate-800 mt-0.5">Lifetime</p>
              ) : daysLeft !== null ? (
                <p className={`text-xl font-bold mt-0.5 ${daysLeft <= 5 ? 'text-red-500' : 'text-slate-800'}`}>
                  {daysLeft} <span className="text-sm font-medium text-slate-400">days left</span>
                </p>
              ) : (
                <p className="text-xl font-bold text-slate-800 mt-0.5">Lifetime</p>
              )}
            </div>

            <div className="glass-card p-4">
              <div className="w-9 h-9 rounded-xl bg-orange-50 text-orange-500 flex items-center justify-center mb-3">
                <Zap className="w-4 h-4" />
              </div>
              <p className="text-xs text-slate-500 font-medium">Monthly Msgs</p>
              <p className="text-xl font-bold text-slate-800 mt-0.5">
                {quota?.monthly_messages_used ?? 0}
                <span className="text-sm font-medium text-slate-400"> / {quota?.monthly_messages_limit ?? 0}</span>
              </p>
            </div>
          </div>

          {/* UPGRADE */}
          {isFreePlan && (
            <div className="relative bg-gradient-to-br from-slate-800 to-slate-900 rounded-2xl p-5 text-white overflow-hidden shadow-lg mt-4">
              <div className="relative z-10">
                <h3 className="text-lg font-bold mb-1">
                  Unlock Premium Features
                </h3>
                <p className="text-slate-300 text-sm mb-4">
                  Get higher daily limits, premium AI access, and more features.
                </p>
                <button
                  onClick={() => tg?.sendData?.('upgrade_requested')}
                  className="w-full flex items-center justify-center bg-gradient-to-r from-brand-500 to-purple-500 text-white font-semibold py-2.5 px-4 rounded-xl text-sm shadow-lg"
                >
                  View Plans
                  <ArrowUpRight className="w-4 h-4 ml-1.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'billing' && (
        <div className="space-y-3 animate-in slide-in-from-right-4 duration-300">
          <h2 className="font-bold text-slate-800 mb-2 px-1 text-sm flex items-center">
            <CreditCard className="w-4 h-4 mr-2 text-slate-500" />
            Payment History
          </h2>
          {payments.length === 0 ? (
            <div className="glass-card p-8 text-center">
              <CreditCard className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">No payment history</p>
              <p className="text-xs text-slate-400 mt-1">Your payments will appear here.</p>
            </div>
          ) : (
            payments.map((payment) => (
              <div key={payment.id} className="glass-card p-4 relative overflow-hidden">
                <div className={`absolute left-0 top-0 bottom-0 w-1 ${payment.status === 'success' ? 'bg-green-500' :
                    payment.status === 'failed' ? 'bg-red-500' : 'bg-yellow-500'
                  }`} />
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h3 className="font-semibold text-slate-800 text-sm">
                      {payment.plan_name || 'Unknown Plan'}
                    </h3>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {new Date(payment.created_at).toLocaleDateString(undefined, {
                        year: 'numeric',
                        month: 'short',
                        day: 'numeric'
                      })}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-slate-800">
                      ₹{(payment.amount_inr / 100).toFixed(2)}
                    </p>
                    <span className={`text-[10px] font-bold uppercase tracking-wider ${payment.status === 'success' ? 'text-green-600' :
                        payment.status === 'failed' ? 'text-red-600' : 'text-yellow-600'
                      }`}>
                      {payment.status}
                    </span>
                  </div>
                </div>
                {payment.merchant_txn_id && (
                  <p className="text-[10px] text-slate-400 font-mono truncate border-t border-slate-100 pt-2 mt-2">
                    TXN: {payment.merchant_txn_id}
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === 'conversations' && (
        <div className="space-y-3 animate-in slide-in-from-right-4 duration-300">
          <h2 className="font-bold text-slate-800 mb-2 px-1 text-sm flex items-center">
            <MessageCircle className="w-4 h-4 mr-2 text-slate-500" />
            Your Conversations
          </h2>
          {conversations.length === 0 ? (
            <div className="glass-card p-8 text-center">
              <MessageSquare className="w-12 h-12 text-slate-300 mx-auto mb-3" />
              <p className="text-slate-500 font-medium">No conversations yet</p>
              <p className="text-xs text-slate-400 mt-1">Start chatting in Telegram.</p>
            </div>
          ) : (
            conversations.map((conv) => (
              <div key={conv.id} className="glass-card p-4">
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-medium text-slate-800 text-sm line-clamp-1 max-w-[70%]">
                    {conv.title || 'New Chat'}
                  </h3>
                  {conv.status === 'active' ? (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-green-50 text-green-600 border border-green-200">
                      Active
                    </span>
                  ) : (
                    <span className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-50 text-slate-500 border border-slate-200">
                      {conv.status.charAt(0).toUpperCase() + conv.status.slice(1)}
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between mt-3 text-xs text-slate-500">
                  <span className="flex items-center">
                    <MessageSquare className="w-3 h-3 mr-1 text-slate-400" />
                    {conv.total_messages} msgs
                  </span>
                  <span className="flex items-center">
                    <Clock className="w-3 h-3 mr-1 text-slate-400" />
                    {new Date(conv.last_activity_at).toLocaleDateString(undefined, {
                      month: 'short',
                      day: 'numeric'
                    })}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

    </div>
  );
}