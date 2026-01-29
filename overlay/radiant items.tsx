import React from 'react';

const RADIANT_ITEMS = [
  { name: 'Radiant Adaptive Helm', file: 'Radiant Adaptive Helm.png' },
  { name: "Radiant Archangel's Staff", file: "Radiant Archangel's Staff.png" },
  { name: 'Radiant Bloodthirster', file: 'Radiant Bloodthirster.png' },
  { name: 'Radiant Blue Buff', file: 'Radiant Blue Buff.png' },
  { name: 'Radiant Bramble Vest', file: 'Radiant Bramble Vest.png' },
  { name: 'Radiant Crownguard', file: 'Radiant Crownguard.png' },
  { name: 'Radiant Deathblade', file: 'Radiant Deathblade.png' },
  { name: "Radiant Dragon's Claw", file: "Radiant Dragon's Claw.png" },
  { name: 'Radiant Edge of Night', file: 'Radiant Edge of Night.png' },
  { name: 'Radiant Evenshroud', file: 'Radiant Evenshroud.png' },
  { name: 'Radiant Gargoyle Stoneplate', file: 'Radiant Gargoyle Stoneplate.png' },
  { name: 'Radiant Giant Slayer', file: 'Radiant Giant Slayer.png' },
  { name: "Radiant Guinsoo's Rageblade", file: "Radiant Guinsoo's Rageblade.png" },
  { name: 'Radiant Hand of Justice', file: 'Radiant Hand of Justice.png' },
  { name: 'Radiant Hextech Gunblade', file: 'Radiant Hextech Gunblade.png' },
  { name: 'Radiant Infinity Edge', file: 'Radiant Infinity Edge.png' },
  { name: 'Radiant Ionic Spark', file: 'Radiant Ionic Spark.png' },
  { name: 'Radiant Jeweled Gauntlet', file: 'Radiant Jeweled Gauntlet.png' },
  { name: "Radiant Kraken's Fury", file: "Radiant Kraken's Fury.png" },
  { name: 'Radiant Last Whisper', file: 'Radiant Last Whisper.png' },
  { name: 'Radiant Morellonomicon', file: 'Radiant Morellonomicon.png' },
  { name: "Radiant Nashor's Tooth", file: "Radiant Nashor's Tooth.png" },
  { name: "Radiant Protector's Vow", file: "Radiant Protector's Vow.png" },
  { name: 'Radiant Quicksilver', file: 'Radiant Quicksilver.png' },
  { name: "Radiant Rabadon's Deathcap", file: "Radiant Rabadon's Deathcap.png" },
  { name: 'Radiant Red Buff', file: 'Radiant Red Buff.png' },
  { name: 'Radiant Spear of Shojin', file: 'Radiant Spear of Shojin.png' },
  { name: 'Radiant Spirit Visage', file: 'Radiant Spirit Visage.png' },
  { name: 'Radiant Steadfast Heart', file: 'Radiant Steadfast Heart.png' },
  { name: "Radiant Sterak's Gage", file: "Radiant Sterak's Gage.png" },
  { name: "Radiant Striker's Flail", file: "Radiant Striker's Flail.png" },
  { name: 'Radiant Sunfire Cape', file: 'Radiant Sunfire Cape.png' },
  { name: "Radiant Thief's Gloves", file: "Radiant Thief's Gloves.png" },
  { name: "Radiant Titan's Resolve", file: "Radiant Titan's Resolve.png" },
  { name: 'Radiant Void Staff', file: 'Radiant Void Staff.png' },
  { name: "Radiant Warmog's Armor", file: "Radiant Warmog's Armor.png" },
] as const;

export type RadiantItemName = (typeof RADIANT_ITEMS)[number]['name'];

export interface InventoryItem {
  name: string;
  count?: number;
  category?: string;
}

interface RadiantItemsProps {
  inventory?: Iterable<InventoryItem>;
  onItemClick?: (item: RadiantItemName) => void;
  className?: string;
}

const RadiantItems: React.FC<RadiantItemsProps> = ({ inventory, onItemClick, className }) => {
  const ownedItems = new Map<string, number>();

  if (inventory) {
    for (const item of inventory) {
      if (item.category && item.category !== 'radiant') continue;
      if (typeof item.count === 'number' && item.count <= 0) continue;
      ownedItems.set(item.name, item.count ?? 1);
    }
  }

  return (
    <div
      data-layer="Frame"
      className={`relative w-[491.99px] h-36 p-1 ${className ?? ''}`}
    >
      <div className="grid grid-cols-[repeat(12,32px)] gap-0 mx-auto">
        {RADIANT_ITEMS.map((item) => {
          const isOwned = ownedItems.has(item.name);
          const imageSrc = new URL(
            `./images/radiant items images/${item.file}`,
            import.meta.url,
          ).href;

          return (
            <button
              key={item.name}
              type="button"
              data-layer={item.name}
              title={item.name}
              aria-pressed={isOwned}
              onClick={onItemClick ? () => onItemClick(item.name) : undefined}
              className={[
                'h-8 w-8 rounded-[4px] transition',
                'ring-1 ring-transparent',
                isOwned
                  ? 'opacity-100 ring-2 ring-[#fab964] shadow-[0_0_8px_rgba(250,185,100,0.65)]'
                  : 'opacity-75 hover:opacity-100',
              ].join(' ')}
            >
              <img
                src={imageSrc}
                alt={item.name}
                className="h-full w-full object-contain"
                draggable={false}
              />
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default RadiantItems;
