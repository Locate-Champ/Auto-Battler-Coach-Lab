import React, { useEffect, useState } from 'react';
import { MetaComp } from './hooks/useMetaComps';
import { EarlyCompWithTransition } from './hooks/useEarlyComps';
import { AugmentRecommendation } from './hooks/useAugments';
import EarlyCompDropdown from './EarlyCompDropdown';
import { TraitList } from './components/TraitIcon';

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
  TFT16_Zoe: 1, TFT16_Blitzcrank: 1, TFT16_KogMaw: 1,
  // 2-cost
  TFT16_Ekko: 2, TFT16_Kennen: 2, TFT16_Leona: 2, TFT16_Neeko: 2, TFT16_Orianna: 2,
  TFT16_Senna: 2, TFT16_Shen: 2, TFT16_Sona: 2, TFT16_Teemo: 2, TFT16_Tristana: 2,
  TFT16_Vi: 2, TFT16_XinZhao: 2, TFT16_Yorick: 2, TFT16_Aphelios: 2, TFT16_Bard: 2,
  TFT16_Yasuo: 2,
  // 3-cost
  TFT16_Ahri: 3, TFT16_ChoGath: 3, TFT16_Draven: 3, TFT16_Gangplank: 3, TFT16_Gwen: 3,
  TFT16_Jinx: 3, TFT16_Kobuko: 3, TFT16_Loris: 3, TFT16_Malzahar: 3, TFT16_Mordekaiser: 3,
  TFT16_Nautilus: 3, TFT16_Sejuani: 3, TFT16_Sion: 3, TFT16_Swain: 3, TFT16_Vayne: 3,
  TFT16_Wukong: 3, TFT16_Darius: 3, TFT16_DrMundo: 3,
  // 4-cost
  TFT16_Ambessa: 4, TFT16_Braum: 4, TFT16_Galio: 4, TFT16_Garen: 4, TFT16_Kalista: 4,
  TFT16_Lissandra: 4, TFT16_Lux: 4, TFT16_MissFortune: 4, TFT16_RiftHerald: 4,
  TFT16_Seraphine: 4, TFT16_Taric: 4, TFT16_Yunara: 4, TFT16_BelVeth: 4,
  TFT16_Diana: 4, TFT16_Fizz: 4, TFT16_Kaisa: 4, TFT16_Nasus: 4, TFT16_Nidalee: 4,
  TFT16_Renekton: 4, TFT16_Singed: 4, TFT16_Skarner: 4, TFT16_Veigar: 4,
  TFT16_Warwick: 4, TFT16_Yone: 4,
  // 5-cost
  TFT16_Aatrox: 5, TFT16_Azir: 5, TFT16_Fiddlesticks: 5, TFT16_Kindred: 5, TFT16_Lucian: 5,
  TFT16_Ornn: 5, TFT16_Ryze: 5, TFT16_Sett: 5, TFT16_Shyvana: 5, TFT16_Thresh: 5,
  TFT16_Zilean: 5, TFT16_AurelionSol: 5, TFT16_Mel: 5, TFT16_Zaahen: 5, TFT16_Ziggs: 5,
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
    case 'C': return 'linear-gradient(135deg, #74c0fc, #4dabf7)';
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

// Helper to format comp name for display
const formatCompName = (name: string): string => {
  // Remove TFT16_ prefix and clean up
  return name
    .replace(/TFT16_/g, '')
    .replace(/, /g, ' ')
    .replace(/,/g, ' ')
    .trim();
};

// Get unit limit based on levelling strategy
const getUnitLimit = (levelling: string): number => {
  // Fast 8 comps typically show 8 units, Fast 9/Standard show 9
  if (levelling?.includes('Fast 8') && !levelling?.includes('Fast 9')) {
    return 8;
  }
  return 9;
};

