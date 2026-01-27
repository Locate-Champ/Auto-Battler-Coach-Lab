import React, { useState, useMemo } from 'react';

// ═══════════════════════════════════════════════════════════════════════════════
// DATA: Your actual performance stats from match history analysis
// ═══════════════════════════════════════════════════════════════════════════════

const TRAIT_PERFORMANCE = {
  'Harvester': { top4: 88.0, tier: 'S' },
  'The Boss': { top4: 87.5, tier: 'S' },
  'Soulbound': { top4: 72.7, tier: 'A' },
  'Chronokeeper': { top4: 83.3, tier: 'S' },
  'Blacksmith': { top4: 70.8, tier: 'A' },
  'Heroic': { top4: 73.1, tier: 'A' },
  'Rune Mage': { top4: 72.7, tier: 'A' },
  'Warden': { top4: 65.5, tier: 'B' },
  'Bruiser': { top4: 63.8, tier: 'B' },
  'Demacia': { top4: 68.2, tier: 'B' },
  'Bilgewater': { top4: 7.1, tier: 'F' },
  'Quickstriker': { top4: 64.3, tier: 'B' },
  'Juggernaut': { top4: 54.2, tier: 'C' },
  'Arcanist': { top4: 55.3, tier: 'C' },
  'Defender': { top4: 59.7, tier: 'C' },
  'Invoker': { top4: 58.6, tier: 'C' },
  'Targon': { top4: 55.2, tier: 'C' },
  'Void': { top4: 36.4, tier: 'D' },
  'Noxus': { top4: 40.0, tier: 'D' },
  'Ionia': { top4: 68.4, tier: 'B' },
};

const CARRY_PERFORMANCE = [
  { name: 'Fiddlesticks', cost: 5, top4: 100.0, winRate: 25.0 },
  { name: 'Ornn', cost: 5, top4: 100.0, winRate: 28.6 },
  { name: 'Sett', cost: 5, top4: 100.0, winRate: 0.0 },
  { name: 'Zilean', cost: 5, top4: 80.0, winRate: 0.0 },
  { name: 'Thresh', cost: 5, top4: 80.0, winRate: 0.0 },
  { name: 'Ryze', cost: 5, top4: 70.0, winRate: 10.0 },
  { name: 'Lucian & Senna', cost: 5, top4: 66.7, winRate: 33.3 },
  { name: 'Garen', cost: 4, top4: 66.7, winRate: 16.7 },
  { name: 'Shyvana', cost: 5, top4: 57.1, winRate: 28.6 },
];

const ITEM_PERFORMANCE = {
  build: [
    { name: "Protector's Vow", top4: 100.0 },
    { name: 'Edge of Night', top4: 100.0 },
    { name: 'Blue Buff', top4: 85.7 },
    { name: 'Spirit Visage', top4: 88.9 },
    { name: 'Morellonomicon', top4: 76.9 },
    { name: 'Bramble Vest', top4: 72.7 },
  ],
  avoid: [
    { name: 'Infinity Edge', top4: 20.0 },
    { name: 'Giant Slayer', top4: 25.0 },
    { name: "Kraken's Fury", top4: 12.5 },
    { name: "Warmog's Armor", top4: 0.0 },
    { name: 'Sunfire Cape', top4: 25.0 },
  ],
};

const COMP_ARCHETYPES = [
  { id: 'harvester', name: 'Harvester', traits: ['Harvester'], color: '#eab308' },
  { id: 'soulbound', name: 'Soulbound', traits: ['Soulbound'], color: '#a855f7' },
  { id: 'blacksmith', name: 'Blacksmith', traits: ['Blacksmith'], color: '#f97316' },
  { id: 'bruiser', name: 'Bruiser', traits: ['Bruiser', 'Warden'], color: '#22c55e' },
  { id: 'arcanist', name: 'Arcanist', traits: ['Arcanist', 'Invoker'], color: '#3b82f6' },
  { id: 'bilgewater', name: 'Bilgewater', traits: ['Bilgewater'], color: '#ef4444' },
];

const COST_COLORS = {
  1: { border: '#6b7280', glow: 'rgba(107, 114, 128, 0.5)' },
  2: { border: '#22c55e', glow: 'rgba(34, 197, 94, 0.5)' },
  3: { border: '#3b82f6', glow: 'rgba(59, 130, 246, 0.5)' },
  4: { border: '#a855f7', glow: 'rgba(168, 85, 247, 0.5)' },
  5: { border: '#eab308', glow: 'rgba(234, 179, 8, 0.5)' },
};

const TIER_COLORS = {
  S: '#eab308',
  A: '#22c55e',
  B: '#3b82f6',
  C: '#6b7280',
  D: '#f97316',
  F: '#ef4444',
};

