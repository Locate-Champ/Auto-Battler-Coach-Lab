import React from 'react';

const CRAFTABLE_GROUPS = [
  {
    title: 'Tank',
    left: '20px',
    top: '8px',
    items: [
      { name: "Protector's Vow", file: "Protector's Vow.png" },
      { name: 'Spirit Visage', file: 'Spirit Visage.png' },
      { name: 'Crownguard', file: 'Crownguard.png' },
      { name: 'Steadfast Heart', file: 'Steadfast Heart.png' },
      { name: 'Bramble Vest', file: 'Bramble Vest.png' },
      { name: 'Gargoyle Stoneplate', file: 'Gargoyle Stoneplate.png' },
      { name: "Dragon's Claw", file: "Dragon's Claw.png" },
      { name: "Warmog's Armor", file: "Warmog's Armor.png" },
    ],
  },
  {
    title: 'AD',
    left: '328.19px',
    top: '8px',
    items: [
      { name: "Kraken's Fury", file: "Kraken's Fury.png" },
      { name: 'Deathblade', file: 'Deathblade.png' },
      { name: 'Infinity Edge', file: 'Infinity Edge.png' },
    ],
  },
  {
    title: 'Utility',
    left: '20px',
    top: '80px',
    items: [
      { name: 'Evenshroud', file: 'Evenshroud.png' },
      { name: 'Last Whisper', file: 'Last Whisper.png' },
      { name: 'Ionic Spark', file: 'Ionic Spark.png' },
      { name: 'Void Staff', file: 'Void Staff.png' },
      { name: 'Sunfire Cape', file: 'Sunfire Cape.png' },
      { name: 'Red Buff', file: 'Red Buff.png' },
      { name: 'Morellonomicon', file: 'Morellonomicon.png' },
    ],
  },
  {
    title: 'AP',
    left: '291.20px',
    top: '80px',
    items: [
      { name: "Nashor's Tooth", file: "Nashor's Tooth.png" },
      { name: "Archangel's Staff", file: "Archangel's Staff.png" },
      { name: "Rabadon's Deathcap", file: "Rabadon's Deathcap.png" },
      { name: 'Jeweled Gauntlet', file: 'Jeweled Gauntlet.png' },
    ],
  },
  {
    title: 'Melee',
    left: '20px',
    top: '140px',
    items: [
      { name: "Titan's Resolve", file: "Titan's Resolve.png" },
      { name: 'Edge of Night', file: 'Edge of Night.png' },
      { name: "Sterak's Gage", file: "Sterak's Gage.png" },
      { name: 'Quicksilver', file: 'Quicksilver.png' },
    ],
  },
  {
    title: 'Omnivamp',
    left: '180.21px',
    top: '140px',
    items: [
      { name: 'Hand Of Justice', file: 'Hand Of Justice.png' },
      { name: 'Hextech Gunblade', file: 'Hextech Gunblade.png' },
      { name: 'Bloodthirster', file: 'Bloodthirster.png' },
    ],
  },
  {
    title: 'Mana',
    left: '303.42px',
    top: '140px',
    items: [
      { name: 'Blue Buff', file: 'Blue Buff.png' },
      { name: 'Spear of Shojin', file: 'Spear of Shojin.png' },
      { name: 'Adaptive Helm', file: 'Adaptive Helm.png' },
    ],
  },
  {
    title: 'Any Carry',
    left: '20px',
    top: '200px',
    items: [
      { name: "Guinsoo's Rageblade", file: "Guinsoo's Rageblade.png" },
      { name: 'Giant Slayer', file: 'Giant Slayer.png' },
      { name: "Striker's Flail", file: "Striker's Flail.png" },
      { name: "Thief's Gloves", file: "Thief's Gloves.png" },
    ],
  },
  {
    title: 'Component',
    left: '20px',
    top: '260px',
    items: [
      { name: 'B.F. Sword', file: 'B.F. Sword.png' },
      { name: 'Chain Vest', file: 'Chain Vest.png' },
      { name: 'Frying Pan', file: 'Frying Pan.png' },
      { name: "Giant's Belt", file: "Giant's Belt.png" },
      { name: 'Needlessly Large Rod', file: 'Needlessly Large Rod.png' },
      { name: 'Negatron Cloak', file: 'Negatron Cloak.png' },
      { name: 'Recurve Bow', file: 'Recurve Bow.png' },
      { name: 'Sparring Gloves', file: 'Sparring Gloves.png' },
      { name: 'Spatula', file: 'Spatula.png' },
      { name: 'Tear of the Goddess', file: 'Tear of the Goddess.png' },
    ],
  },
] as const;

export type CraftableItemName =
  (typeof CRAFTABLE_GROUPS)[number]['items'][number]['name'];

export interface InventoryItem {
  name: string;
  count?: number;
  category?: string;
}

interface CraftableItemsProps {
  inventory?: Iterable<InventoryItem>;
  onItemClick?: (item: CraftableItemName) => void;
  className?: string;
}

const CraftableItems: React.FC<CraftableItemsProps> = ({
  inventory,
  onItemClick,
  className,
}) => {
  const ownedItems = new Map<string, number>();

  if (inventory) {
    for (const item of inventory) {
      if (item.category && !['craftable', 'component'].includes(item.category)) {
        continue;
      }
      if (typeof item.count === 'number' && item.count <= 0) continue;
      ownedItems.set(item.name, item.count ?? 1);
    }
  }

  return (
    <div
      data-layer="Frame"
      className={`relative w-[492.88px] h-[420px] ${className ?? ''}`}
    >
      {CRAFTABLE_GROUPS.map((group) => (
        <div
          key={group.title}
          data-layer="div.builder-item-group"
          className="absolute h-16 px-[1px] pt-[0.11px] pb-[1px] outline outline-1 outline-offset-[-1px] inline-flex flex-col justify-start items-center"
          style={{ left: group.left, top: group.top, outlineColor: 'rgba(255,255,255,0.2)' }}
        >
          <div
            data-layer="div.builder-item-group-header"
            className="flex flex-col justify-start items-start"
          >
            <div
              data-layer={group.title}
              className="text-base leading-7"
              style={{ fontFamily: 'Arial, sans-serif', color: 'rgba(255,255,255,0.87)' }}
            >
              {group.title}
            </div>
          </div>
          <div
            data-layer="div.builder-item-row"
            className="inline-flex justify-start items-start gap-[1px] flex-wrap content-start"
          >
            {group.items.map((item) => {
              const isOwned = ownedItems.has(item.name);
              const imageSrc = new URL(
                `./images/craftable items images/${item.file}`,
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
      ))}
    </div>
  );
};

export default CraftableItems;
