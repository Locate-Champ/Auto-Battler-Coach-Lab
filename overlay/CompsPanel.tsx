import React, { useState } from 'react';
import MetaCompCard from './MetaCompCard';
import { useMetaComps } from './hooks/useMetaComps';

interface CompsPanelProps {
  className?: string;
}

const CompsPanel: React.FC<CompsPanelProps> = ({ className }) => {
  const { data, loading, error, refetch } = useMetaComps({ limit: 15 });
  const [sortBy, setSortBy] = useState<'top4' | 'winRate' | 'games'>('top4');

  // Sort comps based on selected criteria
  const sortedComps = data?.comps.slice().sort((a, b) => {
    if (sortBy === 'top4') return b.top4_rate - a.top4_rate;
    if (sortBy === 'winRate') return b.win_rate - a.win_rate;
    if (sortBy === 'games') return b.games_played - a.games_played;
    return 0;
  });

  return (
    <div
      className={`w-[340px] rounded-lg overflow-hidden ${className ?? ''}`}
      style={{
        backgroundColor: '#252538',
        border: '1px solid #3a3a4f',
      }}
    >
      {/* Header */}
      <div
        className="py-3 px-4"
        style={{
          background: 'linear-gradient(180deg, #c9a033 0%, #8b6914 100%)',
        }}
      >
        <div className="flex justify-between items-center">
          <h2 className="text-white text-base font-semibold tracking-wide">Meta Comps</h2>
          {data && (
            <span className="text-white/80 text-xs">
              Patch {data.patch}
            </span>
          )}
        </div>
      </div>

      {/* Sort controls */}
      {data && (
        <div className="px-3 py-2 flex gap-2 border-b border-[#3a3a4f]">
          <button
            className={`px-2 py-1 rounded text-xs ${sortBy === 'top4' ? 'bg-[#3a3a4f] text-white' : 'text-[#888]'}`}
            onClick={() => setSortBy('top4')}
          >
            Top 4%
          </button>
          <button
            className={`px-2 py-1 rounded text-xs ${sortBy === 'winRate' ? 'bg-[#3a3a4f] text-white' : 'text-[#888]'}`}
            onClick={() => setSortBy('winRate')}
          >
            Win%
          </button>
          <button
            className={`px-2 py-1 rounded text-xs ${sortBy === 'games' ? 'bg-[#3a3a4f] text-white' : 'text-[#888]'}`}
            onClick={() => setSortBy('games')}
          >
            Games
          </button>
        </div>
      )}

      {/* Content */}
      <div
        className="p-2 flex flex-col gap-2 overflow-y-auto"
        style={{ maxHeight: '650px' }}
      >
        {/* Loading state */}
        {loading && (
          <div className="text-xs text-[#6b7280] text-center py-8">
            Loading meta data...
          </div>
        )}

        {/* Error state */}
        {error && !loading && (
          <div className="text-center py-4">
            <div className="text-xs text-[#ff6b6b] mb-2">{error}</div>
            <button
              className="px-3 py-1 rounded text-xs bg-[#3a3a4f] text-white hover:bg-[#4a4a5f]"
              onClick={() => refetch()}
            >
              Retry
            </button>
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && (!data || data.comps.length === 0) && (
          <div className="text-xs text-[#6b7280] text-center py-8">
            No meta data available.
            <br />
            <span className="text-[10px]">Run fetch_meta_data.py to load data.</span>
          </div>
        )}

        {/* Comp cards */}
        {!loading && !error && sortedComps && sortedComps.map((comp, index) => (
          <MetaCompCard
            key={`${comp.units.join('-')}-${index}`}
            comp={comp}
            rank={index + 1}
            isHighlighted={index === 0}
          />
        ))}
      </div>

      {/* Footer with total games */}
      {data && (
        <div
          className="px-3 py-2 text-xs text-[#6b7280] text-center border-t border-[#3a3a4f]"
        >
          Data from {(data.total_games / 1000000).toFixed(1)}M games
          {data.last_updated && (
            <span className="ml-2">
              | Updated: {new Date(data.last_updated).toLocaleDateString()}
            </span>
          )}
        </div>
      )}
    </div>
  );
};

export default CompsPanel;