// Demo board state (simulating Riot API data)
const DEMO_UNITS = [
  { row: 0, col: 1, name: 'Ornn', cost: 5, stars: 2, items: ['Bramble Vest', 'Dragon\'s Claw'] },
  { row: 0, col: 3, name: 'Sett', cost: 5, stars: 1, items: [] },
  { row: 1, col: 2, name: 'Shen', cost: 2, stars: 2, items: ['Gargoyle'] },
  { row: 2, col: 1, name: 'Fiddlesticks', cost: 5, stars: 2, items: ['Morellonomicon', 'Blue Buff'] },
  { row: 2, col: 4, name: 'Ryze', cost: 5, stars: 1, items: ['Void Staff'] },
  { row: 3, col: 3, name: 'Zilean', cost: 5, stars: 1, items: [] },
];

// ═══════════════════════════════════════════════════════════════════════════════
// COMPONENTS
// ═══════════════════════════════════════════════════════════════════════════════

// Tier Badge Component
const TierBadge = ({ tier }) => (
  <span
    className="text-[10px] font-bold text-white px-1 py-0.5 rounded"
    style={{ backgroundColor: TIER_COLORS[tier] || TIER_COLORS.C }}
  >
    {tier}
  </span>
);

// Status Dot with pulse animation
const StatusDot = ({ isLive }) => (
  <div className="flex items-center gap-2">
    <div className="relative">
      <div
        className={`w-2 h-2 rounded-full ${isLive ? 'bg-green-500' : 'bg-gray-500'}`}
      />
      {isLive && (
        <div className="absolute inset-0 w-2 h-2 rounded-full bg-green-500 animate-ping opacity-75" />
      )}
    </div>
    <span className="text-xs text-gray-400">
      {isLive ? 'Live • 3s poll' : 'Offline'}
    </span>
  </div>
);

// Panel Card wrapper
const PanelCard = ({ title, children, className = '' }) => (
  <div
    className={`bg-gray-900/90 border border-gray-700 rounded-lg p-3 ${className}`}
  >
    <h3 className="text-sm font-bold text-cyan-400 border-b border-gray-700 pb-2 mb-2">
      {title}
    </h3>
    {children}
  </div>
);

// Trait Row
const TraitRow = ({ name, count, tier }) => (
  <div className="flex items-center justify-between h-6">
    <div className="flex items-center gap-1">
      <span className="text-sm text-gray-300">{name}</span>
      {tier && <TierBadge tier={tier} />}
    </div>
    <span className="text-sm text-gray-500">{count}</span>
  </div>
);

// Counter buttons for Lobby Tracker
const Counter = ({ value, onChange }) => (
  <div className="flex items-center gap-0.5">
    <button
      onClick={() => onChange(Math.max(0, value - 1))}
      className="w-5 h-5 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 text-xs font-bold transition-colors"
    >
      −
    </button>
    <span className="w-5 text-center text-sm font-bold text-white">{value}</span>
    <button
      onClick={() => onChange(Math.min(7, value + 1))}
      className="w-5 h-5 bg-gray-700 hover:bg-gray-600 rounded text-gray-300 text-xs font-bold transition-colors"
    >
      +
    </button>
  </div>
);

// Comp Row for Lobby Tracker
const CompRow = ({ comp, count, onChange }) => {
  const statusIcon = count === 0 ? '✓' : count === 1 ? '⚠' : '⛔';
  const statusColor = count === 0 ? '#22c55e' : count === 1 ? '#eab308' : '#ef4444';
  
  return (
    <div className="flex items-center justify-between h-7">
      <div className="flex items-center gap-2">
        <span style={{ color: statusColor }}>{statusIcon}</span>
        <span
          className="text-xs"
          style={{ color: count > 0 ? '#9ca3af' : comp.color }}
        >
          {comp.name}
        </span>
      </div>
      <Counter value={count} onChange={onChange} />
    </div>
  );
};

// Empty Hex
const EmptyHex = () => (
  <div
    className="w-16 h-[72px] flex items-center justify-center opacity-40 hover:opacity-60 transition-opacity"
  >
    <div
      className="w-14 h-12 border-2 border-gray-700"
      style={{
        background: 'linear-gradient(135deg, #1f2937, #111827)',
        clipPath: 'polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)',
      }}
    />
  </div>
);

