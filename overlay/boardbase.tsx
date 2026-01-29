import React from 'react';

// Hexagon component for reusability
interface HexagonProps {
  left: number;
  top: number;
  id: string;
}

const Hexagon: React.FC<HexagonProps> = ({ left, top, id }) => (
  <div 
    data-svg-wrapper 
    data-layer="Vector" 
    className="Vector absolute"
    style={{ left: `${left}px`, top: `${top}px` }}
  >
    <svg 
      width="95" 
      height="109" 
      viewBox="0 0 95 109" 
      fill="none" 
      xmlns="http://www.w3.org/2000/svg"
    >
      <path 
        d="M47.0781 0.6203L93.619 27.4915V81.2339L47.0781 108.105L0.537231 81.2339V27.4915L47.0781 0.6203Z" 
        fill="#3a5a7c"
        stroke="black" 
        strokeWidth="1.07439"
      />
    </svg>
  </div>
);

const BoardBase: React.FC = () => {
  // 7x4 hexagonal grid layout
  // Row 1: 7 hexagons starting at y=7.53
  // Row 2: 7 hexagons starting at y=115.02 (offset by ~53px horizontally)
  // Row 3: 7 hexagons starting at y=222.50
  // Row 4: 7 hexagons starting at y=329.99 (offset by ~53px horizontally)
  
  const hexWidth = 105.98; // horizontal spacing between hexagons
  const rowHeight = 107.49; // vertical spacing between rows
  const offsetX = 52.99; // horizontal offset for alternating rows
  
  const rows = [
    { y: 7.53, startX: 2.69, offset: false },
    { y: 115.02, startX: 55.68, offset: true },
    { y: 222.50, startX: 2.69, offset: false },
    { y: 329.99, startX: 55.68, offset: true },
  ];

  const hexagons: { left: number; top: number; id: string }[] = [];
  
  rows.forEach((row, rowIndex) => {
    for (let col = 0; col < 7; col++) {
      hexagons.push({
        left: row.startX + (col * hexWidth),
        top: row.y,
        id: `hex-${rowIndex}-${col}`,
      });
    }
  });

  return (
    <div 
      data-layer="base board design" 
      className="BaseBoardDesign relative bg-neutral-700 min-h-screen"
    >
      <div 
        data-layer="Frame" 
        className="Frame absolute"
        style={{ 
          width: '787.33px', 
          height: '450px', 
          left: '100px', 
          top: '100px' 
        }}
      >
        {hexagons.map((hex) => (
          <Hexagon 
            key={hex.id} 
            left={hex.left} 
            top={hex.top} 
            id={hex.id} 
          />
        ))}
      </div>
    </div>
  );
};

export default BoardBase;
