import React from 'react';

// Types
export type ChampionCost = 1 | 2 | 3 | 4 | 5;

export interface UnitItem {
  name: string;
  imageUrl: string;
}

export interface BoardUnit {
  id: string;
  name: string;
  cost: ChampionCost;
  imageUrl: string;
  stars: 1 | 2 | 3;
  items: UnitItem[];
  isLocked?: boolean;
}

// Cost border colors matching TFT
const COST_COLORS: Record<ChampionCost, string> = {
  1: '#344049', // Grey
  2: '#1C964D', // Green
  3: '#2D72B3', // Blue
  4: '#C40C93', // Purple
  5: '#D88810', // Gold/Orange
};

interface HexUnitProps {
  unit?: BoardUnit;
  size?: 'normal' | 'small';
}

const HexUnit: React.FC<HexUnitProps> = ({ unit, size = 'normal' }) => {
  const isSmall = size === 'small';

  // Dimensions based on size
  const hexWidth = isSmall ? 70 : 93;
  const hexHeight = isSmall ? 81 : 108;
  const portraitWidth = isSmall ? 80 : 106;
  const portraitHeight = isSmall ? 92 : 123;
  const itemSize = isSmall ? 16 : 22;
  const starSize = isSmall ? 10 : 12;
  const nameSize = isSmall ? 9 : 11;

  // Empty hex
  if (!unit) {
    return (
      <div
        className="relative"
        style={{ width: hexWidth, height: hexHeight }}
      >
        <svg
          width={hexWidth}
          height={hexHeight}
          viewBox="0 0 93 108"
          className="absolute inset-0"
        >
          <path
            d="M46.5 0 L93 27 V81 L46.5 108 L0 81 V27 Z"
            fill="rgba(30,30,40,0.5)"
            stroke="#333"
            strokeWidth="1"
          />
        </svg>
      </div>
    );
  }

  const borderColor = COST_COLORS[unit.cost];

  return (
    <div
      className="relative"
      style={{ width: hexWidth, height: hexHeight }}
    >
      {/* Hex frame with cost-colored border */}
      <svg
        width={hexWidth}
        height={hexHeight}
        viewBox="0 0 93 108"
        className="absolute inset-0"
      >
        <defs>
          <filter id={`glow-${unit.id}`}>
            <feDropShadow
              dx="0"
              dy="0"
              stdDeviation="2"
              floodColor={borderColor}
              floodOpacity="0.6"
            />
          </filter>
          <clipPath id={`hex-clip-${unit.id}`}>
            <path d="M46.5 0 L93 27 V81 L46.5 108 L0 81 V27 Z" />
          </clipPath>
        </defs>
        <path
          d="M46.5 0 L93 27 V81 L46.5 108 L0 81 V27 Z"
          fill="#1a1a2e"
          stroke={borderColor}
          strokeWidth="5"
          filter={`url(#glow-${unit.id})`}
        />
      </svg>

      {/* Champion portrait - centered and clipped to hex */}
      <div
        className="absolute flex items-center justify-center overflow-hidden"
        style={{
          width: portraitWidth,
          height: portraitHeight,
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          clipPath: 'polygon(50% 0%, 93.5% 25%, 93.5% 75%, 50% 100%, 6.5% 75%, 6.5% 25%)',
        }}
      >
        <img
          src={unit.imageUrl}
          alt={unit.name}
          className="w-full h-full object-cover"
          style={{
            // Slight zoom to fill hex better and crop edges
            transform: 'scale(1.15)',
          }}
        />
      </div>

      {/* Items at top */}
      {unit.items.length > 0 && (
        <div
          className="absolute flex gap-0.5 z-10"
          style={{
            top: isSmall ? 6 : 8,
            left: '50%',
            transform: 'translateX(-50%)',
          }}
        >
          {unit.items.slice(0, 3).map((item, idx) => (
            <div
              key={idx}
              className="rounded-sm overflow-hidden"
              style={{
                width: itemSize,
                height: itemSize,
                backgroundColor: 'rgba(0,0,0,0.5)',
                border: '1px solid rgba(255,255,255,0.2)',
              }}
            >
              <img
                src={item.imageUrl}
                alt={item.name}
                className="w-full h-full object-contain"
              />
            </div>
          ))}
        </div>
      )}

      {/* Stars below items */}
      <div
        className="absolute flex gap-px z-10"
        style={{
          top: isSmall ? 24 : 32,
          left: '50%',
          transform: 'translateX(-50%)',
        }}
      >
        {Array.from({ length: unit.stars }).map((_, idx) => (
          <span
            key={idx}
            style={{
              fontSize: starSize,
              color: '#ffd700',
              textShadow: '0 0 4px rgba(0,0,0,1), 1px 1px 0 #000',
            }}
          >
            ★
          </span>
        ))}
      </div>

      {/* Champion name at bottom */}
      <div
        className="absolute z-10 whitespace-nowrap font-semibold text-white"
        style={{
          bottom: isSmall ? 14 : 18,
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: nameSize,
          textShadow: '1px 1px 0 #000, -1px 1px 0 #000, 1px -1px 0 #000, -1px -1px 0 #000, 0 2px 3px rgba(0,0,0,0.8)',
        }}
      >
        {unit.name}
      </div>

      {/* Lock icon if locked */}
      {unit.isLocked && (
        <div
          className="absolute flex items-center justify-center rounded-sm z-10"
          style={{
            left: isSmall ? 9 : 12,
            top: '50%',
            transform: 'translateY(-50%)',
            width: isSmall ? 12 : 16,
            height: isSmall ? 12 : 16,
            backgroundColor: 'rgba(192,192,192,0.9)',
            fontSize: isSmall ? 8 : 10,
          }}
        >
          🔒
        </div>
      )}
    </div>
  );
};

export default HexUnit;
