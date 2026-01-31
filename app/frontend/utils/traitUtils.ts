/**
 * Trait utilities for TFT Set 16
 * Handles trait ID mapping, icon lookup, and breakpoint calculations
 */

// Tier colors from tftset16trait.py (Riot's official colors)
export const TIER_COLORS = {
  bronze: { bg: '#B8773B', border: '#CD7F32', text: '#FFFFFF' },
  silver: { bg: '#71797E', border: '#C0C0C0', text: '#FFFFFF' },
  gold: { bg: '#C9A227', border: '#FFD700', text: '#FFFFFF' },
  prismatic: { bg: '#9B59B6', border: '#B388FF', text: '#FFFFFF' },
  unique: { bg: '#E74C8C', border: '#FF4D8D', text: '#FFFFFF' },
  inactive: { bg: '#2C3442', border: '#4a4a5f', text: '#6b7280' },
};

// API name -> Display name mapping
export const TRAIT_ID_MAP: Record<string, string> = {
  // Mismatched names (API name differs from display name)
  'Sorcerer': 'Arcanist',
  'Magus': 'Disruptor',
  'Rapidfire': 'Quickstriker',
  'Explorer': 'Ixtal',
  'Brawler': 'Bruiser',
  'DarkinWeapon': 'Darkin',
  'ShadowIsles': 'Shadow Isles',
  'RuneMage': 'Rune Mage',
  'DarkChild': 'Dark Child',
  'TheBoss': 'The Boss',
  'AatroxUnique': 'World Ender',
  'AurelionSolUnique': 'Star Forger',
  'BaronUnique': 'Riftscourge',
  'KaisaUnique': 'Assimilator',
  'KindredUnique': 'Eternal',
  'ShyvanaUnique': 'Dragonborn',
  'SylasTrait': 'Chainbreaker',
  'XerathUnique': 'Ascendant',
  'ZaahenTrait': 'Immortal',
  'Teamup_AmbessaKindred': 'Chosen Wolves',
  'Teamup_EkkoZilean': 'Timewinders',
  'Teamup_JarvanShyvana': 'Dragonguards',
  'Teamup_LucianVayne': 'Sentinels of Light',
  'Teamup_SingedTeemo': 'Poison Pals',
  // Names that match (included for completeness)
  'Freljord': 'Freljord',
  'Juggernaut': 'Juggernaut',
  'Longshot': 'Longshot',
  'Vanquisher': 'Vanquisher',
  'Slayer': 'Slayer',
  'Emperor': 'Emperor',
  'Gunslinger': 'Gunslinger',
  'HexMech': 'HexMech',
  'Caretaker': 'Caretaker',
  'Soulbound': 'Soulbound',
  'Piltover': 'Piltover',
  'Void': 'Void',
  'Glutton': 'Glutton',
  'Invoker': 'Invoker',
  'Demacia': 'Demacia',
  'Bilgewater': 'Bilgewater',
  'Noxus': 'Noxus',
  'Yordle': 'Yordle',
  'Zaun': 'Zaun',
  'Warden': 'Warden',
  'Ionia': 'Ionia',
  'Defender': 'Defender',
  'Shurima': 'Shurima',
  'Targon': 'Targon',
  'Blacksmith': 'Blacksmith',
  'Harvester': 'Harvester',
  'Heroic': 'Heroic',
  'Huntress': 'Huntress',
  'Chronokeeper': 'Chronokeeper',
};

