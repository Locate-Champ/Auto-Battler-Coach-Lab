import React from 'react';

// Types
type ChampionCost = 1 | 2 | 3 | 4 | 5;
type CompTier = 'S' | 'A' | 'B';
type PlayStyle = 'Fast 9' | 'Fast 8' | '2-Cost Reroll' | '3-Cost Reroll' | 'Standard';
type Difficulty = 'Easy' | 'Medium' | 'Hard';
type ContestedState = 'neutral' | 'contested' | 'clear';

interface CompChampion {
  name: string;
  cost: ChampionCost;
  imageFile: string;
  isCarry?: boolean;
}

interface CompTrait {
  name: string;
  count: number;
  isActive: boolean;
}

interface CoreItem {
  name: string;
  imageFile: string;
}

interface CompStats {
  top4Rate: number;
  winRate: number;
  avgPlacement: number;
  playRate: number;
}

export interface Comp {
  id: string;
  name: string;
  playStyle: PlayStyle;
  tier: CompTier;
  cost: number;
  difficulty: Difficulty;
  champions: CompChampion[];
  traits: CompTrait[];
  stats: CompStats;
  coreItems: CoreItem[];
}

// Colors
const COLORS = {
  cardBg: '#1e1e2f',
  cardBorder: '#3a3a4f',
  metaBadgeBg: '#2a2a3f',
  tierS: { start: '#ff6b6b', end: '#c92a2a' },
  tierA: { start: '#ffa94d', end: '#e67700' },
  tierB: { start: '#69db7c', end: '#2f9e44' },
  cost: {
    1: '#5a5a6f',
    2: '#2ecc71',
    3: '#3498db',
    4: '#9b59b6',
    5: '#f1c40f',
  } as Record<ChampionCost, string>,
  statGood: '#69db7c',
  statMid: '#ffa94d',
  statBad: '#ff6b6b',
  traitActiveBg: '#3a3a1f',
  traitActiveText: '#c9a033',
  contested: { bg: '#4a1a1a', border: '#ff6b6b', icon: '#ff6b6b' },
  clear: { bg: '#1a3a1a', border: '#69db7c', icon: '#69db7c' },
  neutral: { bg: '#2a2a3f', border: '#3a3a4f', icon: '#555555' },
  difficultyEasy: '#69db7c',
  difficultyMedium: '#ffa94d',
  difficultyHard: '#ff6b6b',
  gold: '#c9a033',
  carryGlow: '#c9a033',
};

// Helper functions
const getTierGradient = (tier: CompTier): string => {
  const colors = tier === 'S' ? COLORS.tierS : tier === 'A' ? COLORS.tierA : COLORS.tierB;
  return `linear-gradient(135deg, ${colors.start}, ${colors.end})`;
};

