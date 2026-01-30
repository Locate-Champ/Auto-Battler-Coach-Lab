import React, { useState } from 'react';
import { MetaComp } from './hooks/useMetaComps';
import { EarlyCompWithTransition } from './hooks/useEarlyComps';
import EarlyCompDropdown from './EarlyCompDropdown';

// Colors matching the overlay theme
const COLORS = {
  cardBg: '#1e1e2f',
  cardBorder: '#3a3a4f',
  metaBadgeBg: '#2a2a3f',
  gold: '#c9a033',
  statGood: '#69db7c',
  statMid: '#ffa94d',
  statBad: '#ff6b6b',
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
  TFT16_Zoe: 1,
  // 2-cost
  TFT16_Ekko: 2, TFT16_Kennen: 2, TFT16_Leona: 2, TFT16_Neeko: 2, TFT16_Orianna: 2,
  TFT16_Senna: 2, TFT16_Shen: 2, TFT16_Sona: 2, TFT16_Teemo: 2, TFT16_Tristana: 2,
  TFT16_Vi: 2, TFT16_XinZhao: 2, TFT16_Yorick: 2,
  // 3-cost
  TFT16_Ahri: 3, TFT16_ChoGath: 3, TFT16_Draven: 3, TFT16_Gangplank: 3, TFT16_Gwen: 3,
  TFT16_Jinx: 3, TFT16_Kobuko: 3, TFT16_Loris: 3, TFT16_Malzahar: 3, TFT16_Mordekaiser: 3,
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
  return CHAMPION_COSTS[name] || 3; // Default to 3 if not found
};

// Get stat color based on value
const getStatColor = (value: number, type: 'top4' | 'winRate' | 'avgPlacement'): string => {
  if (type === 'avgPlacement') {
    if (value <= 3.5) return COLORS.statGood;
    if (value <= 4.2) return COLORS.statMid;
    return COLORS.statBad;
  }
  if (type === 'top4') {
    if (value >= 60) return COLORS.statGood;
    if (value >= 50) return COLORS.statMid;
    return COLORS.statBad;
  }
  if (type === 'winRate') {
    if (value >= 15) return COLORS.statGood;
    if (value >= 10) return COLORS.statMid;
    return COLORS.statBad;
  }
  return '#ffffff';
};

// Get tier color based on tier letter
const getTierColor = (tier: string): string => {
  switch (tier) {
    case 'S': return 'linear-gradient(135deg, #ff6b6b, #c92a2a)';
    case 'A': return 'linear-gradient(135deg, #ffa94d, #e67700)';
    case 'B': return 'linear-gradient(135deg, #69db7c, #2f9e44)';
    default: return 'linear-gradient(135deg, #868e96, #495057)';
  }
};

// Get levelling badge color
const getLevellingColor = (levelling: string): string => {
  if (levelling.includes('Fast 9')) return '#9b59b6';
  if (levelling.includes('Fast 8')) return '#3498db';
  if (levelling.includes('lvl')) return '#2ecc71';
  return '#6b7280';
};

// Get image URL for a champion
const getChampionImage = (championName: string): string => {
  const displayName = formatChampionName(championName);
  return new URL(`./images/champion images/${displayName}.png`, import.meta.url).href;
};

interface MetaCompCardProps {
  comp: MetaComp;
  rank: number;
  isHighlighted?: boolean;
  earlyTransitions?: EarlyCompWithTransition[];
}

