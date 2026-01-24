import HexUnit from './HexUnit'

function HexBoard({ units }) {
  // Create 4x7 grid (matching Figma spec)
  const rows = 4
  const cols = 7

  // Find unit at position
  const getUnit = (row, col) => {
    return units.find(u => u.row === row && u.col === col)
  }

  return (
    <div className="flex flex-col items-center py-4">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div
          key={rowIndex}
          className="flex"
          style={{
            // Alternate row offset: 32px (half hex width)
            marginLeft: rowIndex % 2 === 1 ? '32px' : '0',
            // Vertical overlap: -8px between rows
            marginTop: rowIndex > 0 ? '-8px' : '0',
          }}
        >
          {Array.from({ length: cols }).map((_, colIndex) => {
            const unit = getUnit(rowIndex, colIndex)
            return (
              <div key={`${rowIndex}-${colIndex}`} className="w-16">
                {unit ? (
                  <HexUnit unit={unit} />
                ) : (
                  <EmptyHex />
                )}
              </div>
            )
          })}
        </div>
      ))}
    </div>
  )
}

function EmptyHex() {
  return (
    <div className="w-16 h-[72px] flex items-center justify-center">
      <div
        className="w-14 h-12 hex-clip transition-opacity cursor-pointer hover:opacity-60"
        style={{
          background: 'linear-gradient(135deg, #1f2937, #111827)',
          border: '2px solid #374151',
          opacity: 0.4,
        }}
      />
    </div>
  )
}

export default HexBoard
