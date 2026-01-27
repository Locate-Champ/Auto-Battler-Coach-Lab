# TFT Coach Companion - Figma UI Specification

## 📐 LAYOUT OVERVIEW

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HEADER                                                          [Status]  │
│  TFT Coach Companion • Set 16.2                                 🟢 Live    │
├─────────────────┬───────────────────────────────────┬───────────────────────┤
│                 │                                   │                       │
│  LEFT PANEL     │        CENTER PANEL               │    RIGHT PANEL        │
│  (240px)        │        (flex/remaining)           │    (280px)            │
│                 │                                   │                       │
│  ┌───────────┐  │  ┌─────────────────────────────┐  │  ┌─────────────────┐  │
│  │  TRAITS   │  │  │                             │  │  │  RECOMMENDED    │  │
│  │  PANEL    │  │  │      HEXAGONAL BOARD        │  │  │  COMPS          │  │
│  │           │  │  │      (7x4 hex grid)         │  │  │                 │  │
│  │  👥 6     │  │  │                             │  │  │  🥇 Harvester   │  │
│  │  💰 31g   │  │  │   [Live from Riot API]      │  │  │  🥈 Soulbound   │  │
│  │           │  │  │                             │  │  │  🥉 Blacksmith  │  │
│  └───────────┘  │  │                             │  │  │                 │  │
│                 │  └─────────────────────────────┘  │  └─────────────────┘  │
│  ┌───────────┐  │                                   │                       │
│  │  LOBBY    │  │  ┌─────────────────────────────┐  │  ┌─────────────────┐  │
│  │  TRACKER  │  │  │      ITEM SUGGESTIONS       │  │  │  PRIORITY       │  │
│  │           │  │  │                             │  │  │  UNITS          │  │
│  │  Comp [-]n[+] │  │  BUILD:        AVOID:       │  │  │                 │  │
│  │  Comp [-]n[+] │  │  Blue Buff     IE           │  │  │  Fiddlesticks   │  │
│  │  Comp [-]n[+] │  │  Morello       Giant Slayer │  │  │  Ornn           │  │
│  └───────────┘  │  └─────────────────────────────┘  │  │  Sett           │  │
│                 │                                   │  └─────────────────┘  │
└─────────────────┴───────────────────────────────────┴───────────────────────┘
```

---

## 🎨 COLOR PALETTE

### Background Colors
| Name | Hex | Usage |
|------|-----|-------|
| bg-primary | `#030712` | Main app background (gray-950) |
| bg-secondary | `#111827` | Panel backgrounds (gray-900) |
| bg-card | `#1f2937` | Card/elevated surfaces (gray-800) |
| bg-hover | `#374151` | Hover states (gray-700) |

### Accent Colors
| Name | Hex | Usage |
|------|-----|-------|
| cyan-primary | `#00d4ff` | Headers, highlights, primary actions |
| cyan-muted | `#0891b2` | Secondary accents |

### Champion Cost Tier Colors
| Cost | Border Hex | Glow Color | RGB Glow |
|------|------------|------------|----------|
| 1-cost | `#6b7280` | Gray | `rgba(107, 114, 128, 0.5)` |
| 2-cost | `#22c55e` | Green | `rgba(34, 197, 94, 0.5)` |
| 3-cost | `#3b82f6` | Blue | `rgba(59, 130, 246, 0.5)` |
| 4-cost | `#a855f7` | Purple | `rgba(168, 85, 247, 0.5)` |
| 5-cost | `#eab308` | Gold | `rgba(234, 179, 8, 0.5)` |

### Status/Feedback Colors
| Name | Hex | Usage |
|------|-----|-------|
| success | `#22c55e` | Open comp, good items, S-tier |
| warning | `#eab308` | Contested (1 player), caution |
| danger | `#ef4444` | Heavily contested (2+), avoid items |
| info | `#3b82f6` | Neutral info, B-tier |

### Tier Badge Colors
| Tier | Background Hex | Text |
|------|----------------|------|
| S | `#eab308` | White |
| A | `#22c55e` | White |
| B | `#3b82f6` | White |
| C | `#6b7280` | White |
| D | `#f97316` | White |
| F | `#ef4444` | White |

---

## 📝 TYPOGRAPHY

### Font Family
- **Primary**: Inter, -apple-system, BlinkMacSystemFont, sans-serif
- **Alternative**: Roboto, system-ui

