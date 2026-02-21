import React, { useState } from 'react';

type ItemTab = 'Craftable' | 'Artifact' | 'Emblem' | 'Radiant' | 'Support' | 'Set';

const TABS: ItemTab[] = ['Craftable', 'Artifact', 'Emblem', 'Radiant', 'Support', 'Set'];

interface ItemsBarProps {
  defaultTab?: ItemTab;
  onTabChange?: (tab: ItemTab) => void;
}

const ItemsBar: React.FC<ItemsBarProps> = ({ defaultTab = 'Set', onTabChange }) => {
  const [selectedTab, setSelectedTab] = useState<ItemTab>(defaultTab);

  const handleTabClick = (tab: ItemTab) => {
    setSelectedTab(tab);
    onTabChange?.(tab);
  };

  return (
    <div
      className="w-[491.99px] px-5 inline-flex flex-col justify-start items-start rounded-t-lg"
      style={{
        backgroundColor: '#232422',
        boxShadow: '0px 4px 4px 0px rgba(0,0,0,0.25)'
      }}
    >
      <div className="self-stretch relative inline-flex justify-center items-start">
        {TABS.map((tab) => {
          const isSelected = selectedTab === tab;
          return (
            <button
              key={tab}
              onClick={() => handleTabClick(tab)}
              className="flex-1 h-10 px-1.5 py-px inline-flex flex-col justify-center items-center overflow-hidden cursor-pointer bg-transparent border-none"
            >
              <span
                className="text-center text-xs font-bold leading-10"
                style={{
                  fontFamily: 'Google Sans Code, monospace',
                  color: isSelected ? '#fab964' : '#f7f7f7',
                  textShadow: '-2px 2px 2px rgba(0, 0, 0, 1.00)'
                }}
              >
                {tab}
              </span>
            </button>
          );
        })}
        
        {/* Animated underline bar */}
        <div
          className="h-0.5 absolute bottom-0 transition-all duration-200 ease-in-out"
          style={{
            backgroundColor: '#fab964',
            width: `${100 / TABS.length}%`,
            left: `${(TABS.indexOf(selectedTab) / TABS.length) * 100}%`
          }}
        />
      </div>
    </div>
  );
};

export default ItemsBar;
