import React, { useState } from 'react';
import CompCard, { Comp, ContestedState } from './CompCard';

// Static comp data from mockup
const STATIC_COMPS: Comp[] = [
  {
    id: 'fiddlesticks-carry',
    name: 'Fiddlesticks Carry',
    playStyle: 'Fast 9',
    tier: 'S',
    cost: 38,
    difficulty: 'Easy',
    champions: [
      { name: 'Anivia', cost: 1, imageFile: 'Anivia.png' },
      { name: 'Neeko', cost: 2, imageFile: 'Neeko.png' },
      { name: 'Nautilus', cost: 3, imageFile: 'Nautilus.png' },
      { name: 'Sejuani', cost: 3, imageFile: 'Sejuani.png' },
      { name: 'Braum', cost: 4, imageFile: 'Braum.png' },
      { name: 'Taric', cost: 4, imageFile: 'Taric.png' },
      { name: 'Fiddlesticks', cost: 5, imageFile: 'Fiddlesticks.png' },
      { name: 'Ornn', cost: 5, imageFile: 'Ornn.png' },
      { name: 'Zilean', cost: 5, imageFile: 'Zilean.png' },
    ],
    traits: [
      { name: 'Harbinger', count: 4, isActive: true },
      { name: 'Invoker', count: 2, isActive: true },
    ],
    stats: { top4Rate: 70, winRate: 18, avgPlacement: 3.2, playRate: 12 },
    coreItems: [
      { name: 'Morellonomicon', imageFile: 'Morellonomicon.png' },
      { name: 'Blue Buff', imageFile: 'Blue Buff.png' },
      { name: 'Jeweled Gauntlet', imageFile: 'Jeweled Gauntlet.png' },
    ],
  },
  {
    id: 'ryze-arcanist',
    name: 'Ryze Arcanist',
    playStyle: 'Fast 8',
    tier: 'S',
    cost: 35,
    difficulty: 'Medium',
    champions: [
      { name: 'Lulu', cost: 1, imageFile: 'Lulu.png' },
      { name: 'Twisted Fate', cost: 2, imageFile: 'Twisted Fate.png' },
      { name: 'Ahri', cost: 3, imageFile: 'Ahri.png' },
      { name: 'Zoe', cost: 3, imageFile: 'Zoe.png' },
      { name: 'Lux', cost: 4, imageFile: 'Lux.png' },
      { name: 'Seraphine', cost: 4, imageFile: 'Seraphine.png' },
      { name: 'Taric', cost: 4, imageFile: 'Taric.png' },
      { name: 'Ryze', cost: 5, imageFile: 'Ryze.png' },
      { name: 'Zilean', cost: 5, imageFile: 'Zilean.png' },
    ],
    traits: [
      { name: 'Arcanist', count: 6, isActive: true },
      { name: 'Scholar', count: 2, isActive: true },
    ],
    stats: { top4Rate: 68, winRate: 15, avgPlacement: 3.4, playRate: 8 },
    coreItems: [
      { name: "Archangel's Staff", imageFile: "Archangel's Staff.png" },
      { name: "Rabadon's Deathcap", imageFile: "Rabadon's Deathcap.png" },
      { name: 'Jeweled Gauntlet', imageFile: 'Jeweled Gauntlet.png' },
    ],
  },
  {
    id: 'ambessa-slayer',
    name: 'Ambessa Slayer',
    playStyle: 'Fast 8',
    tier: 'A',
    cost: 32,
    difficulty: 'Medium',
    champions: [
      { name: 'Viego', cost: 1, imageFile: 'Viego.png' },
      { name: 'Ekko', cost: 2, imageFile: 'Ekko.png' },
      { name: 'Draven', cost: 3, imageFile: 'Draven.png' },
      { name: 'Leona', cost: 3, imageFile: 'Leona.png' },
      { name: 'Ambessa', cost: 4, imageFile: 'Ambessa.png' },
      { name: 'Swain', cost: 4, imageFile: 'Swain.png' },
      { name: 'Garen', cost: 4, imageFile: 'Garen.png' },
      { name: 'Kindred', cost: 5, imageFile: 'Kindred.png' },
      { name: 'Mordekaiser', cost: 5, imageFile: 'Mordekaiser.png' },
    ],
    traits: [
      { name: 'Slayer', count: 4, isActive: true },
      { name: 'Noxus', count: 4, isActive: true },
    ],
    stats: { top4Rate: 58, winRate: 12, avgPlacement: 3.8, playRate: 15 },
    coreItems: [
      { name: 'Deathblade', imageFile: 'Deathblade.png' },
      { name: 'Bloodthirster', imageFile: 'Bloodthirster.png' },
      { name: 'Quicksilver', imageFile: 'Quicksilver.png' },
    ],
  },
  {
    id: 'ornn-tank',
    name: 'Ornn Tank',
    playStyle: 'Fast 9',
    tier: 'A',
    cost: 36,
    difficulty: 'Easy',
    champions: [
      { name: 'Anivia', cost: 1, imageFile: 'Anivia.png' },
      { name: 'Ashe', cost: 2, imageFile: 'Ashe.png' },
      { name: 'Sejuani', cost: 3, imageFile: 'Sejuani.png' },
      { name: 'Braum', cost: 4, imageFile: 'Braum.png' },
      { name: 'Lissandra', cost: 4, imageFile: 'Lissandra.png' },
      { name: 'Taric', cost: 4, imageFile: 'Taric.png' },
      { name: 'Ornn', cost: 5, imageFile: 'Ornn.png' },
      { name: 'Fiddlesticks', cost: 5, imageFile: 'Fiddlesticks.png' },
      { name: 'Zilean', cost: 5, imageFile: 'Zilean.png' },
    ],
    traits: [
      { name: 'Freljord', count: 4, isActive: true },
      { name: 'Invoker', count: 2, isActive: true },
    ],
    stats: { top4Rate: 55, winRate: 10, avgPlacement: 4.0, playRate: 6 },
    coreItems: [
      { name: "Warmog's Armor", imageFile: "Warmog's Armor.png" },
      { name: 'Gargoyle Stoneplate', imageFile: 'Gargoyle Stoneplate.png' },
      { name: "Dragon's Claw", imageFile: "Dragon's Claw.png" },
    ],
  },
  {
    id: 'tristana-reroll',
    name: 'Tristana Reroll',
    playStyle: '2-Cost Reroll',
    tier: 'B',
    cost: 22,
    difficulty: 'Hard',
    champions: [
      { name: 'Caitlyn', cost: 1, imageFile: 'Caitlyn.png' },
      { name: 'Rumble', cost: 1, imageFile: 'Rumble.png' },
      { name: 'Tristana', cost: 2, imageFile: 'Tristana.png' },
      { name: 'Teemo', cost: 2, imageFile: 'Teemo.png' },
      { name: 'Jinx', cost: 3, imageFile: 'Jinx.png' },
      { name: 'Gangplank', cost: 3, imageFile: 'Gangplank.png' },
      { name: 'Miss Fortune', cost: 4, imageFile: 'Miss Fortune.png' },
      { name: 'Braum', cost: 4, imageFile: 'Braum.png' },
      { name: 'Lucian', cost: 5, imageFile: 'Lucian.png' },
    ],
    traits: [
      { name: 'Gunslinger', count: 4, isActive: true },
      { name: 'Yordle', count: 3, isActive: true },
    ],
    stats: { top4Rate: 42, winRate: 6, avgPlacement: 4.8, playRate: 20 },
    coreItems: [
      { name: 'Infinity Edge', imageFile: 'Infinity Edge.png' },
      { name: 'Last Whisper', imageFile: 'Last Whisper.png' },
      { name: 'Giant Slayer', imageFile: 'Giant Slayer.png' },
    ],
  },
];