### Type Scale
| Element | Size | Weight | Color |
|---------|------|--------|-------|
| App title | 20px | Bold (700) | `#00d4ff` |
| Subtitle | 12px | Normal (400) | `#6b7280` |
| Panel header | 14px | Bold (700) | `#00d4ff` |
| Body text | 14px | Normal (400) | `#e5e7eb` |
| Small text | 12px | Normal (400) | `#9ca3af` |
| Tiny/labels | 10px | Medium (500) | `#6b7280` |
| Champion name | 9px | Normal (400) | `#ffffff` |
| Stats/numbers | 14px | Bold (700) | `#ffffff` |

---

## 📦 COMPONENT SPECIFICATIONS

### 1. HEADER
```
Height: 56px
Padding: 16px horizontal
Border-bottom: 1px solid #1f2937

Left side:
- Title: "TFT Coach Companion" (20px, bold, cyan)
- Subtitle: "Set 16.2 • Based on 163 games" (12px, gray-500)

Right side:
- Status dot: 8px circle, #22c55e, with pulse animation
- Text: "Live • 3s poll" (12px, gray-400)
```

### 2. PANEL CARD (Traits, Lobby, Suggestions, etc.)
```
Background: #111827 (gray-900) with 90% opacity
Border: 1px solid #374151 (gray-700)
Border-radius: 8px
Padding: 12px

Header:
- Text: 14px, bold, #00d4ff
- Border-bottom: 1px solid #374151
- Padding-bottom: 8px
- Margin-bottom: 8px
```

### 3. HEXAGONAL BOARD

#### Board Layout
```
Grid: 7 columns × 4 rows
Row offset: Alternate rows offset by half hex width (32px)
Row vertical overlap: -8px (hexes slightly overlap vertically)

Total dimensions: ~480px wide × 280px tall
```

#### Single Hex Unit (with champion)
```
Container: 64px wide × 72px tall

Components (top to bottom):
1. ITEM SLOTS (top)
   - Position: Centered at top
   - Two circles: 16px × 16px each
   - Gap: 2px between
   - Background: #1f2937
   - Border: 1px solid #4b5563
   
2. STARS (below items)
   - Position: Top 56% (about 4px below items)
   - Font: 10px
   - Color: #eab308 (gold)
   - Characters: ★ (repeated for star level)
   - Text shadow: 0 1px 2px rgba(0,0,0,0.8)

3. HEXAGON PORTRAIT
   - Position: 5px from top
   - Size: 56px wide × 48px tall
   - Clip path: polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)
   - Border: 2px solid [cost color]
   - Box shadow: 0 0 8px [cost glow color]
   - Image: object-fit cover, scale 110%

4. CHAMPION NAME (bottom)
   - Position: Bottom of container
   - Font: 9px, white
   - Text shadow: 0 1px 2px rgba(0,0,0,0.9)
   - White-space: nowrap
```

#### Empty Hex
```
Same hexagon shape/size
Background: linear-gradient(135deg, #1f2937, #111827)
Border: 2px solid #374151
Opacity: 40%
Hover opacity: 60%
```

### 4. TRAITS PANEL

#### Stats Row
```
Layout: Horizontal flex, gap 16px
Items:
- "👥 6" (unit count)
- "💰 31g" (board cost)
Emoji: 14px
Number: 14px, bold, white
```

#### Trait Row
```
Height: 24px
Layout: Space-between flex

Left side:
- Trait name (14px, #d1d5db)
- Tier badge (inline, 4px margin-left)

Right side:
- Count number (14px, #6b7280)

Tier Badge:
- Font: 10px, bold, white
- Padding: 2px 4px
- Border-radius: 4px
- Background: [tier color]
```

### 5. LOBBY TRACKER

#### Comp Row
```
Height: 28px
Layout: Space-between flex

Left side:
- Status icon (✓/⚠/⛔) with color
- Comp name (12px)
  - If count=0: comp.color
  - If count>0: #9ca3af

Right side - Counter:
- Minus button: 20px × 20px, bg #374151, hover #4b5563, rounded
- Count: 20px wide, centered, 14px bold white
- Plus button: same as minus
- Gap: 2px between elements
```

#### Status Icons
| Count | Icon | Color |
|-------|------|-------|
| 0 | ✓ | `#22c55e` |
| 1 | ⚠ | `#eab308` |
| 2+ | ⛔ | `#ef4444` |

### 6. MODEL SUGGESTIONS (Recommended Comps)

