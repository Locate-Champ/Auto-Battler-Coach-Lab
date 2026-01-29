import React from 'react';

// Types
export type ChampionCost = 1 | 2 | 3 | 4 | 5;

export interface UnitItem {
  name: string;
  imageFile: string;
}

export interface BoardUnit {
  id: string;
  name: string;
  cost: ChampionCost;
  stars: 1 | 2 | 3;
  items: UnitItem[];
  isLocked?: boolean;
}

export interface BoardPosition {
  row: number;
  col: number;
}

export interface PositionedUnit extends BoardUnit {
  position: BoardPosition;
}

// Cost border colors matching TFT
const COST_COLORS: Record<ChampionCost, string> = {
  1: '#344049', // Grey
  2: '#1C964D', // Green
  3: '#2D72B3', // Blue
  4: '#C40C93', // Purple
  5: '#D88810', // Gold/Orange
};

// Icon positioning from icon config.txt (converted to pixels for 95x109 hex)
const ICON_POSITIONS = {
  // Items at bottom (3 slots) - cx/cy are center positions
  bottomLeft:  { cx: 19.6, cy: 91.8, w: 21.5, h: 20.6 },
  bottomMid:   { cx: 45.5, cy: 92.3, w: 20.6, h: 21.6 },
  bottomRight: { cx: 71.0, cy: 92.3, w: 20.6, h: 21.6 },
};

// Helper to get item position by index
const getItemPosition = (index: number) => {
  const positions = [ICON_POSITIONS.bottomLeft, ICON_POSITIONS.bottomMid, ICON_POSITIONS.bottomRight];
  return positions[index];
};

// Image helpers
const getChampionImage = (name: string): string => {
  return new URL(`./images/champion images/${name}.png`, import.meta.url).href;
};

const getItemImage = (imageFile: string): string => {
  return new URL(`./images/craftable items images/${imageFile}`, import.meta.url).href;
};

interface HexUnitOverlayProps {
  unit: BoardUnit;
}

const HexUnitOverlay: React.FC<HexUnitOverlayProps> = ({ unit }) => {
  const hexWidth = 95;
  const hexHeight = 109;
  const borderColor = COST_COLORS[unit.cost];

  return (
    <div
      className="absolute"
      style={{
        width: hexWidth,
        height: hexHeight,
        pointerEvents: 'none',
      }}
    >
      {/* Cost-colored border glow overlay (SVG with no fill, just stroke) */}
      <svg
        width={hexWidth}
        height={hexHeight}
        viewBox="0 0 95 109"
        className="absolute inset-0 z-10"
        style={{ pointerEvents: 'none' }}
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
        </defs>
        <path
          d="M47.0781 0.6203L93.619 27.4915V81.2339L47.0781 108.105L0.537231 81.2339V27.4915L47.0781 0.6203Z"
          fill="none"
          stroke={borderColor}
          strokeWidth="4"
          filter={`url(#glow-${unit.id})`}
        />
      </svg>

      {/* Champion portrait - clipped to hex shape */}
      <div
        className="absolute overflow-hidden"
        style={{
          width: 99,
          height: 114,
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          clipPath: 'polygon(50% 0%, 93.5% 25%, 93.5% 75%, 50% 100%, 6.5% 75%, 6.5% 25%)',
        }}
      >
        <img
          src={getChampionImage(unit.name)}
          alt={unit.name}
          className="w-full h-full object-cover"
          style={{ transform: 'scale(1.1)' }}
        />
      </div>

      {/* Items at bottom */}
      {unit.items.slice(0, 3).map((item, idx) => {
        const pos = getItemPosition(idx);
        return (
          <div
            key={idx}
            className="absolute rounded-sm overflow-hidden z-20"
            style={{
              left: pos.cx - pos.w / 2,
              top: pos.cy - pos.h / 2,
              width: pos.w,
              height: pos.h,
              backgroundColor: 'rgba(0,0,0,0.6)',
              border: '1px solid rgba(255,255,255,0.3)',
            }}
          >
            <img
              src={getItemImage(item.imageFile)}
              alt={item.name}
              className="w-full h-full object-contain"
            />
          </div>
        );
      })}

      {/* Stars */}
      <div
        className="absolute flex gap-px z-20"
        style={{
          top: 18,
          left: '50%',
          transform: 'translateX(-50%)',
        }}
      >
        {Array.from({ length: unit.stars }).map((_, idx) => (
          <span
            key={idx}
            style={{
              fontSize: 12,
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
        className="absolute z-20 whitespace-nowrap font-semibold text-white text-center"
        style={{
          bottom: 28,
          left: '50%',
          transform: 'translateX(-50%)',
          fontSize: 10,
          textShadow: '1px 1px 0 #000, -1px 1px 0 #000, 1px -1px 0 #000, -1px -1px 0 #000, 0 2px 3px rgba(0,0,0,0.8)',
        }}
      >
        {unit.name}
      </div>

      {/* Lock icon if locked */}
      {unit.isLocked && (
        <div
          className="absolute flex items-center justify-center rounded-sm z-20"
          style={{
            left: 8,
            top: '50%',
            transform: 'translateY(-50%)',
            width: 14,
            height: 14,
            backgroundColor: 'rgba(192,192,192,0.9)',
            fontSize: 8,
          }}
        >
          🔒
        </div>
      )}
    </div>
  );
};

export default HexUnitOverlay;
