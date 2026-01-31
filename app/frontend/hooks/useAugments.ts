/**
 * Hook for fetching augment recommendations from the backend API
 */

import { useCallback, useEffect, useState } from 'react';

export interface AugmentRecommendation {
  name: string;
  tier: string;
  score: number;
  types: string[];
  rarity: string;
}

export interface AugmentsResponse {
  augments: AugmentRecommendation[];
}

interface UseAugmentsOptions {
  apiUrl?: string;
  enabled?: boolean;
}

interface UseAugmentsResult {
  data: AugmentsResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

// Empty string uses Vite proxy in development
const DEFAULT_API_URL = '';

export function useAugments(options: UseAugmentsOptions = {}): UseAugmentsResult {
  const { apiUrl = DEFAULT_API_URL, enabled = true } = options;

  const [data, setData] = useState<AugmentsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchAugments = useCallback(async () => {
    if (!enabled) return;

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${apiUrl}/api/augments`);

      if (!response.ok) {
        throw new Error(`Failed to fetch augments: ${response.statusText}`);
      }

      const result: AugmentsResponse = await response.json();
      setData(result);
      console.log('[Augments] Loaded', result.augments.length, 'augments');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      console.error('[Augments] Error:', message);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [apiUrl, enabled]);

  useEffect(() => {
    if (enabled) {
      fetchAugments();
    }
  }, [fetchAugments, enabled]);

  return {
    data,
    loading,
    error,
    refetch: fetchAugments,
  };
}

export default useAugments;