interface CompsPanelProps {
  className?: string;
}

const CompsPanel: React.FC<CompsPanelProps> = ({ className }) => {
  const [contestedStates, setContestedStates] = useState<Record<string, ContestedState>>({});

  const getContestedState = (compId: string): ContestedState => {
    return contestedStates[compId] || 'neutral';
  };

  const handleContestedToggle = (compId: string, newState: ContestedState) => {
    setContestedStates((prev) => ({
      ...prev,
      [compId]: newState,
    }));
  };

  return (
    <div
      className={`w-[340px] rounded-lg overflow-hidden ${className ?? ''}`}
      style={{
        backgroundColor: '#252538',
        border: '1px solid #3a3a4f',
      }}
    >
      {/* Header */}
      <div
        className="py-3 px-4 text-center"
        style={{
          background: 'linear-gradient(180deg, #c9a033 0%, #8b6914 100%)',
        }}
      >
        <h2 className="text-white text-base font-semibold tracking-wide">Top Comps</h2>
      </div>

      {/* Scrollable list */}
      <div
        className="p-2 flex flex-col gap-2 overflow-y-auto"
        style={{ maxHeight: '700px' }}
      >
        {STATIC_COMPS.map((comp) => (
          <CompCard
            key={comp.id}
            comp={comp}
            contestedState={getContestedState(comp.id)}
            onContestedToggle={(newState) => handleContestedToggle(comp.id, newState)}
          />
        ))}
      </div>
    </div>
  );
};

export default CompsPanel;
