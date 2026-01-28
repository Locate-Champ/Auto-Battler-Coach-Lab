import HexUnit from './HexUnit'

function HexBoard({ units = [], title = "Your Board" }) {
  // Create 4x7 grid (matching TFTFlows layout)
  const rows = 4
  const cols = 7

  // Find unit at position
  const getUnit = (row, col) => {
    return units.find(u => u.row === row && u.col === col)
  }

  // SVG hexagon path for empty slots
  const hexPath = "M50 0 L93.3 25 L93.3 75 L50 100 L6.7 75 L6.7 25 Z"

  return (
    <div className="flex flex-col items-center p-4 bg-[#1a1a2e] rounded-lg">
      {title && (
        <h3
          className="text-sm font-bold text-white mb-3 tracking-wide uppercase"
          style={{
            textShadow: '1px 1px 0 #000, -1px -1px 0 #000, 1px -1px 0 #000, -1px 1px 0 #000'
          }}
        >
          {title}
        </h3>
      )}
      <div className="flex flex-col items-center">
        {Array.from({ length: rows }).map((_, rowIndex) => (
          <div
            key={rowIndex}
            className="flex"
            style={{
              // Alternate row offset: 36px (half hex width)
              marginLeft: rowIndex % 2 === 1 ? '36px' : '0',
              // Vertical overlap between rows
              marginTop: rowIndex > 0 ? '-20px' : '0',
            }}
          >
            {Array.from({ length: cols }).map((_, colIndex) => {
              const unit = getUnit(rowIndex, colIndex)
              return (
                <div key={`${rowIndex}-${colIndex}`} className="w-[72px]">
                  {unit ? (
                    <HexUnit unit={unit} />
                  ) : (
                    <EmptyHex hexPath={hexPath} />
                  )}
                </div>
              )
            })}
          </div>
        ))}
      </div>
    </div>
  )
}

function EmptyHex({ hexPath }) {
  return (
    <div className="w-[72px] h-[100px] flex flex-col items-center">
      {/* Spacer for items area */}
      <div className="h-6" />

      {/* Empty hexagon */}
      <div className="relative w-[66px] h-[76px]">
        <svg
          className="absolute inset-0 w-full h-full opacity-30 hover:opacity-50 transition-opacity cursor-pointer"
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
        >
          <path
            d={hexPath}
            fill="#1f2937"
            stroke="#374151"
            strokeWidth="2"
          />
        </svg>
      </div>
    </div>
  )
}

export default HexBoard
