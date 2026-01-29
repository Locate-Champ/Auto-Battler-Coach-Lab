import React from 'react';
import HexUnit, { BoardUnit } from './HexUnit';

// Board position type: row (0-3) and column (0-6)
export interface BoardPosition {
  row: number;
  col: number;
}

// Unit with position on board
export interface PositionedUnit extends BoardUnit {
  position: BoardPosition;
}

interface GameBoardProps {
  units: PositionedUnit[];
  mirrored?: boolean; // For opponent board - flips vertically
  size?: 'normal' | 'small';
  showEmptyHexes?: boolean;
}

const GameBoard: React.FC<GameBoardProps> = ({
  units,
  mirrored = false,
  size = 'normal',
  showEmptyHexes = true,
}) => {
  const isSmall = size === 'small';

  // Board dimensions
  const hexWidth = isSmall ? 70 : 93;
  const hexHeight = isSmall ? 81 : 108;
  const hexSpacingX = isSmall ? 80 : 106; // Horizontal spacing between hex centers
  const hexSpacingY = isSmall ? 60 : 80; // Vertical spacing between rows
  const offsetX = hexSpacingX / 2; // Offset for alternating rows

  // Board container dimensions
  const boardWidth = isSmall ? 590 : 787;
  const boardHeight = isSmall ? 338 : 450;

  // Calculate hex positions for 7x4 grid
  const getHexPosition = (row: number, col: number): { left: number; top: number } => {
    const isOffsetRow = row % 2 === 1;
    const baseX = isSmall ? 2 : 2.69;
    const baseY = isSmall ? 5.6 : 7.53;

    // If mirrored, flip row positions (3 becomes 0, 2 becomes 1, etc.)
    const actualRow = mirrored ? 3 - row : row;

    return {
      left: baseX + col * hexSpacingX + (isOffsetRow ? offsetX : 0),
      top: baseY + actualRow * hexSpacingY,
    };
  };

  // Create unit lookup by position
  const unitMap = new Map<string, PositionedUnit>();
  units.forEach((unit) => {
    const key = `${unit.position.row}-${unit.position.col}`;
    unitMap.set(key, unit);
  });

  // Generate all hex positions
  const hexPositions: { row: number; col: number; left: number; top: number }[] = [];
  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 7; col++) {
      const pos = getHexPosition(row, col);
      hexPositions.push({ row, col, ...pos });
    }
  }

  return (
    <div
      className="relative"
      style={{
        width: boardWidth,
        height: boardHeight,
        backgroundColor: '#404040',
        transform: mirrored ? 'scaleY(-1)' : 'none',
      }}
    >
      {hexPositions.map(({ row, col, left, top }) => {
        const key = `${row}-${col}`;
        const unit = unitMap.get(key);

        // Skip empty hexes if not showing them
        if (!showEmptyHexes && !unit) {
          return null;
        }

        return (
          <div
            key={key}
            className="absolute"
            style={{
              left,
              top,
              // If board is mirrored, flip the unit back right-side up
              transform: mirrored ? 'scaleY(-1)' : 'none',
            }}
          >
            <HexUnit unit={unit} size={size} />
          </div>
        );
      })}
    </div>
  );
};

export default GameBoard;

// Sample data for testing
export const SAMPLE_PLAYER_UNITS: PositionedUnit[] = [
  {
    id: 'sejuani-1',
    name: 'Sejuani',
    cost: 3,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_sejuani_square.tft_set16.png',
    stars: 2,
    items: [
      { name: "Warmog's", imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/warmogsarmor.png' },
      { name: 'Gargoyle', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/gargoylestoneplate.png' },
    ],
    position: { row: 0, col: 2 },
  },
  {
    id: 'anivia-1',
    name: 'Anivia',
    cost: 1,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_anivia_square.tft_set16.png',
    stars: 1,
    items: [],
    position: { row: 0, col: 3 },
  },
  {
    id: 'garen-1',
    name: 'Garen',
    cost: 4,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_garen_square.tft_set16.png',
    stars: 2,
    items: [
      { name: 'Titan', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/titanichydra.png' },
    ],
    position: { row: 1, col: 2 },
  },
  {
    id: 'sona-1',
    name: 'Sona',
    cost: 1,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_sona_square.tft_set16.png',
    stars: 2,
    items: [],
    position: { row: 1, col: 3 },
  },
  {
    id: 'kindred-1',
    name: 'Kindred',
    cost: 5,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_kindred_square.tft_set16.png',
    stars: 2,
    items: [
      { name: 'IE', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/infinityedge.png' },
      { name: 'LW', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/lastwhisper.png' },
      { name: 'GS', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/giantslayer.png' },
    ],
    position: { row: 2, col: 1 },
  },
  {
    id: 'diana-1',
    name: 'Diana',
    cost: 4,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_diana_square.tft_set16.png',
    stars: 2,
    items: [
      { name: 'BB', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/bluebuff.png' },
    ],
    position: { row: 2, col: 2 },
  },
  {
    id: 'ornn-1',
    name: 'Ornn',
    cost: 5,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_ornn_square.tft_set16.png',
    stars: 1,
    items: [
      { name: 'Sunfire', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/sunfirecape.png' },
      { name: "Warmog's", imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/warmogsarmor.png' },
    ],
    position: { row: 2, col: 3 },
  },
];

export const SAMPLE_OPPONENT_UNITS: PositionedUnit[] = [
  {
    id: 'opp-fiddle-1',
    name: 'Fiddlesticks',
    cost: 5,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_fiddlesticks_square.tft_set16.png',
    stars: 2,
    items: [
      { name: 'Morello', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/morellonomicon.png' },
      { name: 'JG', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/jeweledgauntlet.png' },
      { name: 'BB', imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/bluebuff.png' },
    ],
    position: { row: 3, col: 3 },
  },
  {
    id: 'opp-braum-1',
    name: 'Braum',
    cost: 4,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_braum_square.tft_set16.png',
    stars: 2,
    items: [
      { name: "Warmog's", imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/items/tileIcon/warmogsarmor.png' },
    ],
    position: { row: 3, col: 2 },
  },
  {
    id: 'opp-zilean-1',
    name: 'Zilean',
    cost: 5,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_zilean_square.tft_set16.png',
    stars: 1,
    items: [],
    position: { row: 3, col: 4 },
  },
  {
    id: 'opp-leona-1',
    name: 'Leona',
    cost: 3,
    imageUrl: 'https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_leona_square.tft_set16.png',
    stars: 2,
    items: [],
    position: { row: 2, col: 3 },
  },
];
