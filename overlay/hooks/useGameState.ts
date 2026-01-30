/**
 * WebSocket hook for connecting to TFT Coach backend
 * Receives live game state updates including board_units
 */

import { useState, useEffect, useCallback, useRef } from 'react';

// Types matching the backend GameState.to_dict() output
export interface BoardUnitData {
  id: string | null;
  character_id: string;
  name: string;
  stars: number;
  items: string[];
  position: { row: number; col: number } | null;
}

export interface BenchUnitData {
  character_id: string;
  name: string;
  stars: number;
  items: string[];
}

export interface PlayerData {
  name: string;
  health: number;
  level: number;
}

export interface OpponentData {
  name: string;
  health: number;
  level: number;
}

export interface OpponentBoardUnit {
  character_id: string;
  name: string;
  stars: number;
}

export interface GameState {
  game_id: string | null;
  game_phase: string;
  stage: string;
  game_start_time: string | null;
  last_update: string;
  player: PlayerData;
  xp: string;
  gold: number;
  win_streak: number;
  loss_streak: number;
  augments: string[];
  augment_options: string[];
  augment_armory_active: boolean;
  opponents: Record<string, OpponentData>;
  opponent_boards: Record<string, OpponentBoardUnit[]>;
  currently_scouting: string | null;
  win_chance: number | null;
  board_units: BoardUnitData[];
  bench_units: BenchUnitData[];
}

interface UseGameStateOptions {
  url?: string;
  reconnectInterval?: number;
  enabled?: boolean;
}

interface UseGameStateResult {
  state: GameState | null;
  isConnected: boolean;
  error: string | null;
  reconnect: () => void;
}

const DEFAULT_WS_URL = 'ws://127.0.0.1:8765/ws';

export function useGameState(options: UseGameStateOptions = {}): UseGameStateResult {
  const {
    url = DEFAULT_WS_URL,
    reconnectInterval = 3000,
    enabled = true,
  } = options;

  const [state, setState] = useState<GameState | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);

  const connect = useCallback(() => {
    if (!enabled) return;

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
    }

    try {
      console.log(`[WS] Connecting to ${url}...`);
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('[WS] Connected');
        setIsConnected(true);
        setError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as GameState;
          setState(data);
          console.log('[WS] State updated:', data.stage, `${data.board_units.length} units`);
        } catch (e) {
          console.error('[WS] Failed to parse message:', e);
        }
      };

      ws.onerror = (event) => {
        console.error('[WS] Error:', event);
        setError('WebSocket error');
      };

      ws.onclose = () => {
        console.log('[WS] Disconnected');
        setIsConnected(false);
        wsRef.current = null;

        // Auto-reconnect
        if (enabled) {
          reconnectTimeoutRef.current = window.setTimeout(() => {
            console.log('[WS] Attempting reconnect...');
            connect();
          }, reconnectInterval);
        }
      };
    } catch (e) {
      console.error('[WS] Failed to connect:', e);
      setError('Failed to connect');
    }
  }, [url, reconnectInterval, enabled]);

  const reconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    connect();
  }, [connect]);

  // Connect on mount
  useEffect(() => {
    if (enabled) {
      connect();
    }

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [connect, enabled]);

  return { state, isConnected, error, reconnect };
}

export default useGameState;