const MetaCompCard: React.FC<MetaCompCardProps> = ({
  comp,
  rank,
  isHighlighted = false,
  earlyTransitions = [],
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const tierColor = getTierColor(comp.tier);
  const gamesInK = (comp.games_played / 1000).toFixed(1);
  const levellingColor = getLevellingColor(comp.levelling);
  const hasEarlyPaths = earlyTransitions.length > 0;

  const handleClick = () => {
    if (hasEarlyPaths) {
      setIsExpanded(!isExpanded);
    }
  };

  return (
    <div
      className="rounded-md p-3 transition-all duration-200"
      style={{
        backgroundColor: COLORS.cardBg,
        border: `1px solid ${isHighlighted ? COLORS.gold : COLORS.cardBorder}`,
        cursor: hasEarlyPaths ? 'pointer' : 'default',
      }}
      onClick={handleClick}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = COLORS.gold;
        e.currentTarget.style.transform = 'translateX(2px)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = isHighlighted ? COLORS.gold : COLORS.cardBorder;
        e.currentTarget.style.transform = 'translateX(0)';
      }}
    >
      {/* Header: Rank + Tier + Levelling */}
      <div className="flex justify-between items-center mb-2">
        <div className="flex items-center gap-2">
          <span
            className="px-2 py-0.5 rounded text-xs font-bold"
            style={{ background: tierColor, color: '#fff' }}
          >
            {comp.tier}
          </span>
          <span className="text-xs font-bold" style={{ color: '#6b7280' }}>
            #{rank}
          </span>
          <span
            className="px-1.5 py-0.5 rounded text-[10px]"
            style={{ backgroundColor: levellingColor + '33', color: levellingColor, border: `1px solid ${levellingColor}` }}
          >
            {comp.levelling}
          </span>
        </div>
        <span className="text-xs" style={{ color: '#6b7280' }}>
          {gamesInK}k games
        </span>
      </div>

      {/* Champions row */}
      <div className="flex gap-1 flex-wrap mb-2">
        {comp.units.slice(0, 8).map((unit, index) => {
          const cost = getChampionCost(unit);
          return (
            <div
              key={`${unit}-${index}`}
              className="rounded overflow-hidden"
              style={{
                width: 28,
                height: 28,
                border: `2px solid ${COLORS.cost[cost] || COLORS.cost[3]}`,
                backgroundColor: '#3a3a4f',
              }}
            >
              <img
                src={getChampionImage(unit)}
                alt={formatChampionName(unit)}
                className="w-full h-full object-cover"
                draggable={false}
                onError={(e) => {
                  // Hide broken images
                  e.currentTarget.style.display = 'none';
                }}
              />
            </div>
          );
        })}
      </div>

      {/* Top traits */}
      {comp.traits && comp.traits.length > 0 && (
        <div className="flex gap-1 flex-wrap mb-2">
          {comp.traits.filter(t => t.count >= 2).slice(0, 4).map((trait) => (
            <span
              key={trait.name}
              className="px-1.5 py-0.5 rounded text-[10px]"
              style={{
                backgroundColor: '#3a3a1f',
                color: COLORS.gold,
                border: `1px solid ${COLORS.gold}`,
              }}
            >
              {trait.name} {trait.count}
            </span>
          ))}
        </div>
      )}

      {/* Stats row */}
      <div className="flex gap-4 items-center">
        <div className="flex flex-col items-center">
          <span
            className="text-sm font-semibold"
            style={{ color: getStatColor(comp.win_rate, 'winRate') }}
          >
            {comp.win_rate.toFixed(1)}%
          </span>
          <span className="text-[10px] uppercase tracking-wide" style={{ color: '#888' }}>
            Win
          </span>
        </div>
        <div className="flex flex-col items-center">
          <span
            className="text-sm font-semibold"
            style={{ color: getStatColor(comp.avg_placement, 'avgPlacement') }}
          >
            {comp.avg_placement.toFixed(2)}
          </span>
          <span className="text-[10px] uppercase tracking-wide" style={{ color: '#888' }}>
            Avg
          </span>
        </div>

        {/* Early paths indicator */}
        {hasEarlyPaths && (
          <div className="ml-auto flex items-center gap-1 text-xs" style={{ color: '#6b7280' }}>
            <span style={{ color: isExpanded ? COLORS.gold : '#6b7280' }}>
              {isExpanded ? '▼' : '▶'}
            </span>
            <span>{earlyTransitions.length} early paths</span>
          </div>
        )}
      </div>

      {/* Early game paths dropdown */}
      {isExpanded && hasEarlyPaths && (
        <EarlyCompDropdown earlyComps={earlyTransitions} maxComps={3} />
      )}
    </div>
  );
};

export default MetaCompCard;
