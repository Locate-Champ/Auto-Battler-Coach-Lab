import React, { useState } from 'react';
import { GameState } from './hooks/useGameState';
import { usePoolTracker, Availability } from './hooks/usePoolTracker';

// Colors matching the overlay theme
const COLORS = {
  cardBg: '#1e1e2f',
  cardBorder: '#3a3a4f',
  gold: '#c9a033',
  cost: {
    1: '#5a5a6f',
    2: '#2ecc71',
    3: '#3498db',
    4: '#9b59b6',
    5: '#f1c40f',
  } as Record<number, string>,
  availability: {
    high: '#69db7c',
    medium: '#ffa94d',
    low: '#ff6b6b',
    none: '#495057',
  } as Record<Availability, string>,
};

// Pool sizes by cost
const POOL_SIZES: Record<number, number> = {
  1: 30,
  2: 25,
  3: 18,
  4: 10,
  5: 9,
};

// Champion cost mapping for Set 16
const CHAMPION_COSTS: Record<string, number> = {
  // 1-cost
  TFT16_Anivia: 1, TFT16_Ashe: 1, TFT16_Briar: 1, TFT16_Caitlyn: 1, TFT16_Elise: 1,
  TFT16_Illaoi: 1, TFT16_JarvanIV: 1, TFT16_Lulu: 1, TFT16_Nocturne: 1, TFT16_Poppy: 1,
  TFT16_RekSai: 1, TFT16_Rumble: 1, TFT16_Soraka: 1, TFT16_TwistedFate: 1, TFT16_Viego: 1,
  TFT16_Zoe: 1, TFT16_Blitzcrank: 1, TFT16_KogMaw: 1,
  // 2-cost
  TFT16_Ekko: 2, TFT16_Kennen: 2, TFT16_Leona: 2, TFT16_Neeko: 2, TFT16_Orianna: 2,
  TFT16_Senna: 2, TFT16_Shen: 2, TFT16_Sona: 2, TFT16_Teemo: 2, TFT16_Tristana: 2,
  TFT16_Vi: 2, TFT16_XinZhao: 2, TFT16_Yorick: 2, TFT16_Malzahar: 2,
  // 3-cost
  TFT16_Ahri: 3, TFT16_ChoGath: 3, TFT16_Draven: 3, TFT16_Gangplank: 3, TFT16_Gwen: 3,
  TFT16_Jinx: 3, TFT16_Kobuko: 3, TFT16_Loris: 3, TFT16_Mordekaiser: 3,
  TFT16_Nautilus: 3, TFT16_Sejuani: 3, TFT16_Sion: 3, TFT16_Swain: 3, TFT16_Vayne: 3,
  TFT16_Wukong: 3,
  // 4-cost
  TFT16_Ambessa: 4, TFT16_Braum: 4, TFT16_Galio: 4, TFT16_Garen: 4, TFT16_Kalista: 4,
  TFT16_Lissandra: 4, TFT16_Lux: 4, TFT16_MissFortune: 4, TFT16_RiftHerald: 4,
  TFT16_Seraphine: 4, TFT16_Taric: 4, TFT16_Yunara: 4, TFT16_BelVeth: 4,
  // 5-cost
  TFT16_Aatrox: 5, TFT16_Azir: 5, TFT16_Fiddlesticks: 5, TFT16_Kindred: 5, TFT16_Lucian: 5,
  TFT16_Ornn: 5, TFT16_Ryze: 5, TFT16_Sett: 5, TFT16_Shyvana: 5, TFT16_Thresh: 5,
  TFT16_Zilean: 5,
};

// Get all champions grouped by cost
const CHAMPIONS_BY_COST = Object.entries(CHAMPION_COSTS).reduce((acc, [champ, cost]) => {
  if (!acc[cost]) acc[cost] = [];
  acc[cost].push(champ);
  return acc;
}, {} as Record<number, string[]>);

// Format champion name (remove TFT16_ prefix)
const formatChampionName = (name: string): string => {
  return name.replace('TFT16_', '');
};

interface PoolTrackerProps {
  gameState: GameState | null;
}

