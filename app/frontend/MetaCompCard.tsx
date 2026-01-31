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

// Trait breakpoint styles (from traits.jsonl style values)
// style: 1=bronze, 3=silver, 4=unique, 5=gold, 6=prismatic
const TRAIT_TIER_COLORS = {
  bronze: { bg: '#5c4033', border: '#cd7f32', text: '#cd7f32' },
  silver: { bg: '#3d3d4d', border: '#c0c0c0', text: '#c0c0c0' },
  gold: { bg: '#3a3a1f', border: '#ffd700', text: '#ffd700' },
  prismatic: { bg: '#2a1f3a', border: '#e066ff', text: '#e066ff' },
  unique: { bg: '#1f2a3a', border: '#4dabf7', text: '#4dabf7' },
};

// Trait breakpoints mapping from game data
// Format: { traitName: [[minUnits, style], ...] } sorted by minUnits
const TRAIT_BREAKPOINTS: Record<string, [number, number][]> = {
  // Standard traits
  'Freljord': [[3, 1], [5, 3], [7, 5]],
  'Juggernaut': [[2, 1], [4, 3], [6, 5]],
  'Quickstriker': [[2, 1], [3, 3], [4, 3], [5, 5]],
  'Longshot': [[2, 1], [3, 3], [4, 5], [5, 5]],
  'Vanquisher': [[2, 1], [3, 3], [4, 3], [5, 5]],
  'Ixtal': [[3, 1], [5, 3], [7, 5]],
  'Slayer': [[2, 1], [4, 3], [6, 5]],
  'Arcanist': [[2, 1], [4, 3], [6, 5]],
  'Gunslinger': [[2, 1], [4, 5]],
  'Disruptor': [[2, 1], [4, 5]],
  'Void': [[2, 1], [4, 3], [6, 5], [9, 5]],
  'Invoker': [[2, 1], [4, 5]],
  'Demacia': [[3, 1], [5, 3], [7, 5], [11, 6]],
  'Bilgewater': [[3, 1], [5, 3], [7, 5], [10, 6]],
  'Piltover': [[2, 1], [4, 3], [6, 5]],
  'Darkin': [[1, 1], [2, 3], [3, 5]],
  'Noxus': [[3, 1], [5, 3], [7, 5], [10, 6]],
  'Yordle': [[2, 1], [4, 3], [6, 3], [8, 5], [10, 6]],
  'Zaun': [[3, 1], [5, 3], [7, 5]],
  'Bruiser': [[2, 1], [4, 3], [6, 5]],
  'Warden': [[2, 1], [3, 3], [4, 3], [5, 5]],
  'Ionia': [[3, 1], [5, 3], [7, 5], [10, 6]],
  'Defender': [[2, 1], [4, 3], [6, 5]],
  'Shadow Isles': [[2, 1], [3, 3], [4, 3], [5, 5]],
  'Shurima': [[2, 1], [3, 5], [4, 6]],
  'Targon': [[1, 5]],
};

// Get trait tier info based on count
interface TraitTierInfo {
  tier: 'bronze' | 'silver' | 'gold' | 'prismatic' | 'unique' | 'inactive';
  currentBreakpoint: number;
  nextBreakpoint: number | null;
}

