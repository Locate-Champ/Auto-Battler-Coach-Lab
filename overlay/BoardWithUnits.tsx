import React from 'react';
import BoardBase from './boardbase';
import HexUnitOverlay, { PositionedUnit } from './HexUnitOverlay';

// EXACT positioning from boardbase.tsx - DO NOT CHANGE
const HEX_POSITIONS = {
  hexWidth: 105.98,
  rows: [
    { y: 7.53, startX: 2.69 },    // Row 0
    { y: 115.02, startX: 55.68 }, // Row 1 (offset)
    { y: 222.50, startX: 2.69 },  // Row 2
    { y: 329.99, startX: 55.68 }, // Row 3 (offset)
  ],
};

const getHexPosition = (row: number, col: number): { left: number; top: number } => {
  const rowConfig = HEX_POSITIONS.rows[row];
  return {
    left: rowConfig.startX + col * HEX_POSITIONS.hexWidth,
    top: rowConfig.y,
  };
};

interface BoardWithUnitsProps {
  units: PositionedUnit[];
}

const BoardWithUnits: React.FC<BoardWithUnitsProps> = ({ units }) => {
  return (
    <div
      className="relative"
      style={{
        width: 787,
        height: 450,
      }}
    >
      {/* Base hex grid (unchanged) */}
      <BoardBase />

      {/* Unit overlay layer */}
      <div
        className="absolute inset-0"
        style={{ pointerEvents: 'none' }}
      >
        {units.map((unit) => {
          const pos = getHexPosition(unit.position.row, unit.position.col);
          return (
            <div
              key={unit.id}
              className="absolute"
              style={{
                left: pos.left,
                top: pos.top,
              }}
            >
              <HexUnitOverlay unit={unit} />
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default BoardWithUnits;
