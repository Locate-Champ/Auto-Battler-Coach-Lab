import React from 'react';
import { EarlyCompWithTransition } from './hooks/useEarlyComps';

// Colors matching the overlay theme
const COLORS = {
  cardBg: '#1e1e2f',
  cardBorder: '#3a3a4f',
  dropdownBg: '#252538',
  gold: '#c9a033',
  textMuted: '#888',
  probability: {
    high: '#69db7c',   // > 50%
    medium: '#ffa94d', // 20-50%
    low: '#6b7280',    // < 20%
  },
  cost: {
    1: '#5a5a6f',
    2: '#2ecc71',
    3: '#3498db',
    4: '#9b59b6',
    5: '#f1c40f',
  } as Record<number, string>,
};

// Champion cost mapping for Set 16
const CHAMPION_COSTS: Record<string, number> = {
  // 1-cost
  TFT16_Anivia: 1, TFT16_Ashe: 1, TFT16_Briar: 1, TFT16_Caitlyn: 1, TFT16_Elise: 1,
  TFT16_Illaoi: 1, TFT16_JarvanIV: 1, TFT16_Lulu: 1, TFT16_Nocturne: 1, TFT16_Poppy: 1,
  TFT16_RekSai: 1, TFT16_Rumble: 1, TFT16_Soraka: 1, TFT16_TwistedFate: 1, TFT16_Viego: 1,
  TFT16_Zoe: 1, TFT16_Blitzcrank: 1, TFT16_KogMaw: 1, TFT16_ChoGath: 1,
  // 2-cost
  TFT16_Ekko: 2, TFT16_Kennen: 2, TFT16_Leona: 2, TFT16_Neeko: 2, TFT16_Orianna: 2,
  TFT16_Senna: 2, TFT16_Shen: 2, TFT16_Sona: 2, TFT16_Teemo: 2, TFT16_Tristana: 2,
  TFT16_Vi: 2, TFT16_XinZhao: 2, TFT16_Yorick: 2, TFT16_Malzahar: 2,
  // 3-cost
  TFT16_Ahri: 3, TFT16_Draven: 3, TFT16_Gangplank: 3, TFT16_Gwen: 3,
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

// Format champion name (remove TFT16_ prefix)
const formatChampionName = (name: string): string => {
  return name.replace('TFT16_', '');
};

// Get champion cost
const getChampionCost = (name: string): number => {
  return CHAMPION_COSTS[name] || 1; // Default to 1 for early game units
};

// Get image URL for a champion
const getChampionImage = (championName: string): string => {
  const displayName = formatChampionName(championName);
  return new URL(`./images/champion images/${displayName}.png`, import.meta.url).href;
};

// Get probability color
const getProbabilityColor = (prob: number): string => {
  if (prob >= 0.5) return COLORS.probability.high;
  if (prob >= 0.2) return COLORS.probability.medium;
  return COLORS.probability.low;
};

// Format probability for display (cap at 100%)
const formatProbability = (prob: number): string => {
  const percent = Math.min(prob * 100, 100);
  return `${percent.toFixed(0)}%`;
};

interface EarlyCompRowProps {
  comp: EarlyCompWithTransition;
}

const EarlyCompRow: React.FC<EarlyCompRowProps> = ({ comp }) => {
  const probColor = getProbabilityColor(comp.transitionProbability);

  return (
    <div
      className="flex items-center gap-2 py-1.5 px-2 rounded transition-colors"
      style={{ backgroundColor: COLORS.cardBg }}
    >
      {/* Transition probability badge */}
      <span
        className="text-xs font-bold px-2 py-0.5 rounded min-w-[42px] text-center"
        style={{
          backgroundColor: probColor + '22',
          color: probColor,
          border: `1px solid ${probColor}`,
        }}
      >
        {formatProbability(comp.transitionProbability)}
      </span>

      {/* Unit icons with star levels */}
      <div className="flex gap-0.5 flex-wrap">
        {comp.units.map((unit, index) => {
          const cost = getChampionCost(unit);
          const stars = comp.star_levels[unit] || 1;

          return (
            <div
              key={`${unit}-${index}`}
              className="relative rounded overflow-hidden"
              style={{
                width: 24,
                height: 24,
                border: `2px solid ${COLORS.cost[cost] || COLORS.cost[1]}`,
                backgroundColor: '#3a3a4f',
              }}
            >
              <img
                src={getChampionImage(unit)}
                alt={formatChampionName(unit)}
                className="w-full h-full object-cover"
                draggable={false}
                onError={(e) => {
                  e.currentTarget.style.display = 'none';
                }}
              />
              {/* Star indicator */}
              {stars >= 2 && (
                <span
                  className="absolute -bottom-0.5 left-0 right-0 text-center text-[8px] leading-none"
                  style={{ color: stars === 3 ? '#f1c40f' : '#888' }}
                >
                  {'★'.repeat(stars)}
                </span>
              )}
            </div>
          );
        })}
      </div>

      {/* Stats */}
      <div className="ml-auto text-[10px]" style={{ color: COLORS.textMuted }}>
        <span style={{ color: comp.stats.avg_placement < 4.3 ? COLORS.probability.high : COLORS.textMuted }}>
          {comp.stats.avg_placement.toFixed(1)} avg
        </span>
        <span className="mx-1">|</span>
        <span>{(comp.stats.games / 1000).toFixed(1)}k</span>
      </div>
    </div>
  );
};

interface EarlyCompDropdownProps {
  earlyComps: EarlyCompWithTransition[];
  maxComps?: number;
}

const EarlyCompDropdown: React.FC<EarlyCompDropdownProps> = ({
  earlyComps,
  maxComps = 3,
}) => {
  if (earlyComps.length === 0) {
    return (
      <div
        className="mt-2 p-2 rounded text-xs text-center"
        style={{ backgroundColor: COLORS.dropdownBg, color: COLORS.textMuted }}
      >
        No early game paths found
      </div>
    );
  }

  const displayComps = earlyComps.slice(0, maxComps);

  return (
    <div
      className="mt-2 rounded overflow-hidden"
      style={{
        backgroundColor: COLORS.dropdownBg,
        border: `1px solid ${COLORS.cardBorder}`,
      }}
    >
      {/* Header */}
      <div
        className="px-2 py-1.5 flex justify-between items-center"
        style={{ borderBottom: `1px solid ${COLORS.cardBorder}` }}
      >
        <span className="text-xs font-medium" style={{ color: COLORS.gold }}>
          Early Game Paths
        </span>
        <span className="text-[10px]" style={{ color: COLORS.textMuted }}>
          Stage 2
        </span>
      </div>

      {/* Early comp rows */}
      <div className="p-1.5 flex flex-col gap-1">
        {displayComps.map((comp) => (
          <EarlyCompRow key={comp.comp_id} comp={comp} />
        ))}
      </div>

      {/* Footer if more comps available */}
      {earlyComps.length > maxComps && (
        <div
          className="px-2 py-1 text-[10px] text-center"
          style={{
            borderTop: `1px solid ${COLORS.cardBorder}`,
            color: COLORS.textMuted,
          }}
        >
          +{earlyComps.length - maxComps} more paths
        </div>
      )}
    </div>
  );
};

export default EarlyCompDropdown;
