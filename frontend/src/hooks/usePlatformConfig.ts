import { useEffect, useState } from 'react';
import api from '../api';

export interface PlatformPlan {
  id: string;
  name: string;
  display_name: string;
  description?: string | null;
  price_inr: number;
  validity_days: number;
  limits: Record<string, any>;
}

export interface PlatformConfig {
  platform_mode: 'paid' | 'free';
  billing_enabled: boolean;
  free_plan: PlatformPlan | null;
  plans: PlatformPlan[];
}

export function usePlatformConfig() {
  const [config, setConfig] = useState<PlatformConfig | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get('/config/public')
      .then((res) => {
        if (!cancelled) setConfig(res.data);
      })
      .catch(() => {
        // Fall back to paid-mode rendering; the server still enforces the real mode.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return {
    config,
    freeMode: config?.platform_mode === 'free',
    billingEnabled: config?.billing_enabled ?? true,
  };
}