#### Suggestion Card
```
Padding: 8px
Border-radius: 4px
Margin-bottom: 6px

Top recommendation (index 0):
- Background: rgba(8, 145, 178, 0.15) (cyan-900/30)
- Border: 1px solid rgba(6, 182, 212, 0.3)

Other recommendations:
- Background: rgba(31, 41, 55, 0.5) (gray-800/50)

Content:
- Row 1: Medal emoji + Name (14px, bold) | Score% (14px, bold, cyan)
- Row 2 (if contested): "⚠ N contesting" (12px, yellow)
```

#### Medals
| Rank | Emoji |
|------|-------|
| 1st | 🥇 |
| 2nd | 🥈 |
| 3rd | 🥉 |
| 4th | 4️⃣ |

### 7. PRIORITY UNITS

#### Unit Row
```
Height: 22px
Layout: Space-between flex

Left side:
- Name (14px, [tier color])
- Cost badge: "(5💰)" (12px, #6b7280)

Right side:
- Win rate: "100%" (14px, #9ca3af)
```

### 8. ITEM SUGGESTIONS

#### Layout
```
Two-column grid, gap 16px

Column 1 - BUILD:
- Header: "BUILD:" (12px, bold, #22c55e)
- Items list

Column 2 - AVOID:
- Header: "AVOID:" (12px, bold, #ef4444)
- Items list (with strikethrough)
```

#### Item Row
```
Height: 18px
Font: 12px
Layout: Space-between flex

BUILD items:
- Name: #d1d5db
- Percent: #22c55e

AVOID items:
- Name: #6b7280, text-decoration: line-through
- Percent: #ef4444
```

---

## 🔧 INTERACTIVE STATES

### Buttons (Counter +/-)
```
Default: bg #374151, text #d1d5db
Hover: bg #4b5563
Active: bg #1f2937
```

### Hex Hover
```
Empty: opacity 40% → 60%
With unit: scale 1.05, cursor pointer
```

### Panel Hover
```
Subtle lift: box-shadow 0 4px 6px rgba(0,0,0,0.3)
```

---

## 📱 RESPONSIVE CONSIDERATIONS

### Desktop (1200px+)
- Full 3-column layout
- All panels visible

### Tablet (768px - 1199px)
- Stack: Left panel above center
- Right panel as collapsible drawer

### Mobile (< 768px)
- Single column stack
- Hex board scales down
- Panels become accordion sections

---

## 🖼️ ASSET SOURCES

### Champion Portraits
```
Primary: https://raw.communitydragon.org/latest/game/assets/characters/tft16_{champion}/hud/tft16_{champion}_square.tft_set16.png

Fallback: https://tftflow.com/wp-content/uploads/tftImages/champions/tileIcon/tft16_{champion}_square.tft_set16.png

Size: 56×56px recommended
Format: PNG with transparency
```

### Naming Convention
- lowercase
- no spaces
- no apostrophes
- Example: "Miss Fortune" → "missfortune"
- Example: "Kai'Sa" → "kaisa"

---

## 📊 DATA FLOW

```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│  Riot API   │───▶│  Board State │───▶│ Trait Calculator│
│  (3s poll)  │    │    Parser    │    │                 │
└─────────────┘    └──────────────┘    └────────┬────────┘
                                                │
┌─────────────┐    ┌──────────────┐    ┌────────▼────────┐
│   Manual    │───▶│    Lobby     │───▶│  Recommendation │
│   Input     │    │   Tracker    │    │     Engine      │
└─────────────┘    └──────────────┘    └────────┬────────┘
                                                │
                                       ┌────────▼────────┐
                                       │   UI Update     │
                                       │  (React State)  │
                                       └─────────────────┘
```

---

## 🎯 KEY FIGMA COMPONENTS TO CREATE

1. **HexUnit** - Champion in hex with items, stars, portrait, name
2. **EmptyHex** - Empty board slot
3. **HexBoard** - 7×4 grid of hex slots
4. **PanelCard** - Reusable card container with header
5. **TraitRow** - Trait name + tier badge + count
6. **CompCounter** - Comp name + status + [-] n [+] buttons
7. **SuggestionCard** - Medal + name + score + contestation warning
8. **UnitRow** - Priority unit with tier color + cost + win rate
9. **ItemRow** - Item name + percentage (build/avoid variants)
10. **TierBadge** - S/A/B/C/D/F badges
11. **StatusDot** - Pulsing connection indicator