// Display name -> Icon filename mapping
export const TRAIT_ICON_MAP: Record<string, string> = {
  'Arcanist': 'trait_icon_16_arcanist.png',
  'Disruptor': 'trait_icon_16_disruptor.png',
  'Quickstriker': 'trait_icon_16_quickstriker.png',
  'Ixtal': 'trait_icon_16_ixtal.tft_set16.png',
  'Bruiser': 'trait_icon_16_bruiser.tft_set16.png',
  'Darkin': 'trait_icon_16_darkin.tft_set16.png',
  'Shadow Isles': 'trait_icon_16_shadowisles.tft_set16.png',
  'Rune Mage': 'trait_icon_16_runemage.tft_set16.png',
  'Dark Child': 'trait_icon_16_darkchild.tft_set16.png',
  'The Boss': 'trait_icon_16_theboss.tft_set16.png',
  'World Ender': 'trait_icon_16_worldender.tft_set16.png',
  'Star Forger': 'trait_icon_16_starforger.tft_set16.png',
  'Riftscourge': 'trait_icon_16_riftscourge.png',
  'Assimilator': 'trait_icon_16_assimilator.tft_set16.png',
  'Eternal': 'trait_icon_16_eternal.png',
  'Dragonborn': 'trait_icon_16_dragonborn.tft_set16.png',
  'Chainbreaker': 'trait_icon_16_chainbreaker.tft_set16.png',
  'Ascendant': 'trait_icon_16_ascendant.tft_set16.png',
  'Immortal': 'trait_icon_16_immortal.tft_set16.png',
  'Chosen Wolves': 'teamup_trait_chosenwolves.tft_set16.png',
  'Timewinders': 'teamup_trait_timewinders.tft_set16.png',
  'Dragonguards': 'teamup_trait_uncompromisingwill.tft_set16.png',
  'Sentinels of Light': 'teamup_trait_sentinelsoflight.tft_set16.png',
  'Poison Pals': 'teamup_trait_poisonpals.tft_set16.png',
  'Freljord': 'trait_icon_16_freljord.tft_set16.png',
  'Juggernaut': 'trait_icon_16_juggernaut.png',
  'Longshot': 'trait_icon_16_longshot.tft_set16.png',
  'Vanquisher': 'trait_icon_16_vanquisher.png',
  'Slayer': 'trait_icon_16_slayer.png',
  'Emperor': 'trait_icon_16_emperor.tft_set16.png',
  'Gunslinger': 'trait_icon_16_gunslinger.tft_set16.png',
  'HexMech': 'trait_icon_16_hexmech.tft_set16.png',
  'Caretaker': 'trait_icon_16_caretaker.tft_set16.png',
  'Soulbound': 'trait_icon_16_soulbound.tft_set16.png',
  'Piltover': 'trait_icon_16_piltover.tft_set16.png',
  'Void': 'trait_icon_16_void.tft_set16.png',
  'Glutton': 'trait_icon_16_glutton.tft_set16.png',
  'Invoker': 'trait_icon_16_invoker.png',
  'Demacia': 'trait_icon_16_demacia.tft_set16.png',
  'Bilgewater': 'trait_icon_16_bilgewater.tft_set16.png',
  'Noxus': 'trait_icon_16_noxus.tft_set16.png',
  'Yordle': 'trait_icon_16_yordle.tft_set16.png',
  'Zaun': 'trait_icon_16_zaun.tft_set16.png',
  'Warden': 'trait_icon_16_warden.tft_set16.png',
  'Ionia': 'trait_icon_16_ionia.tft_set16.png',
  'Defender': 'trait_icon_16_defender.png',
  'Shurima': 'trait_icon_16_shurima.tft_set16.png',
  'Targon': 'trait_icon_16_targon.tft_set16.png',
  'Blacksmith': 'trait_icon_16_blacksmith.tft_set16.png',
  'Harvester': 'trait_icon_16_harvester.tft_set16.png',
  'Heroic': 'trait_icon_16_heroic.tft_set16.png',
  'Huntress': 'trait_icon_16_huntress.tft_set16.png',
  'Chronokeeper': 'trait_icon_16_chronokeeper.tft_set16.png',
};

