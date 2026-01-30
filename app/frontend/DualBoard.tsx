import React from 'react';
import BoardWithUnits from './BoardWithUnits';
import { PositionedUnit } from './HexUnitOverlay';

interface DualBoardProps {
  playerUnits: PositionedUnit[];
  opponentUnits: PositionedUnit[];
}

const DualBoard: React.FC<DualBoardProps> = ({ playerUnits, opponentUnits }) => {
  return (
    <div className="flex flex-col" style={{ width: 787 }}>
      {/* Opponent Board (rotated 180 degrees so front lines face each other) */}
      <BoardWithUnits units={opponentUnits} isRotated={true} />

      {/* Thin black line between boards */}
      <div
        className="w-full"
        style={{
          height: 1,
          backgroundColor: '#000',
        }}
      />

      {/* Player Board */}
      <BoardWithUnits units={playerUnits} isRotated={false} />
    </div>
  );
};

export default DualBoard;

// Sample data for testing
export const SAMPLE_PLAYER_UNITS: PositionedUnit[] = [
  {
    id: 'player-sejuani',
    name: 'Sejuani',
    cost: 3,
    stars: 2,
    items: [
      { name: "Warmog's Armor", imageFile: "Warmog's Armor.png" },
      { name: 'Gargoyle Stoneplate', imageFile: 'Gargoyle Stoneplate.png' },
    ],
    position: { row: 0, col: 2 },
  },
  {
    id: 'player-anivia',
    name: 'Anivia',
    cost: 1,
    stars: 1,
    items: [],
    position: { row: 0, col: 3 },
  },
  {
    id: 'player-garen',
    name: 'Garen',
    cost: 4,
    stars: 2,
    items: [
      { name: "Titan's Resolve", imageFile: "Titan's Resolve.png" },
    ],
    position: { row: 1, col: 2 },
  },
  {
    id: 'player-sona',
    name: 'Sona',
    cost: 1,
    stars: 2,
    items: [],
    position: { row: 1, col: 3 },
  },
  {
    id: 'player-kindred',
    name: 'Kindred',
    cost: 5,
    stars: 2,
    items: [
      { name: 'Infinity Edge', imageFile: 'Infinity Edge.png' },
      { name: 'Last Whisper', imageFile: 'Last Whisper.png' },
      { name: 'Giant Slayer', imageFile: 'Giant Slayer.png' },
    ],
    position: { row: 2, col: 1 },
  },
  {
    id: 'player-diana',
    name: 'Diana',
    cost: 4,
    stars: 2,
    items: [
      { name: 'Blue Buff', imageFile: 'Blue Buff.png' },
    ],
    position: { row: 2, col: 2 },
  },
  {
    id: 'player-ornn',
    name: 'Ornn',
    cost: 5,
    stars: 1,
    items: [
      { name: 'Sunfire Cape', imageFile: 'Sunfire Cape.png' },
      { name: "Warmog's Armor", imageFile: "Warmog's Armor.png" },
    ],
    position: { row: 2, col: 3 },
  },
];

export const SAMPLE_OPPONENT_UNITS: PositionedUnit[] = [
  {
    id: 'opp-fiddlesticks',
    name: 'Fiddlesticks',
    cost: 5,
    stars: 2,
    items: [
      { name: 'Morellonomicon', imageFile: 'Morellonomicon.png' },
      { name: 'Jeweled Gauntlet', imageFile: 'Jeweled Gauntlet.png' },
      { name: 'Blue Buff', imageFile: 'Blue Buff.png' },
    ],
    position: { row: 3, col: 3 },
  },
  {
    id: 'opp-braum',
    name: 'Braum',
    cost: 4,
    stars: 2,
    items: [
      { name: "Warmog's Armor", imageFile: "Warmog's Armor.png" },
    ],
    position: { row: 3, col: 2 },
  },
  {
    id: 'opp-zilean',
    name: 'Zilean',
    cost: 5,
    stars: 1,
    items: [],
    position: { row: 3, col: 4 },
  },
  {
    id: 'opp-leona',
    name: 'Leona',
    cost: 3,
    stars: 2,
    items: [],
    position: { row: 2, col: 3 },
  },
];
