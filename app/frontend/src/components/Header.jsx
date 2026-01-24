function Header({ isLive }) {
  return (
    <header className="h-14 px-4 flex items-center justify-between border-b border-gray-800">
      <div>
        <h1 className="text-xl font-bold text-[#00d4ff]">TFT Coach Companion</h1>
        <p className="text-xs text-gray-500">Set 16.2 &bull; Based on 163 games</p>
      </div>
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${isLive ? 'bg-green-500 status-pulse' : 'bg-gray-500'}`}
        />
        <span className="text-xs text-gray-400">
          {isLive ? 'Live • 3s poll' : 'Offline'}
        </span>
      </div>
    </header>
  )
}

export default Header
