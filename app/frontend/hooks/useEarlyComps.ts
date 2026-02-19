/**
 * Hook for fetching early game compositions with transition links to late game comps
 */

import { useState, useEffect, useCallback, useMemo } from 'react';

// Transition link to a late game comp
export interface ForwardLink {
  target_cluster_id: number;
  probability: number;
}

// Early game composition stats
export interface EarlyCompStats {
  avg_placement: number;
  games: number;
  winrate: number;
  matchup_winrate: number;
  avg_hp: number;
}

// Early game composition
export interface EarlyComp {
  comp_id: string;
  cluster: string;
  units: string[];
  stats: EarlyCompStats;
  star_levels: Record<string, number>;
  forwards_links: ForwardLink[];
  void_probability: number;
}

export interface EarlyCompsResponse {
  stage: string;
  source: string;
  total_comps: number;
  total_matchups: number;
  overall_stats: {
    avg_placement: number;
    avg_hp: number;
  };
  comps: EarlyComp[];
}

interface UseEarlyCompsOptions {
  apiUrl?: string;
  limit?: number;
  enabled?: boolean;
}

interface UseEarlyCompsResult {
  data: EarlyCompsResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
  // Helper function to get early comps that transition to a given late game cluster
  getTransitionsTo: (targetClusterId: number | string) => EarlyCompWithTransition[];
}

// Early comp with its specific transition probability to a target comp
export interface EarlyCompWithTransition extends EarlyComp {
  transitionProbability: number;
}

// Empty string uses Vite proxy in development
const DEFAULT_API_URL = '';

export function useEarlyComps(options: UseEarlyCompsOptions = {}): UseEarlyCompsResult {
  const {
    apiUrl = DEFAULT_API_URL,
    limit = 35,
    enabled = true,
  } = options;

  const [data, setData] = useState<EarlyCompsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchEarlyComps = useCallback(async () => {
    if (!enabled) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiUrl}/api/early-comps?limit=${limit}`);

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('Early comps data not available. Add local data/meta/early_comps.json first.');
        }
        throw new Error(`Failed to fetch early comps: ${response.statusText}`);
      }

      const result: EarlyCompsResponse = await response.json();
      setData(result);
      console.log('[EarlyComps] Loaded', result.comps.length, 'early comps');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      console.error('[EarlyComps] Error:', message);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, limit, enabled]);

  // Initial fetch on mount
  useEffect(() => {
    if (enabled) {
      fetchEarlyComps();
    }
  }, [fetchEarlyComps, enabled]);

  // Helper function to find early comps that transition to a specific late game comp
  const getTransitionsTo = useCallback((targetClusterId: number | string): EarlyCompWithTransition[] => {
    if (!data?.comps) return [];

    const targetId = typeof targetClusterId === 'string'
      ? parseInt(targetClusterId, 10)
      : targetClusterId;

    const matching: EarlyCompWithTransition[] = [];

    for (const comp of data.comps) {
      const link = comp.forwards_links.find(l => l.target_cluster_id === targetId);
      if (link && link.probability > 0) {
        matching.push({
          ...comp,
          transitionProbability: link.probability,
        });
      }
    }

    // Sort by transition probability (highest first)
    matching.sort((a, b) => b.transitionProbability - a.transitionProbability);

    return matching;
  }, [data]);

  return {
    data,
    loading,
    error,
    refetch: fetchEarlyComps,
    getTransitionsTo,
  };
}

export default useEarlyComps;
