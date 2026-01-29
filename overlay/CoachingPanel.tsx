import React, { useState } from 'react';

// Types
type TipType = 'econ' | 'combat' | 'strength' | 'warning' | 'augment' | 'level';
type AugmentChoiceType = 'econ' | 'combat' | 'flex';

interface Tip {
  type: TipType;
  icon: string;
  title: string;
  text: string;
}

interface AugmentRow {
  condition: string;
  choice: AugmentChoiceType;
}

interface AugmentBox {
  title: string;
  rows: AugmentRow[];
}

interface PersonalStat {
  label: string;
  value: string;
  isBad?: boolean;
}

interface PersonalBox {
  title: string;
  stats: PersonalStat[];
}

interface WarningBox {
  title: string;
  items: string[];
}

interface Checkpoint {
  stage: string;
  target: string;
  note: string;
}

interface StageSection {
  id: string;
  badge: string;
  name: string;
  isActive?: boolean;
  tips?: Tip[];
  augmentBox?: AugmentBox;
  personalBox?: PersonalBox;
  warningBox?: WarningBox;
  checkpoints?: Checkpoint[];
}

// Colors
const COLORS = {
  panelBg: '#252538',
  panelBorder: '#3a3a4f',
  sectionBg: '#1e1e2f',
  sectionHover: '#2a2a3f',
  badgeBg: '#3a3a4f',
  gold: '#c9a033',
  goldDark: '#8b6914',
  tipBg: '#252538',
  tipTypes: {
    econ: '#f1c40f',
    combat: '#e74c3c',
    strength: '#2ecc71',
    warning: '#e67e22',
    augment: '#9b59b6',
    level: '#3498db',
  } as Record<TipType, string>,
  augmentChoices: {
    econ: { bg: 'rgba(241, 196, 15, 0.2)', text: '#f1c40f' },
    combat: { bg: 'rgba(231, 76, 60, 0.2)', text: '#e74c3c' },
    flex: { bg: 'rgba(52, 152, 219, 0.2)', text: '#3498db' },
  } as Record<AugmentChoiceType, { bg: string; text: string }>,
};

// Static data
const STAGE_SECTIONS: StageSection[] = [
  {
    id: 'stage-2',
    badge: '2',
    name: 'Early Game',
    tips: [
      {
        type: 'combat',
        icon: '⚔️',
        title: 'Slam Items Early',
        text: "Don't greed for perfect items. Completed items = HP saved = more gold for level 9.",
      },
      {
        type: 'econ',
        icon: '💰',
        title: 'Econ Target: 10g by 2-1',
        text: 'Start banking early. You need 50g by Stage 4 for your fast 9 playstyle.',
      },
      {
        type: 'strength',
        icon: '✓',
        title: 'Flexible Early Board',
        text: "Play strongest board, don't tunnel. Your spike is late — survive now.",
      },
    ],
    augmentBox: {
      title: '🔮 Stage 2-1 Augment',
      rows: [
        { condition: 'Default for you', choice: 'econ' },
        { condition: 'Offered strong combat', choice: 'flex' },
      ],
    },
  },
  {
    id: 'stage-3',
    badge: '3',
    name: 'Mid Game',
    isActive: true,
    tips: [
      {
        type: 'level',
        icon: '⬆️',
        title: 'Level to 6 at 3-2',
        text: "Standard tempo. Don't roll here — you're not a reroll player.",
      },
      {
        type: 'warning',
        icon: '⚠️',
        title: "Don't Panic Roll at 7",
        text: 'Your level 7 rolldowns: 7% top 4. Disaster. Push to 8 minimum.',
      },
      {
        type: 'econ',
        icon: '💰',
        title: 'Econ Target: 50g by 3-5',
        text: 'Stay above 50g. Lose streak is fine — you scale harder than them.',
      },
    ],
    augmentBox: {
      title: '🔮 Stage 3-2 Augment',
      rows: [
        { condition: 'HP above 70', choice: 'econ' },
        { condition: 'HP 50-70', choice: 'flex' },
        { condition: 'HP below 50', choice: 'combat' },
      ],
    },
  },
  {
    id: 'stage-4',
    badge: '4',
    name: 'Transition',
    tips: [
      {
        type: 'level',
        icon: '⬆️',
        title: 'Level 8 at 4-2 or 4-5',
        text: 'This is your rolldown spike. Look for Fiddle/Ornn/Ryze.',
      },
    ],
    personalBox: {
      title: '⭐ Your Best Carries',
      stats: [
        { label: 'Fiddlesticks', value: '70% Top 4' },
        { label: 'Ornn', value: '100% Top 4' },
        { label: 'Ryze', value: '75% Top 4' },
      ],
    },
    warningBox: {
      title: '🚫 Avoid These',
      items: ['AD Carries (0% Top 4)', 'Bilgewater comps (7% Top 4)', 'Rolling at level 7'],
    },
    augmentBox: {
      title: '🔮 Stage 4-2 Augment',
      rows: [
        { condition: 'Found your carry', choice: 'combat' },
        { condition: 'Still building board', choice: 'econ' },
      ],
    },
  },
  {
    id: 'stage-5',
    badge: '5+',
    name: 'Your Win Condition',
    tips: [
      {
        type: 'strength',
        icon: '🏆',
        title: 'Push Level 9',
        text: 'Level 9: 70% top 4 for you. Level 7: 7%. This is your biggest edge.',
      },
      {
        type: 'combat',
        icon: '⚔️',
        title: '9th Unit Matters',
        text: "Add Zilean for utility or 2nd 5-cost carry. Don't add random units.",
      },
      {
        type: 'strength',
        icon: '✓',
        title: 'You Win Long Games',
        text: 'Games over 35 min favor you. Stay alive, scale up, outvalue lobby.',
      },
    ],
    personalBox: {
      title: '📊 Your Level Stats',
      stats: [
        { label: 'Level 9 Games', value: '70% Top 4' },
        { label: 'Level 8 Games', value: '45% Top 4' },
        { label: 'Level 7 Games', value: '7% Top 4', isBad: true },
      ],
    },
  },
  {
    id: 'econ-checkpoints',
    badge: '📋',
    name: 'Econ Checkpoints',
    checkpoints: [
      { stage: '2-1', target: '10g', note: 'Start banking' },
      { stage: '3-2', target: '30g', note: 'After level 6' },
      { stage: '4-1', target: '50g', note: 'Fast 9 pace' },
      { stage: '4-5', target: '30g', note: 'After level 8' },
      { stage: '5-1', target: '50g', note: 'Push 9 ready' },
    ],
  },
];