const getStatColor = (value: number, type: 'top4' | 'winRate' | 'avgPlacement' | 'playRate'): string => {
  if (type === 'playRate') return '#ffffff';
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

const getDifficultyColor = (difficulty: Difficulty): string => {
  if (difficulty === 'Easy') return COLORS.difficultyEasy;
  if (difficulty === 'Medium') return COLORS.difficultyMedium;
  return COLORS.difficultyHard;
};

const getNextContestedState = (current: ContestedState): ContestedState => {
  if (current === 'neutral') return 'contested';
  if (current === 'contested') return 'clear';
  return 'neutral';
};

// Image loading helpers
const getChampionImage = (filename: string): string => {
  return new URL(`./images/champion images/${filename}`, import.meta.url).href;
};

const getItemImage = (filename: string): string => {
  return new URL(`./images/craftable items images/${filename}`, import.meta.url).href;
};

// Sub-components
const TierBadge: React.FC<{ tier: CompTier }> = ({ tier }) => (
  <span
    className="px-2 py-0.5 rounded text-xs font-bold"
    style={{ background: getTierGradient(tier), color: '#fff' }}
  >
    {tier}
  </span>
);

const ChampionIcon: React.FC<{ champion: CompChampion; size?: number }> = ({ champion, size = 28 }) => (
  <div
    className="rounded overflow-hidden"
    style={{
      width: size,
      height: size,
      border: champion.isCarry
        ? `2px solid ${COLORS.carryGlow}`
        : `2px solid ${COLORS.cost[champion.cost]}`,
      backgroundColor: '#3a3a4f',
      boxShadow: champion.isCarry
        ? `0 0 8px ${COLORS.carryGlow}, 0 0 12px ${COLORS.carryGlow}`
        : 'none',
    }}
  >
    <img
      src={getChampionImage(champion.imageFile)}
      alt={champion.name}
      className="w-full h-full object-cover"
      draggable={false}
    />
  </div>
);

const TraitBadge: React.FC<{ trait: CompTrait }> = ({ trait }) => (
  <span
    className="flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px]"
    style={{
      backgroundColor: trait.isActive ? COLORS.traitActiveBg : COLORS.metaBadgeBg,
      color: trait.isActive ? COLORS.traitActiveText : '#aaa',
      border: trait.isActive ? `1px solid ${COLORS.traitActiveText}` : 'none',
    }}
  >
    <span className="font-semibold">{trait.count}</span>
    {trait.name}
  </span>
);

const StatDisplay: React.FC<{ value: number; label: string; type: 'top4' | 'winRate' | 'avgPlacement' | 'playRate' }> = ({ value, label, type }) => (
  <div className="flex flex-col items-center">
    <span className="text-sm font-semibold" style={{ color: getStatColor(value, type) }}>
      {type === 'avgPlacement' ? value.toFixed(1) : `${value}%`}
    </span>
    <span className="text-[10px] uppercase tracking-wide" style={{ color: '#888' }}>{label}</span>
  </div>
);

const ContestedToggle: React.FC<{ state: ContestedState; onToggle?: () => void }> = ({ state, onToggle }) => {
  const colors = state === 'contested' ? COLORS.contested : state === 'clear' ? COLORS.clear : COLORS.neutral;

  return (
    <button
      onClick={(e) => {
        e.stopPropagation();
        onToggle?.();
      }}
      className="w-7 h-7 rounded flex items-center justify-center transition-all duration-200"
      style={{
        backgroundColor: colors.bg,
        border: `1px solid ${colors.border}`,
      }}
    >
      {state === 'contested' && (
        <svg viewBox="0 0 24 24" fill="none" stroke={colors.icon} strokeWidth="3" className="w-4 h-4">
          <path d="M18 6L6 18M6 6l12 12" />
        </svg>
      )}
      {state === 'clear' && (
        <svg viewBox="0 0 24 24" fill="none" stroke={colors.icon} strokeWidth="3" className="w-4 h-4">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      )}
      {state === 'neutral' && (
        <svg viewBox="0 0 24 24" fill="none" stroke={colors.icon} strokeWidth="2" className="w-4 h-4">
          <circle cx="12" cy="12" r="10" />
        </svg>
      )}
    </button>
  );
};

// Main CompCard component
interface CompCardProps {
  comp: Comp;
  contestedState: ContestedState;
  onContestedToggle?: (newState: ContestedState) => void;
  onClick?: () => void;
}

const CompCard: React.FC<CompCardProps> = ({ comp, contestedState, onContestedToggle, onClick }) => {
  const isContested = contestedState === 'contested';

  return (
    <div
      className="rounded-md p-3 cursor-pointer transition-all duration-200"
      style={{
        backgroundColor: COLORS.cardBg,
        border: `1px solid ${isContested ? COLORS.contested.border : COLORS.cardBorder}`,
        opacity: isContested ? 0.5 : 1,
      }}
      onClick={onClick}
      onMouseEnter={(e) => {
        if (!isContested) {
          e.currentTarget.style.borderColor = COLORS.gold;
          e.currentTarget.style.transform = 'translateX(2px)';
        }
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = isContested ? COLORS.contested.border : COLORS.cardBorder;
        e.currentTarget.style.transform = 'translateX(0)';
      }}
    >
      {/* Header: Name + Tier */}
      <div className="flex justify-between items-start mb-1.5">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm font-semibold text-white">{comp.name}</span>
          <span className="text-[10px]" style={{ color: '#888' }}>{comp.playStyle}</span>
        </div>
        <TierBadge tier={comp.tier} />
      </div>

      {/* Meta badges: Cost + Difficulty */}
      <div className="flex gap-2 mb-2">
        <span
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px]"
          style={{ backgroundColor: COLORS.metaBadgeBg, color: '#f1c40f' }}
        >
          <svg viewBox="0 0 24 24" fill="currentColor" className="w-3 h-3">
            <circle cx="12" cy="12" r="10" />
          </svg>
          {comp.cost}g
        </span>
        <span
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px]"
          style={{ backgroundColor: COLORS.metaBadgeBg, color: getDifficultyColor(comp.difficulty) }}
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-3 h-3">
            <path d="M12 2v20M2 12h20" />
          </svg>
          {comp.difficulty}
        </span>
      </div>

      {/* Champions row */}
      <div className="flex gap-1 flex-wrap mb-2">
        {comp.champions.map((champ) => (
          <ChampionIcon key={champ.name} champion={champ} />
        ))}
      </div>

      {/* Traits row */}
      <div className="flex gap-1.5 flex-wrap mb-2">
        {comp.traits.map((trait) => (
          <TraitBadge key={trait.name} trait={trait} />
        ))}
      </div>

      {/* Stats row */}
      <div className="flex gap-3 mb-2">
        <StatDisplay value={comp.stats.top4Rate} label="Top 4" type="top4" />
        <StatDisplay value={comp.stats.winRate} label="Win" type="winRate" />
        <StatDisplay value={comp.stats.avgPlacement} label="Avg" type="avgPlacement" />
        <StatDisplay value={comp.stats.playRate} label="Play" type="playRate" />
      </div>

      {/* Footer: Core items + Contested toggle */}
      <div
        className="flex justify-between items-center pt-2"
        style={{ borderTop: `1px solid ${COLORS.cardBorder}` }}
      >
        <div className="flex items-center gap-1">
          <span className="text-[10px]" style={{ color: '#666' }}>Core:</span>
          {comp.coreItems.map((item) => (
            <div
              key={item.name}
              className="w-6 h-6 rounded overflow-hidden"
              style={{ backgroundColor: '#3a3a4f' }}
            >
              <img
                src={getItemImage(item.imageFile)}
                alt={item.name}
                className="w-full h-full object-cover"
                draggable={false}
              />
            </div>
          ))}
        </div>
        <ContestedToggle
          state={contestedState}
          onToggle={() => onContestedToggle?.(getNextContestedState(contestedState))}
        />
      </div>
    </div>
  );
};

export default CompCard;
export type { Comp, ContestedState };