const getTraitTierInfo = (traitName: string, count: number): TraitTierInfo => {
  const breakpoints = TRAIT_BREAKPOINTS[traitName];

  if (!breakpoints || breakpoints.length === 0) {
    // Unknown trait - assume it's active if count >= 2
    return {
      tier: count >= 2 ? 'bronze' : 'inactive',
      currentBreakpoint: count,
      nextBreakpoint: null,
    };
  }

  let activeTier: TraitTierInfo['tier'] = 'inactive';
  let currentBreakpoint = 0;
  let nextBreakpoint: number | null = null;

  for (let i = 0; i < breakpoints.length; i++) {
    const [minUnits, style] = breakpoints[i];

    if (count >= minUnits) {
      currentBreakpoint = minUnits;
      // Map style number to tier name
      switch (style) {
        case 1: activeTier = 'bronze'; break;
        case 3: activeTier = 'silver'; break;
        case 4: activeTier = 'unique'; break;
        case 5: activeTier = 'gold'; break;
        case 6: activeTier = 'prismatic'; break;
      }
      // Check for next breakpoint
      if (i + 1 < breakpoints.length) {
        nextBreakpoint = breakpoints[i + 1][0];
      } else {
        nextBreakpoint = null;
      }
    }
  }

  // If no breakpoint was reached, find the first one
  if (activeTier === 'inactive' && breakpoints.length > 0) {
    nextBreakpoint = breakpoints[0][0];
  }

  return { tier: activeTier, currentBreakpoint, nextBreakpoint };
};

// Calculate tier based on top4_rate (override API tier if needed)
const calculateTier = (top4Rate: number, apiTier: string): string => {
  // Recalculate tier based on actual performance
  if (top4Rate >= 65) return 'S';
  if (top4Rate >= 55) return 'A';
  if (top4Rate >= 45) return 'B';
  return apiTier || 'B';
};

// Get unit limit based on levelling strategy
const getUnitLimit = (levelling: string): number => {
  // Fast 8 comps typically show 8 units, Fast 9/Standard show 9
  if (levelling?.includes('Fast 8') && !levelling?.includes('Fast 9')) {
    return 8;
  }
  return 9;
};

// Get image URL for a champion
const getChampionImage = (championName: string): string => {
  const displayName = formatChampionName(championName);
  return new URL(`./images/champion images/${displayName}.png`, import.meta.url).href;
};