const PoolTracker: React.FC<PoolTrackerProps> = ({ gameState }) => {
  const poolState = usePoolTracker(gameState);
  const [expandedCost, setExpandedCost] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<'contested' | 'byCost'>('contested');

  // Get contested units (any with copies in play)
  const getContestedUnits = () => {
    if (!poolState) return [];

    const contested: { id: string; name: string; cost: number; inPlay: number; remaining: number; availability: Availability }[] = [];

    for (const [champId, inPlay] of Object.entries(poolState.unitsInPlay)) {
      if (inPlay > 0) {
        const cost = CHAMPION_COSTS[champId] || 3;
        contested.push({
          id: champId,
          name: formatChampionName(champId),
          cost,
          inPlay,
          remaining: poolState.getRemaining(champId),
          availability: poolState.getAvailability(champId),
        });
      }
    }

    // Sort by most contested (fewest remaining)
    return contested.sort((a, b) => a.remaining - b.remaining);
  };

  const contestedUnits = getContestedUnits();
  const totalInPlay = poolState?.getTotalInPlay() || 0;

  return (
    <div
      className="rounded-lg p-3"
      style={{ backgroundColor: COLORS.cardBg, border: `1px solid ${COLORS.cardBorder}` }}
    >
      {/* Header */}
      <div className="flex justify-between items-center mb-3">
        <h3
          className="text-sm font-bold"
          style={{ color: COLORS.gold }}
        >
          Pool Tracker
        </h3>
        <span className="text-xs" style={{ color: '#6b7280' }}>
          {totalInPlay} units tracked
        </span>
      </div>

      {/* Toggle buttons */}
      <div className="flex gap-2 mb-3">
        <button
          onClick={() => setViewMode('contested')}
          className="px-2 py-1 text-xs rounded transition-colors"
          style={{
            backgroundColor: viewMode === 'contested' ? COLORS.gold : '#3a3a4f',
            color: viewMode === 'contested' ? '#1e1e2f' : '#9ca3af',
          }}
        >
          Contested
        </button>
        <button
          onClick={() => setViewMode('byCost')}
          className="px-2 py-1 text-xs rounded transition-colors"
          style={{
            backgroundColor: viewMode === 'byCost' ? COLORS.gold : '#3a3a4f',
            color: viewMode === 'byCost' ? '#1e1e2f' : '#9ca3af',
          }}
        >
          By Cost
        </button>
      </div>

      {!poolState ? (
        <div className="text-xs text-center py-4" style={{ color: '#6b7280' }}>
          Waiting for game data...
        </div>
      ) : viewMode === 'contested' ? (
        /* Contested view - shows only units that are in play */
        <div className="space-y-1 max-h-[250px] overflow-y-auto pr-1">
          {contestedUnits.length === 0 ? (
            <div className="text-xs text-center py-4" style={{ color: '#6b7280' }}>
              No units detected yet
            </div>
          ) : (
            contestedUnits.map((unit) => (
              <div
                key={unit.id}
                className="flex items-center justify-between p-1.5 rounded"
                style={{ backgroundColor: '#2a2a3f' }}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: COLORS.cost[unit.cost] }}
                  />
                  <span className="text-xs" style={{ color: '#e5e7eb' }}>
                    {unit.name}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <span
                    className="text-xs font-mono"
                    style={{ color: COLORS.availability[unit.availability] }}
                  >
                    {unit.remaining}/{POOL_SIZES[unit.cost]}
                  </span>
                  <div
                    className="w-12 h-1.5 rounded-full overflow-hidden"
                    style={{ backgroundColor: '#3a3a4f' }}
                  >
                    <div
                      className="h-full rounded-full transition-all"
                      style={{
                        width: `${(unit.remaining / POOL_SIZES[unit.cost]) * 100}%`,
                        backgroundColor: COLORS.availability[unit.availability],
                      }}
                    />
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      ) : (
        /* By Cost view - shows all units grouped by cost tier */
        <div className="space-y-2 max-h-[250px] overflow-y-auto pr-1">
          {[1, 2, 3, 4, 5].map((cost) => {
            const champions = CHAMPIONS_BY_COST[cost] || [];
            const isExpanded = expandedCost === cost;
            const contestedInTier = champions.filter(c =>
              poolState.unitsInPlay[c] && poolState.unitsInPlay[c] > 0
            ).length;

            return (
              <div key={cost} className="rounded" style={{ backgroundColor: '#2a2a3f' }}>
                {/* Cost tier header */}
                <button
                  onClick={() => setExpandedCost(isExpanded ? null : cost)}
                  className="w-full flex items-center justify-between p-2 hover:opacity-80 transition-opacity rounded"
                >
                  <div className="flex items-center gap-2">
                    <span
                      className="px-1.5 py-0.5 rounded text-[10px] font-bold"
                      style={{ backgroundColor: COLORS.cost[cost], color: '#fff' }}
                    >
                      {cost}
                    </span>
                    <span className="text-xs" style={{ color: '#e5e7eb' }}>
                      {cost}-Cost
                    </span>
                    {contestedInTier > 0 && (
                      <span className="text-[10px]" style={{ color: '#ffa94d' }}>
                        {contestedInTier} contested
                      </span>
                    )}
                  </div>
                  <span className="text-[10px]" style={{ color: '#6b7280' }}>
                    {isExpanded ? '▼' : '▶'}
                  </span>
                </button>

                {/* Expanded champions list */}
                {isExpanded && (
                  <div className="px-2 pb-2 space-y-1">
                    {champions.map((champId) => {
                      const inPlay = poolState.unitsInPlay[champId] || 0;
                      const remaining = poolState.getRemaining(champId);
                      const availability = poolState.getAvailability(champId);

                      return (
                        <div
                          key={champId}
                          className="flex items-center justify-between py-0.5"
                        >
                          <span
                            className="text-xs"
                            style={{
                              color: inPlay > 0 ? COLORS.availability[availability] : '#6b7280',
                            }}
                          >
                            {formatChampionName(champId)}
                          </span>
                          <span
                            className="text-[10px] font-mono"
                            style={{ color: COLORS.availability[availability] }}
                          >
                            {remaining}/{POOL_SIZES[cost]}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Pool size reference */}
      <div className="mt-3 pt-2 border-t" style={{ borderColor: COLORS.cardBorder }}>
        <div className="text-[10px] text-center" style={{ color: '#6b7280' }}>
          Pool: 1★=30 | 2★=25 | 3★=18 | 4★=10 | 5★=9
        </div>
      </div>
    </div>
  );
};

export default PoolTracker;
