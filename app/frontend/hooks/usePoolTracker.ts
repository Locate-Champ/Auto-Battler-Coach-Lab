/**
 * Hook for tracking unit pool state and calculating availability
 */

import { useMemo } from 'react';
import { GameState } from './useGameState';

// TFT Set 16 Pool sizes by champion cost
const POOL_SIZES: Record<number, number> = {
  1: 30,
  2: 25,
  3: 18,
  4: 10,
  5: 9,
};

// Shop odds by player level [1-cost%, 2-cost%, 3-cost%, 4-cost%, 5-cost%]
const SHOP_ODDS: Record<number, number[]> = {
  1: [100, 0, 0, 0, 0],
  2: [100, 0, 0, 0, 0],
  3: [75, 25, 0, 0, 0],
  4: [55, 30, 15, 0, 0],
  5: [45, 33, 20, 2, 0],
  6: [30, 40, 25, 5, 0],
  7: [19, 35, 35, 10, 1],
  8: [18, 25, 36, 18, 3],
  9: [10, 20, 25, 35, 10],
  10: [5, 10, 20, 40, 25],
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

export type Availability = 'high' | 'medium' | 'low' | 'none';

export interface PoolState {
  unitsInPlay: Record<string, number>;
  getRemaining: (champion: string) => number;
  getShopProbability: (champion: string, level: number) => number;
  canThreeStar: (champion: string, currentCopies: number) => boolean;
  getAvailability: (champion: string) => Availability;
  getTotalInPlay: () => number;
}

/**
 * Calculate star level copies
 */
const getStarCopies = (stars: number): number => {
  return { 1: 1, 2: 3, 3: 9 }[stars] || 1;
};

/**
 * Hook for tracking unit pool state
 */
export function usePoolTracker(gameState: GameState | null): PoolState | null {
  return useMemo(() => {
    if (!gameState) return null;

    const unitsInPlay: Record<string, number> = {};

    // Count your board + bench units
    const yourUnits = [
      ...(gameState.board_units || []),
      ...(gameState.bench_units || []),
    ];

    for (const unit of yourUnits) {
      const champId = unit.character_id;
      if (!champId) continue;
      const copies = getStarCopies(unit.stars);
      unitsInPlay[champId] = (unitsInPlay[champId] || 0) + copies;
    }

    // Count opponent boards (from Redux bridge)
    const opponentBoards = gameState.opponent_boards || {};
    for (const [, units] of Object.entries(opponentBoards)) {
      for (const unit of units) {
        const champId = unit.character_id;
        if (!champId) continue;
        const copies = getStarCopies(unit.stars);
        unitsInPlay[champId] = (unitsInPlay[champId] || 0) + copies;
      }
    }

    const getRemaining = (champion: string): number => {
      const cost = CHAMPION_COSTS[champion] || 3;
      const total = POOL_SIZES[cost] || 18;
      const inPlay = unitsInPlay[champion] || 0;
      return Math.max(0, total - inPlay);
    };

    const getShopProbability = (champion: string, level: number): number => {
      const cost = CHAMPION_COSTS[champion] || 3;
      const remaining = getRemaining(champion);

      if (remaining <= 0) return 0;

      // Clamp level to valid range
      const clampedLevel = Math.max(1, Math.min(10, level));
      const tierOdds = SHOP_ODDS[clampedLevel] || SHOP_ODDS[6];
      const tierChance = tierOdds[cost - 1] / 100;

      if (tierChance === 0) return 0;

      // Calculate total remaining in tier (simplified)
      // In a real implementation, we'd sum across all champions of same cost
      const totalPool = POOL_SIZES[cost] || 18;
      return tierChance * (remaining / totalPool);
    };

    const canThreeStar = (champion: string, currentCopies: number): boolean => {
      const needed = 9 - currentCopies;
      return getRemaining(champion) >= needed;
    };

    const getAvailability = (champion: string): Availability => {
      const remaining = getRemaining(champion);
      const cost = CHAMPION_COSTS[champion] || 3;
      const total = POOL_SIZES[cost] || 18;

      if (remaining <= 0) return 'none';

      const ratio = remaining / total;

      if (ratio >= 0.66) return 'high';
      if (ratio >= 0.33) return 'medium';
      return 'low';
    };

    const getTotalInPlay = (): number => {
      return Object.values(unitsInPlay).reduce((sum, count) => sum + count, 0);
    };

    return {
      unitsInPlay,
      getRemaining,
      getShopProbability,
      canThreeStar,
      getAvailability,
      getTotalInPlay,
    };
  }, [gameState]);
}

export default usePoolTracker;