// Get image URL for an item (try craftable items first, then other categories)
const getItemImage = (itemName: string): string => {
  // Try craftable items folder first (most common)
  return new URL(`./images/craftable items images/${itemName}.png`, import.meta.url).href;
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
  const [showBuilds, setShowBuilds] = useState(false);
  // Calculate tier from top4_rate instead of trusting API tier
  const tier = calculateTier(comp.top4_rate, comp.tier);
  const tierColor = getTierColor(tier);
  const gamesInK = (comp.games_played / 1000).toFixed(1);
  const levellingColor = getLevellingColor(comp.levelling);
  const hasEarlyPaths = earlyTransitions.length > 0;
  const hasBuilds = comp.builds && comp.builds.length > 0;
  // Dynamic unit limit based on levelling strategy
  const unitLimit = getUnitLimit(comp.levelling);

  const handleClick = () => {
    if (hasEarlyPaths) {
      setIsExpanded(!isExpanded);
    }
  };

  const handleBuildsClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent card click
    setShowBuilds(!showBuilds);
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
            {tier}
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
        {comp.units.slice(0, unitLimit).map((unit, index) => {
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

      {/* Top traits with breakpoint styling */}
      {comp.traits && comp.traits.length > 0 && (
        <div className="flex gap-1 flex-wrap mb-2">
          {comp.traits.filter(t => t.count >= 1).slice(0, 5).map((trait) => {
            const tierInfo = getTraitTierInfo(trait.name, trait.count);
            const tierColors = tierInfo.tier !== 'inactive'
              ? TRAIT_TIER_COLORS[tierInfo.tier]
              : { bg: '#2a2a3f', border: '#4a4a5f', text: '#6b7280' };

            return (
              <span
                key={trait.name}
                className="px-1.5 py-0.5 rounded text-[10px] flex items-center gap-1"
                style={{
                  backgroundColor: tierColors.bg,
                  color: tierColors.text,
                  border: `1px solid ${tierColors.border}`,
                }}
                title={tierInfo.nextBreakpoint
                  ? `Next: ${tierInfo.nextBreakpoint} units`
                  : 'Max tier reached'}
              >
                <span>{trait.name}</span>
                <span className="font-bold">{trait.count}</span>
                {tierInfo.nextBreakpoint && (
                  <span style={{ color: '#6b7280', fontSize: '8px' }}>
                    /{tierInfo.nextBreakpoint}
                  </span>
                )}
              </span>
            );
          })}
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

        {/* Builds indicator */}
        {hasBuilds && (
          <button
            onClick={handleBuildsClick}
            className="ml-auto flex items-center gap-1 text-xs hover:opacity-80 transition-opacity"
            style={{ color: showBuilds ? COLORS.gold : '#6b7280' }}
          >
            <span>{showBuilds ? '▼' : '▶'}</span>
            <span>{comp.builds.length} builds</span>
          </button>
        )}

        {/* Early paths indicator */}
        {hasEarlyPaths && !hasBuilds && (
          <div className="ml-auto flex items-center gap-1 text-xs" style={{ color: '#6b7280' }}>
            <span style={{ color: isExpanded ? COLORS.gold : '#6b7280' }}>
              {isExpanded ? '▼' : '▶'}
            </span>
            <span>{earlyTransitions.length} early paths</span>
          </div>
        )}
      </div>

      {/* Item Builds Section */}
      {showBuilds && hasBuilds && (
        <div className="mt-3 pt-3 border-t" style={{ borderColor: COLORS.cardBorder }}>
          <div className="text-[10px] uppercase tracking-wide mb-2" style={{ color: '#888' }}>
            Item Builds
          </div>
          <div className="space-y-2">
            {comp.builds.slice(0, 3).map((build, buildIndex) => {
              const unitCost = getChampionCost(build.unit);
              return (
                <div
                  key={`${build.unit}-${buildIndex}`}
                  className="flex items-center gap-2 p-1.5 rounded"
                  style={{ backgroundColor: '#2a2a3f' }}
                >
                  {/* Champion icon */}
                  <div
                    className="rounded overflow-hidden flex-shrink-0"
                    style={{
                      width: 24,
                      height: 24,
                      border: `2px solid ${COLORS.cost[unitCost] || COLORS.cost[3]}`,
                      backgroundColor: '#3a3a4f',
                    }}
                  >
                    <img
                      src={getChampionImage(build.unit)}
                      alt={formatChampionName(build.unit)}
                      className="w-full h-full object-cover"
                      draggable={false}
                      onError={(e) => {
                        e.currentTarget.style.display = 'none';
                      }}
                    />
                  </div>

                  {/* Champion name */}
                  <span className="text-xs font-medium" style={{ color: '#e5e7eb', minWidth: '60px' }}>
                    {formatChampionName(build.unit)}
                  </span>

                  {/* Item icons */}
                  <div className="flex gap-1 flex-1">
                    {build.items.map((item, itemIndex) => (
                      <div
                        key={`${item}-${itemIndex}`}
                        className="rounded overflow-hidden"
                        style={{
                          width: 20,
                          height: 20,
                          backgroundColor: '#3a3a4f',
                          border: '1px solid #4a4a5f',
                        }}
                        title={item}
                      >
                        <img
                          src={getItemImage(item)}
                          alt={item}
                          className="w-full h-full object-cover"
                          draggable={false}
                          onError={(e) => {
                            // Show item name as fallback
                            const parent = e.currentTarget.parentElement;
                            if (parent) {
                              parent.innerHTML = `<span style="font-size: 6px; color: #888; display: flex; align-items: center; justify-content: center; height: 100%;">${item.slice(0, 2)}</span>`;
                            }
                          }}
                        />
                      </div>
                    ))}
                  </div>

                  {/* Build stats */}
                  <div className="text-[10px] text-right" style={{ color: '#6b7280' }}>
                    <span style={{ color: getStatColor(build.avg_placement, 'avgPlacement') }}>
                      {build.avg_placement.toFixed(2)}
                    </span>
                    <span className="ml-1">avg</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Early game paths dropdown */}
      {isExpanded && hasEarlyPaths && (
        <EarlyCompDropdown earlyComps={earlyTransitions} maxComps={3} />
      )}
    </div>
  );
};

export default MetaCompCard;