// Trait breakpoints: [minUnits, style] where style: 1=bronze, 3=silver, 5=gold, 6=prismatic, 4=unique
export const TRAIT_BREAKPOINTS: Record<string, [number, number][]> = {
  // Region traits
  'Freljord': [[3, 1], [5, 3], [7, 5]],
  'Ixtal': [[3, 1], [5, 3], [7, 5]],
  'Demacia': [[3, 1], [5, 3], [7, 5], [11, 6]],
  'Bilgewater': [[3, 1], [5, 3], [7, 5], [10, 6]],
  'Piltover': [[2, 1], [4, 3], [6, 5]],
  'Noxus': [[3, 1], [5, 3], [7, 5], [10, 6]],
  'Ionia': [[3, 1], [5, 3], [7, 5], [10, 6]],
  'Void': [[2, 1], [4, 3], [6, 5], [9, 5]],
  'Zaun': [[3, 1], [5, 3], [7, 5]],
  'Shadow Isles': [[2, 1], [3, 3], [4, 3], [5, 5]],
  'Shurima': [[2, 1], [3, 5], [4, 6]],
  'Targon': [[1, 5]],

  // Class traits
  'Juggernaut': [[2, 1], [4, 3], [6, 5]],
  'Quickstriker': [[2, 1], [3, 3], [4, 3], [5, 5]],
  'Longshot': [[2, 1], [3, 3], [4, 5], [5, 5]],
  'Vanquisher': [[2, 1], [3, 3], [4, 3], [5, 5]],
  'Slayer': [[2, 1], [4, 3], [6, 5]],
  'Arcanist': [[2, 1], [4, 3], [6, 5]],
  'Gunslinger': [[2, 1], [4, 5]],
  'Disruptor': [[2, 1], [4, 5]],
  'Invoker': [[2, 1], [4, 5]],
  'Bruiser': [[2, 1], [4, 3], [6, 5]],
  'Warden': [[2, 1], [3, 3], [4, 3], [5, 5]],
  'Defender': [[2, 1], [4, 3], [6, 5]],
  'Darkin': [[1, 1], [2, 3], [3, 5]],
  'Yordle': [[2, 1], [4, 3], [6, 3], [8, 5], [10, 6]],

  // Unique traits (single tier, style 4)
  'Caretaker': [[1, 4]],
  'Emperor': [[1, 4]],
  'Star Forger': [[1, 4]],
  'Dragonborn': [[1, 4]],
  'HexMech': [[1, 4]],
  'Chosen Wolves': [[2, 4]],
  'Chainbreaker': [[1, 4]],
  'Soulbound': [[1, 4]],
  'Timewinders': [[1, 4], [2, 4]],
  'Eternal': [[1, 4]],
  'Dark Child': [[1, 4]],
  'World Ender': [[1, 4]],
  'Assimilator': [[1, 4]],
  'Dragonguards': [[2, 4]],
  'Riftscourge': [[1, 4]],
  'Rune Mage': [[1, 4]],
  'The Boss': [[1, 4]],
  'Glutton': [[1, 4]],
  'Blacksmith': [[1, 4]],
  'Harvester': [[1, 4]],
  'Immortal': [[1, 4]],
  'Heroic': [[1, 4]],
  'Chronokeeper': [[1, 4]],
  'Poison Pals': [[2, 4]],
  'Sentinels of Light': [[2, 4]],
  'Huntress': [[1, 4]],
  'Ascendant': [[1, 4]],
};

export type TraitTier = 'bronze' | 'silver' | 'gold' | 'prismatic' | 'unique' | 'inactive';

export interface TraitTierInfo {
  tier: TraitTier;
  currentBreakpoint: number;
  nextBreakpoint: number | null;
}

/**
 * Normalize trait name from API format to display format
 */
export function normalizeTraitName(apiName: string): string {
  return TRAIT_ID_MAP[apiName] || apiName;
}

/**
 * Get trait icon URL
 */
export function getTraitIcon(displayName: string): string {
  const iconFile = TRAIT_ICON_MAP[displayName];
  if (iconFile) {
    try {
      return new URL(`../images/trait images/trait_icons_set16/${iconFile}`, import.meta.url).href;
    } catch {
      // Fallback for missing icons
      return '';
    }
  }
  return '';
}

/**
 * Get trait tier info based on count
 */
export function getTraitTierInfo(traitName: string, count: number): TraitTierInfo {
  const breakpoints = TRAIT_BREAKPOINTS[traitName];

  if (!breakpoints || breakpoints.length === 0) {
    // Unknown trait - assume it's active if count >= 1
    return {
      tier: count >= 1 ? 'bronze' : 'inactive',
      currentBreakpoint: count,
      nextBreakpoint: null,
    };
  }

  let activeTier: TraitTier = 'inactive';
  let currentBreakpoint = 0;
  let nextBreakpoint: number | null = null;

  for (let i = 0; i < breakpoints.length; i++) {
    const [minUnits, style] = breakpoints[i];

    if (count >= minUnits) {
      currentBreakpoint = minUnits;
      // Map style number to tier name
      switch (style) {
        case 1: activeTier = 'bronze'; break;
        case 3: activeTier = 'silver'; break;
        case 4: activeTier = 'unique'; break;
        case 5: activeTier = 'gold'; break;
        case 6: activeTier = 'prismatic'; break;
      }
      // Check for next breakpoint
      if (i + 1 < breakpoints.length) {
        nextBreakpoint = breakpoints[i + 1][0];
      } else {
        nextBreakpoint = null;
      }
    }
  }

  // If no breakpoint was reached, find the first one
  if (activeTier === 'inactive' && breakpoints.length > 0) {
    nextBreakpoint = breakpoints[0][0];
  }

  return { tier: activeTier, currentBreakpoint, nextBreakpoint };
}

/**
 * Check if a trait is active (meets minimum breakpoint)
 */
export function isTraitActive(traitName: string, count: number): boolean {
  const breakpoints = TRAIT_BREAKPOINTS[traitName];
  if (!breakpoints || breakpoints.length === 0) {
    return count >= 1;
  }
  return count >= breakpoints[0][0];
}

/**
 * Get tier colors for a trait tier
 */
export function getTierColors(tier: TraitTier) {
  return TIER_COLORS[tier] || TIER_COLORS.inactive;
}
