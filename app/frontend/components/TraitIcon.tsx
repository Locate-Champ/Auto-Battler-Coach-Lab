import React from 'react';
import { getTraitIcon, getTraitTierInfo, getTierColors, isTraitActive, type TraitTier } from '../utils/traitUtils';

interface TraitIconProps {
  name: string;
  count: number;
  size?: 'sm' | 'md' | 'lg';
  showCount?: boolean;
  showInactive?: boolean;
}

const SIZE_CLASSES = {
  sm: { container: 'w-6 h-6', icon: 'w-4 h-4', text: 'text-[8px]' },
  md: { container: 'w-8 h-8', icon: 'w-5 h-5', text: 'text-[10px]' },
  lg: { container: 'w-10 h-10', icon: 'w-6 h-6', text: 'text-xs' },
};

export const TraitIcon: React.FC<TraitIconProps> = ({
  name,
  count,
  size = 'sm',
  showCount = true,
  showInactive = false,
}) => {
  const isActive = isTraitActive(name, count);

  // Don't render inactive traits unless explicitly requested
  if (!isActive && !showInactive) {
    return null;
  }

  const tierInfo = getTraitTierInfo(name, count);
  const colors = getTierColors(tierInfo.tier);
  const iconUrl = getTraitIcon(name);
  const sizeClass = SIZE_CLASSES[size];

  // Build tooltip text
  const tooltipText = tierInfo.nextBreakpoint
    ? `${name} (${count}/${tierInfo.nextBreakpoint})`
    : `${name} (${count}) - Max`;

  return (
    <div
      className={`relative ${sizeClass.container} rounded flex items-center justify-center`}
      style={{
        backgroundColor: colors.bg,
        border: `2px solid ${colors.border}`,
      }}
      title={tooltipText}
    >
      {iconUrl ? (
        <img
          src={iconUrl}
          alt={name}
          className={`${sizeClass.icon} object-contain`}
          style={{ filter: tierInfo.tier === 'inactive' ? 'grayscale(100%) opacity(50%)' : 'none' }}
        />
      ) : (
        // Fallback: show first letter of trait name
        <span
          className={`${sizeClass.text} font-bold`}
          style={{ color: colors.text }}
        >
          {name.charAt(0)}
        </span>
      )}

      {/* Count badge */}
      {showCount && (
        <span
          className={`absolute -bottom-1 -right-1 ${sizeClass.text} font-bold rounded-full min-w-[14px] h-[14px] flex items-center justify-center`}
          style={{
            backgroundColor: '#1a1a2e',
            color: colors.text,
            border: `1px solid ${colors.border}`,
          }}
        >
          {count}
        </span>
      )}
    </div>
  );
};

interface TraitListProps {
  traits: Array<{ name: string; count: number }>;
  size?: 'sm' | 'md' | 'lg';
  maxTraits?: number;
  showInactive?: boolean;
}

export const TraitList: React.FC<TraitListProps> = ({
  traits,
  size = 'sm',
  maxTraits,
  showInactive = false,
}) => {
  // Filter to active traits unless showInactive is true
  const filteredTraits = showInactive
    ? traits
    : traits.filter(t => isTraitActive(t.name, t.count));

  // Sort by tier (gold > silver > bronze > unique) then by count descending
  const sortedTraits = [...filteredTraits].sort((a, b) => {
    const tierOrder: Record<TraitTier, number> = {
      prismatic: 0,
      gold: 1,
      silver: 2,
      unique: 3,
      bronze: 4,
      inactive: 5,
    };

    const tierA = getTraitTierInfo(a.name, a.count).tier;
    const tierB = getTraitTierInfo(b.name, b.count).tier;

    const tierDiff = tierOrder[tierA] - tierOrder[tierB];
    if (tierDiff !== 0) return tierDiff;

    return b.count - a.count;
  });

  // Apply max limit if specified
  const displayTraits = maxTraits ? sortedTraits.slice(0, maxTraits) : sortedTraits;

  return (
    <div className="flex flex-wrap gap-1">
      {displayTraits.map((trait) => (
        <TraitIcon
          key={trait.name}
          name={trait.name}
          count={trait.count}
          size={size}
          showInactive={showInactive}
        />
      ))}
    </div>
  );
};

export default TraitIcon;
