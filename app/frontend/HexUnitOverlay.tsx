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

// Image helpers
const getChampionImage = (name: string): string => {
  return new URL(`./images/champion images/${name}.png`, import.meta.url).href;
};

const getItemImage = (imageFile: string): string => {
  return new URL(`./images/craftable items images/${imageFile}`, import.meta.url).href;
};

interface HexUnitOverlayProps {
  unit: BoardUnit;
  isRotated?: boolean; // True when on opponent board (rotated 180deg)
}

const HexUnitOverlay: React.FC<HexUnitOverlayProps> = ({ unit, isRotated = false }) => {
  const hexWidth = 95;
  const hexHeight = 109;
  const borderColor = COST_COLORS[unit.cost];

  // Counter-rotation to keep items/stars/name right-side up when board is rotated
  const counterRotate = isRotated ? 'rotate(180deg)' : 'none';

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
          style={{ transform: isRotated ? 'scale(1.1) rotate(180deg)' : 'scale(1.1)' }}
        />
      </div>

      {/* Items bar at bottom - wrapper for centering, inner for counter-rotation */}
      {unit.items.length > 0 && (
        <div
          className="absolute z-20 w-full flex justify-center"
          style={isRotated ? { top: 6 } : { bottom: 6 }}
        >
          <div className="flex gap-0.5" style={{ transform: counterRotate }}>
            {unit.items.slice(0, 3).map((item, idx) => (
              <div
                key={idx}
                className="rounded-sm overflow-hidden"
                style={{
                  width: 20,
                  height: 20,
                  backgroundColor: 'rgba(0,0,0,0.7)',
                  border: '1px solid rgba(255,255,255,0.4)',
                  boxShadow: '0 2px 4px rgba(0,0,0,0.8), 0 1px 2px rgba(0,0,0,0.6)',
                }}
              >
                <img
                  src={getItemImage(item.imageFile)}
                  alt={item.name}
                  className="w-full h-full object-contain"
                />
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stars - wrapper for centering, inner for counter-rotation */}
      <div
        className="absolute z-20 w-full flex justify-center"
        style={isRotated ? { bottom: 18 } : { top: 18 }}
      >
        <div className="flex gap-px" style={{ transform: counterRotate }}>
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
      </div>

      {/* Champion name - wrapper for centering, inner for counter-rotation */}
      <div
        className="absolute z-20 w-full flex justify-center"
        style={isRotated ? { top: 28 } : { bottom: 28 }}
      >
        <div
          className="whitespace-nowrap font-semibold text-white text-center"
          style={{
            transform: counterRotate,
            fontSize: 12,
            textShadow: '1px 1px 0 #000, -1px 1px 0 #000, 1px -1px 0 #000, -1px -1px 0 #000, 0 2px 4px rgba(0,0,0,0.9)',
          }}
        >
          {unit.name}
        </div>
      </div>

      {/* Lock icon if locked */}
      {unit.isLocked && (
        <div
          className="absolute z-20 h-full flex items-center"
          style={isRotated ? { right: 8 } : { left: 8 }}
        >
          <div
            className="flex items-center justify-center rounded-sm"
            style={{
              transform: counterRotate,
              width: 14,
              height: 14,
              backgroundColor: 'rgba(192,192,192,0.9)',
              fontSize: 8,
            }}
          >
            🔒
          </div>
        </div>
      )}
    </div>
  );
};

export default HexUnitOverlay;
