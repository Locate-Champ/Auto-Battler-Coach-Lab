import HexUnit from './HexUnit'

function HexBoard({ units }) {
  // Create 4x7 grid
  const rows = 4
  const cols = 7

  // Find unit at position
  const getUnit = (row, col) => {
    return units.find(u => u.row === row && u.col === col)
  }

  return (
    <div className="flex flex-col items-center py-2">
      {Array.from({ length: rows }).map((_, rowIndex) => (
        <div
          key={rowIndex}
          className="flex"
          style={{
            marginLeft: rowIndex % 2 === 1 ? '32px' : '0',
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
      <div className="w-14 h-12 hex-clip empty-hex transition-opacity cursor-pointer" />
    </div>
  )
}

export default HexBoard