// Sub-components
const TipCard: React.FC<{ tip: Tip }> = ({ tip }) => (
  <div
    className="flex gap-2.5 p-2.5 mb-2 rounded-md"
    style={{
      backgroundColor: COLORS.tipBg,
      borderLeft: `3px solid ${COLORS.tipTypes[tip.type]}`,
    }}
  >
    <span className="text-base flex-shrink-0" style={{ color: COLORS.tipTypes[tip.type] }}>
      {tip.icon}
    </span>
    <div className="flex-1">
      <div className="text-xs font-semibold text-white mb-1">{tip.title}</div>
      <div className="text-[11px] leading-relaxed" style={{ color: '#999' }}>
        {tip.text}
      </div>
    </div>
  </div>
);

const AugmentBoxComponent: React.FC<{ box: AugmentBox }> = ({ box }) => (
  <div
    className="rounded-md p-3 mt-2.5"
    style={{ backgroundColor: COLORS.sectionHover, border: `1px solid ${COLORS.panelBorder}` }}
  >
    <div
      className="text-[11px] font-semibold mb-2 flex items-center gap-1.5"
      style={{ color: COLORS.tipTypes.augment }}
    >
      {box.title}
    </div>
    {box.rows.map((row, idx) => (
      <div
        key={idx}
        className="flex justify-between items-center py-1.5"
        style={{ borderBottom: idx < box.rows.length - 1 ? `1px solid ${COLORS.panelBorder}` : 'none' }}
      >
        <span className="text-[11px]" style={{ color: '#999' }}>
          {row.condition}
        </span>
        <span
          className="text-[10px] font-semibold px-2 py-0.5 rounded"
          style={{
            backgroundColor: COLORS.augmentChoices[row.choice].bg,
            color: COLORS.augmentChoices[row.choice].text,
          }}
        >
          {row.choice.charAt(0).toUpperCase() + row.choice.slice(1)}
        </span>
      </div>
    ))}
  </div>
);

const PersonalBoxComponent: React.FC<{ box: PersonalBox }> = ({ box }) => (
  <div
    className="rounded-md p-3 mb-2.5"
    style={{
      background: 'linear-gradient(135deg, rgba(46, 204, 113, 0.1), rgba(39, 174, 96, 0.05))',
      border: '1px solid rgba(46, 204, 113, 0.3)',
    }}
  >
    <div
      className="text-[11px] font-semibold mb-2 flex items-center gap-1.5"
      style={{ color: '#2ecc71' }}
    >
      {box.title}
    </div>
    {box.stats.map((stat, idx) => (
      <div key={idx} className="flex justify-between text-[11px] py-1">
        <span style={{ color: '#999' }}>{stat.label}</span>
        <span className="font-semibold" style={{ color: stat.isBad ? '#e74c3c' : '#2ecc71' }}>
          {stat.value}
        </span>
      </div>
    ))}
  </div>
);

const WarningBoxComponent: React.FC<{ box: WarningBox }> = ({ box }) => (
  <div
    className="rounded-md p-3 mb-2.5"
    style={{
      background: 'linear-gradient(135deg, rgba(231, 76, 60, 0.1), rgba(192, 57, 43, 0.05))',
      border: '1px solid rgba(231, 76, 60, 0.3)',
    }}
  >
    <div
      className="text-[11px] font-semibold mb-2 flex items-center gap-1.5"
      style={{ color: '#e74c3c' }}
    >
      {box.title}
    </div>
    {box.items.map((item, idx) => (
      <div
        key={idx}
        className="text-[11px] py-1 flex items-center gap-1.5"
        style={{ color: '#ccc' }}
      >
        <span style={{ color: '#e74c3c', fontSize: '10px', fontWeight: 'bold' }}>✕</span>
        {item}
      </div>
    ))}
  </div>
);

