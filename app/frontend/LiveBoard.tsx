/**
 * LiveBoard - Connects to WebSocket for real-time board updates
 * Uses sample data for opponent (since Overwolf doesn't provide opponent board)
 */

import React from 'react';
import { useGameState } from './hooks/useGameState';
import { transformBoardUnits } from './utils/transformBoardData';
import DualBoard, { SAMPLE_OPPONENT_UNITS } from './DualBoard';
import BoardWithUnits from './BoardWithUnits';

interface LiveBoardProps {
  showDualBoard?: boolean;  // Show both player and opponent boards
  wsUrl?: string;           // WebSocket URL override
}

const LiveBoard: React.FC<LiveBoardProps> = ({
  showDualBoard = true,
  wsUrl,
}) => {
  const { state, isConnected, error } = useGameState({
    url: wsUrl,
    enabled: true,
  });

  // Transform backend data to overlay format
  const playerUnits = state?.board_units
    ? transformBoardUnits(state.board_units)
    : [];

  // Connection status indicator
  const statusColor = isConnected ? '#00ff00' : '#ff0000';
  const statusText = isConnected
    ? `Connected • Stage ${state?.stage || '0-0'} • ${playerUnits.length} units`
    : error || 'Disconnected';

  return (
    <div className="flex flex-col gap-2">
      {/* Status bar */}
      <div
        className="flex items-center gap-2 px-3 py-1 rounded text-xs"
        style={{ backgroundColor: 'rgba(0,0,0,0.7)' }}
      >
        <div
          className="w-2 h-2 rounded-full"
          style={{ backgroundColor: statusColor }}
        />
        <span className="text-white font-mono">{statusText}</span>
        {state && (
          <span className="text-gray-400 ml-auto">
            {state.player.name} • {state.player.health} HP
          </span>
        )}
      </div>

      {/* Board(s) */}
      {showDualBoard ? (
        <DualBoard
          playerUnits={playerUnits}
          opponentUnits={SAMPLE_OPPONENT_UNITS}  // Mock opponent (no live data available)
        />
      ) : (
        <BoardWithUnits
          units={playerUnits}
          isRotated={false}
        />
      )}

      {/* Debug info (can be removed in production) */}
      {state && (
        <div
          className="text-xs font-mono p-2 rounded"
          style={{ backgroundColor: 'rgba(0,0,0,0.5)', color: '#888' }}
        >
          <div>Phase: {state.game_phase} | XP: {state.xp} | Win%: {state.win_chance ?? 'N/A'}</div>
          <div>Bench: {state.bench_units.length} units</div>
          {state.augments.length > 0 && (
            <div>Augments: {state.augments.join(', ')}</div>
          )}
        </div>
      )}
    </div>
  );
};

export default LiveBoard;