const CHAMPION_IMAGE_MAP: Record<string, string> = {
  AnnieTibbers: 'Annie.png',
  AurelionSol: 'Aurelion Sol.png',
  BelVeth: "Bel'Veth.png",
  ChoGath: "Cho'Gath.png",
  DrMundo: 'Dr. Mundo.png',
  JarvanIV: 'Jarvan IV.png',
  Kaisa: "Kai'Sa.png",
  Kobuko: 'Kobuko & Yuumi.png',
  KogMaw: "Kog'Maw.png",
  Lucian: 'Lucian & Senna.png',
  RekSai: "Rek'Sai.png",
  RiftHerald: 'Rift Herald.png',
  XinZhao: 'Xin Zhao.png',
};

// Get image URL for a champion
const getChampionImage = (championName: string): string => {
  const displayName = formatChampionName(championName);
  const fileName = CHAMPION_IMAGE_MAP[displayName] ?? `${displayName}.png`;
  return new URL(`./images/champion images/${fileName}`, import.meta.url).href;
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
  augmentRecommendations?: Array<AugmentRecommendation & {
    matchCount: number;
    matchingTypes: string[];
    fitScore: number;
    enemyBenefit: 'High' | 'Medium' | 'Low';
  }>;
  defaultExpanded?: boolean;
}

const MetaCompCard: React.FC<MetaCompCardProps> = ({
  comp,
  rank,
  isHighlighted = false,
  earlyTransitions = [],
  augmentRecommendations = [],
  defaultExpanded = false,
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [showBuilds, setShowBuilds] = useState(false);
  const tier = comp.tier;
  const tierColor = getTierColor(tier);
  const gamesInK = (comp.games_played / 1000).toFixed(1);
  const levellingColor = getLevellingColor(comp.levelling);
  const hasEarlyPaths = earlyTransitions.length > 0;
  const hasBuilds = comp.builds && comp.builds.length > 0;
  const hasAugments = augmentRecommendations.length > 0;
  // Dynamic unit limit based on levelling strategy
  const unitLimit = getUnitLimit(comp.levelling);

  useEffect(() => {
    setIsExpanded(defaultExpanded);
  }, [defaultExpanded]);

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
      <div className="flex justify-between items-center mb-1">
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

      {/* Comp Name */}
      {comp.name && (
        <div className="text-sm font-medium mb-2" style={{ color: '#e5e7eb' }}>
          {formatCompName(comp.name)}
        </div>
      )}

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

      {/* Active traits with icons */}
      {comp.traits && comp.traits.length > 0 && (
        <div className="mb-2">
          <TraitList traits={comp.traits} size="sm" showInactive />
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

      {/* Augment recommendations */}
      {hasAugments && (
        <div className="mt-3 pt-3 border-t" style={{ borderColor: COLORS.cardBorder }}>
          <div className="text-[10px] uppercase tracking-wide mb-2" style={{ color: '#888' }}>
            Augment Fit
          </div>
          <div className="space-y-1.5">
            {augmentRecommendations.map((augment) => (
              <div
                key={augment.name}
                className="flex items-center justify-between gap-2 rounded px-2 py-1"
                style={{ backgroundColor: '#2a2a3f' }}
              >
                <div className="flex flex-col">
                  <span className="text-xs font-medium" style={{ color: '#e5e7eb' }}>
                    {augment.name}
                  </span>
                  <span className="text-[10px]" style={{ color: '#888' }}>
                    {augment.matchingTypes.length > 0
                      ? `Matches: ${augment.matchingTypes.join(', ')}`
                      : 'General power'}
                  </span>
                </div>
                <div className="text-right">
                  <span
                    className="text-[10px] uppercase tracking-wide"
                    style={{ color: augment.enemyBenefit === 'High' ? COLORS.statBad : augment.enemyBenefit === 'Medium' ? COLORS.statMid : COLORS.statGood }}
                  >
                    Enemy {augment.enemyBenefit}
                  </span>
                  <div className="text-[10px]" style={{ color: '#888' }}>
                    Tier {augment.tier}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

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