const CheckpointRow: React.FC<{ checkpoint: Checkpoint }> = ({ checkpoint }) => (
  <div
    className="flex items-center gap-2.5 px-2.5 py-2 rounded-md mb-1.5"
    style={{ backgroundColor: COLORS.sectionHover }}
  >
    <span className="text-[11px] font-bold min-w-[32px]" style={{ color: COLORS.gold }}>
      {checkpoint.stage}
    </span>
    <span className="text-xs font-semibold text-white">{checkpoint.target}</span>
    <span className="text-[10px] ml-auto" style={{ color: '#666' }}>
      {checkpoint.note}
    </span>
  </div>
);

const StageSectionComponent: React.FC<{
  section: StageSection;
  isExpanded: boolean;
  onToggle: () => void;
}> = ({ section, isExpanded, onToggle }) => (
  <div
    className="rounded-md overflow-hidden"
    style={{
      backgroundColor: COLORS.sectionBg,
      border: `1px solid ${section.isActive ? COLORS.gold : COLORS.panelBorder}`,
      boxShadow: section.isActive ? `0 0 8px rgba(201, 160, 51, 0.3)` : 'none',
    }}
  >
    {/* Header */}
    <div
      className="flex items-center justify-between px-3 py-2.5 cursor-pointer transition-colors duration-200"
      style={{ backgroundColor: isExpanded ? COLORS.sectionHover : 'transparent' }}
      onClick={onToggle}
      onMouseEnter={(e) => {
        if (!isExpanded) e.currentTarget.style.backgroundColor = COLORS.sectionHover;
      }}
      onMouseLeave={(e) => {
        if (!isExpanded) e.currentTarget.style.backgroundColor = 'transparent';
      }}
    >
      <div className="flex items-center gap-2">
        <span
          className="text-[11px] font-bold px-2 py-1 rounded text-center min-w-[24px]"
          style={{
            background: section.isActive
              ? `linear-gradient(135deg, ${COLORS.gold}, ${COLORS.goldDark})`
              : COLORS.badgeBg,
            color: '#fff',
          }}
        >
          {section.badge}
        </span>
        <span
          className="text-[13px] font-semibold"
          style={{ color: section.isActive ? COLORS.gold : '#fff' }}
        >
          {section.name}
        </span>
      </div>
      <span
        className="text-[10px] transition-transform duration-300"
        style={{
          color: '#666',
          transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
        }}
      >
        ▼
      </span>
    </div>

    {/* Content */}
    <div
      className="overflow-hidden transition-all duration-300"
      style={{ maxHeight: isExpanded ? '800px' : '0' }}
    >
      <div className="px-3 pb-3">
        {section.personalBox && <PersonalBoxComponent box={section.personalBox} />}
        {section.warningBox && <WarningBoxComponent box={section.warningBox} />}
        {section.tips?.map((tip, idx) => <TipCard key={idx} tip={tip} />)}
        {section.checkpoints?.map((cp, idx) => <CheckpointRow key={idx} checkpoint={cp} />)}
        {section.augmentBox && <AugmentBoxComponent box={section.augmentBox} />}
      </div>
    </div>
  </div>
);

// Main component
interface CoachingPanelProps {
  className?: string;
}

const CoachingPanel: React.FC<CoachingPanelProps> = ({ className }) => {
  // Default to Stage 3 (Mid Game) expanded since it's marked as active
  const [expandedSection, setExpandedSection] = useState<string | null>('stage-3');

  const handleToggle = (sectionId: string) => {
    setExpandedSection((prev) => (prev === sectionId ? null : sectionId));
  };

  return (
    <div
      className={`w-[280px] rounded-lg overflow-hidden ${className ?? ''}`}
      style={{
        backgroundColor: COLORS.panelBg,
        border: `1px solid ${COLORS.panelBorder}`,
      }}
    >
      {/* Header */}
      <div
        className="py-3 px-4 text-center"
        style={{
          background: `linear-gradient(180deg, ${COLORS.gold} 0%, ${COLORS.goldDark} 100%)`,
        }}
      >
        <h2 className="text-white text-base font-semibold tracking-wide">Game Coach</h2>
        <p className="text-[10px] mt-0.5" style={{ color: 'rgba(255,255,255,0.7)' }}>
          Tailored to your playstyle
        </p>
      </div>

      {/* Stages container */}
      <div className="p-2 flex flex-col gap-1.5">
        {STAGE_SECTIONS.map((section) => (
          <StageSectionComponent
            key={section.id}
            section={section}
            isExpanded={expandedSection === section.id}
            onToggle={() => handleToggle(section.id)}
          />
        ))}
      </div>
    </div>
  );
};

export default CoachingPanel;
