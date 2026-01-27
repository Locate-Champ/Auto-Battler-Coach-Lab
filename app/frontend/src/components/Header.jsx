function Header({ isLive }) {
  return (
    <header className="h-14 px-4 flex items-center justify-between border-b border-[#1f2937] bg-[#030712]">
      <div>
        <h1 className="text-xl font-bold text-[#00d4ff]">TFT Coach Companion</h1>
        <p className="text-xs text-[#6b7280]">Set 16.2 • Based on 163 games</p>
      </div>
      <div className="flex items-center gap-2">
        <div
          className={`w-2 h-2 rounded-full ${isLive ? 'bg-[#22c55e] status-pulse' : 'bg-[#6b7280]'}`}
        />
        <span className="text-xs text-[#9ca3af]">
          {isLive ? 'Live • 3s poll' : 'Offline'}
        </span>
      </div>
    </header>
  )
}

export default Header
