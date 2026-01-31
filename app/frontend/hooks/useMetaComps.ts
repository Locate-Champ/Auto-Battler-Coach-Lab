/**
 * Hook for fetching meta compositions from MetaTFT via the backend API
 */

import { useState, useEffect, useCallback } from 'react';

// Build info for item recommendations
export interface CompBuild {
  unit: string;
  items: string[];
  games: number;
  avg_placement: number;
  place_change: number;
}

// Trait info
export interface CompTrait {
  name: string;
  count: number;
}

// Types matching the backend /api/meta-comps response (MetaTFT format)
export interface MetaComp {
  cluster_id: number | string;
  tier: 'S' | 'A' | 'B' | 'C';
  name: string;
  units: string[];
  traits: CompTrait[];
  avg_placement: number;
  games_played: number;
  top4_rate: number;
  win_rate: number;
  difficulty: number;
  levelling: string;
  builds: CompBuild[];
}

export interface MetaCompsResponse {
  patch: string;
  source: string;
  total_games: number;
  total_comps: number;
  tier_counts: {
    S: number;
    A: number;
    B: number;
    C: number;
  };
  last_updated?: string | null;
  comps: MetaComp[];
}

interface UseMetaCompsOptions {
  apiUrl?: string;
  limit?: number;
  enabled?: boolean;
  refetchInterval?: number | null;
}

interface UseMetaCompsResult {
  data: MetaCompsResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

// Empty string uses Vite proxy in development
const DEFAULT_API_URL = '';

export function useMetaComps(options: UseMetaCompsOptions = {}): UseMetaCompsResult {
  const {
    apiUrl = DEFAULT_API_URL,
    limit = 25,
    enabled = true,
    refetchInterval = null,
  } = options;

  const [data, setData] = useState<MetaCompsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchMetaComps = useCallback(async () => {
    if (!enabled) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiUrl}/api/meta-comps?limit=${limit}`);

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Meta data not available. Run fetch_meta_data.py first.');
        }
        throw new Error(`Failed to fetch meta comps: ${response.statusText}`);
      }

      const result: MetaCompsResponse = await response.json();
      setData(result);
      console.log('[MetaComps] Loaded', result.comps.length, 'comps from patch', result.patch);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      console.error('[MetaComps] Error:', message);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, limit, enabled]);

  // Initial fetch on mount
  useEffect(() => {
    if (enabled) {
      fetchMetaComps();
    }
  }, [fetchMetaComps, enabled]);

  // Optional refetch interval
  useEffect(() => {
    if (!enabled || !refetchInterval) return;

    const interval = setInterval(fetchMetaComps, refetchInterval);
    return () => clearInterval(interval);
  }, [fetchMetaComps, enabled, refetchInterval]);

  return {
    data,
    loading,
    error,
    refetch: fetchMetaComps,
  };
}

export default useMetaComps;