// Hex Unit with champion
const HexUnit = ({ unit }) => {
  const colors = COST_COLORS[unit.cost] || COST_COLORS[1];
  const stars = '★'.repeat(unit.stars);
  
  // Convert name to lowercase for icon URL
  const iconName = unit.name.toLowerCase().replace(/['\s&]/g, '').replace('lucian&senna', 'luciansenna');
  const iconUrl = `https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_${iconName}_square.tft_set16.png`;
  
  return (
    <div className="w-16 h-[72px] relative flex flex-col items-center cursor-pointer hover:scale-105 transition-transform">
      {/* Item slots */}
      <div className="flex gap-0.5 mb-0.5">
        {[0, 1].map((i) => (
          <div
            key={i}
            className="w-4 h-4 rounded-full bg-gray-800 border border-gray-600"
            title={unit.items[i] || 'Empty'}
          >
            {unit.items[i] && (
              <div className="w-full h-full rounded-full bg-gradient-to-br from-yellow-600 to-yellow-800" />
            )}
          </div>
        ))}
      </div>
      
      {/* Stars */}
      <div
        className="text-[10px] absolute"
        style={{
          top: '20px',
          color: '#eab308',
          textShadow: '0 1px 2px rgba(0,0,0,0.8)',
          zIndex: 10,
        }}
      >
        {stars}
      </div>
      
      {/* Hexagon portrait */}
      <div
        className="w-14 h-12 relative overflow-hidden"
        style={{
          clipPath: 'polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)',
          border: `2px solid ${colors.border}`,
          boxShadow: `0 0 8px ${colors.glow}`,
        }}
      >
        <img
          src={iconUrl}
          alt={unit.name}
          className="w-full h-full object-cover scale-110"
          onError={(e) => {
            e.target.style.display = 'none';
            e.target.parentElement.style.background = colors.glow;
          }}
        />
      </div>
      
      {/* Champion name */}
      <span
        className="text-[9px] text-white mt-0.5 truncate max-w-full"
        style={{ textShadow: '0 1px 2px rgba(0,0,0,0.9)' }}
      >
        {unit.name}
      </span>
    </div>
  );
};

// Hex Board (7x4 grid)
const HexBoard = ({ units }) => {
  const getUnit = (row, col) => units.find((u) => u.row === row && u.col === col);
  
  return (
    <div className="flex flex-col items-center gap-[-8px]">
      {[0, 1, 2, 3].map((row) => (
        <div
          key={row}
          className="flex"
          style={{
            marginLeft: row % 2 === 1 ? '32px' : '0',
            marginTop: row > 0 ? '-8px' : '0',
          }}
        >
          {[0, 1, 2, 3, 4, 5, 6].map((col) => {
            const unit = getUnit(row, col);
            return (
              <div key={`${row}-${col}`}>
                {unit ? <HexUnit unit={unit} /> : <EmptyHex />}
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
};

// Suggestion Card
const SuggestionCard = ({ rank, name, score, contested, isTop }) => {
  const medals = ['🥇', '🥈', '🥉', '4️⃣'];
  
  return (
    <div
      className={`p-2 rounded mb-1.5 ${
        isTop
          ? 'bg-cyan-900/30 border border-cyan-600/30'
          : 'bg-gray-800/50'
      }`}
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span>{medals[rank] || `${rank + 1}.`}</span>
          <span className="text-sm font-bold text-white">{name}</span>
        </div>
        <span className="text-sm font-bold text-cyan-400">{score.toFixed(0)}%</span>
      </div>
      {contested > 0 && (
        <div className="text-xs text-yellow-500 mt-1">
          ⚠ {contested} contesting
        </div>
      )}
    </div>
  );
};

// Unit Row for Priority Units
const UnitRow = ({ unit }) => (
  <div className="flex items-center justify-between h-[22px]">
    <div className="flex items-center gap-1">
      <span
        className="text-sm"
        style={{ color: COST_COLORS[unit.cost]?.border || '#fff' }}
      >
        {unit.name}
      </span>
      <span className="text-xs text-gray-500">({unit.cost}💰)</span>
    </div>
    <span className="text-sm text-gray-400">{unit.top4.toFixed(0)}%</span>
  </div>
);

// Item Row
const ItemRow = ({ item, isBuild }) => (
  <div className="flex items-center justify-between h-[18px]">
    <span
      className={`text-xs ${isBuild ? 'text-gray-300' : 'text-gray-500 line-through'}`}
    >
      {item.name}
    </span>
    <span className={`text-xs ${isBuild ? 'text-green-500' : 'text-red-500'}`}>
      {item.top4.toFixed(0)}%
    </span>
  </div>
);

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════════

export default function TFTCoachCompanion() {
  const [units] = useState(DEMO_UNITS);
  const [compCounts, setCompCounts] = useState({
    harvester: 1,
    soulbound: 0,
    blacksmith: 2,
    bruiser: 1,
    arcanist: 0,
    bilgewater: 0,
  });

  // Calculate active traits from board
  const activeTraits = useMemo(() => {
    const traitMap = {
      Ornn: ['Blacksmith'],
      Sett: ['The Boss', 'Bruiser'],
      Shen: ['Ionia', 'Warden'],
      Fiddlesticks: ['Harvester'],
      Ryze: ['Rune Mage', 'Arcanist'],
      Zilean: ['Chronokeeper', 'Invoker'],
    };
    
    const counts = {};
    units.forEach((unit) => {
      const traits = traitMap[unit.name] || [];
      traits.forEach((trait) => {
        counts[trait] = (counts[trait] || 0) + 1;
      });
    });
    
    return Object.entries(counts)
      .map(([name, count]) => ({
        name,
        count,
        tier: TRAIT_PERFORMANCE[name]?.tier || 'C',
        top4: TRAIT_PERFORMANCE[name]?.top4 || 50,
      }))
      .sort((a, b) => b.top4 - a.top4);
  }, [units]);

  // Calculate board stats
  const boardCost = units.reduce((sum, u) => sum + u.cost * u.stars, 0);
  const unitCount = units.length;

  // Calculate recommendations with contestation penalty
  const recommendations = useMemo(() => {
    return COMP_ARCHETYPES.map((comp) => {
      const baseScore = comp.traits.reduce((sum, trait) => {
        return sum + (TRAIT_PERFORMANCE[trait]?.top4 || 50);
      }, 0) / comp.traits.length;
      
      const contested = compCounts[comp.id] || 0;
      const penalty = contested * 0.15;
      const finalScore = baseScore * (1 - penalty);
      
      return { ...comp, baseScore, contested, finalScore };
    })
      .sort((a, b) => b.finalScore - a.finalScore)
      .slice(0, 4);
  }, [compCounts]);

  // Priority units (not on board)
  const priorityUnits = CARRY_PERFORMANCE
    .filter((carry) => !units.find((u) => u.name === carry.name))
    .slice(0, 5);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-950 via-gray-900 to-gray-950 text-white p-4">
      {/* HEADER */}
      <header className="flex items-center justify-between h-14 px-4 border-b border-gray-800 mb-4">
        <div>
          <h1 className="text-xl font-bold text-cyan-400">TFT Coach Companion</h1>
          <p className="text-xs text-gray-500">Set 16.2 • Based on 163 games</p>
        </div>
        <StatusDot isLive={true} />
      </header>

      {/* MAIN GRID */}
      <div className="grid grid-cols-12 gap-4">
        {/* LEFT COLUMN */}
        <div className="col-span-3 space-y-4">
          {/* Traits Panel */}
          <PanelCard title="Traits">
            <div className="flex gap-4 mb-3 text-sm">
              <span>👥 <strong>{unitCount}</strong></span>
              <span>💰 <strong>{boardCost}g</strong></span>
            </div>
            <div className="space-y-1">
              {activeTraits.map((trait) => (
                <TraitRow
                  key={trait.name}
                  name={trait.name}
                  count={trait.count}
                  tier={trait.tier}
                />
              ))}
            </div>
          </PanelCard>

          {/* Lobby Tracker */}
          <PanelCard title="Lobby Tracker">
            <div className="space-y-1">
              {COMP_ARCHETYPES.map((comp) => (
                <CompRow
                  key={comp.id}
                  comp={comp}
                  count={compCounts[comp.id]}
                  onChange={(val) =>
                    setCompCounts((prev) => ({ ...prev, [comp.id]: val }))
                  }
                />
              ))}
            </div>
          </PanelCard>
        </div>

        {/* CENTER COLUMN */}
        <div className="col-span-6 space-y-4">
          {/* Board */}
          <div className="bg-gray-900/50 border border-gray-700 rounded-lg p-4">
            <p className="text-xs text-gray-500 mb-3 text-center">
              BOARD STATE (Live from Riot API)
            </p>
            <HexBoard units={units} />
          </div>

          {/* Items Panel */}
          <PanelCard title="Items">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <h4 className="text-xs font-bold text-green-500 mb-2">BUILD:</h4>
                {ITEM_PERFORMANCE.build.slice(0, 5).map((item) => (
                  <ItemRow key={item.name} item={item} isBuild={true} />
                ))}
              </div>
              <div>
                <h4 className="text-xs font-bold text-red-500 mb-2">AVOID:</h4>
                {ITEM_PERFORMANCE.avoid.slice(0, 5).map((item) => (
                  <ItemRow key={item.name} item={item} isBuild={false} />
                ))}
              </div>
            </div>
          </PanelCard>
        </div>

        {/* RIGHT COLUMN */}
        <div className="col-span-3 space-y-4">
          {/* Recommendations */}
          <PanelCard title="Recommended">
            {recommendations.map((comp, i) => (
              <SuggestionCard
                key={comp.id}
                rank={i}
                name={comp.name}
                score={comp.finalScore}
                contested={comp.contested}
                isTop={i === 0}
              />
            ))}
          </PanelCard>

          {/* Priority Units */}
          <PanelCard title="Find These">
            <div className="space-y-1">
              {priorityUnits.map((unit) => (
                <UnitRow key={unit.name} unit={unit} />
              ))}
            </div>
          </PanelCard>
        </div>
      </div>
    </div>
  );
}
