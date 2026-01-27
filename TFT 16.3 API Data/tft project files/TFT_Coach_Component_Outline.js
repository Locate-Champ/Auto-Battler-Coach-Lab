/*
╔══════════════════════════════════════════════════════════════════════════════╗
║                    TFT COACH COMPANION - COMPONENT TREE                       ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  TFTCoachCompanion (Main App)                                               ║
║  └── div.min-h-screen.bg-gradient                                           ║
║      │                                                                       ║
║      ├── HEADER ─────────────────────────────────────────────────────────   ║
║      │   ├── Title: "TFT Coach Companion"                                   ║
║      │   ├── Subtitle: "Set 16.2 • Based on 163 games"                     ║
║      │   └── Status: 🟢 "Live • 3s poll"                                    ║
║      │                                                                       ║
║      └── MAIN GRID (12-column) ──────────────────────────────────────────   ║
║          │                                                                   ║
║          ├── LEFT COLUMN (col-span-3) ───────────────────────────────────   ║
║          │   │                                                               ║
║          │   ├── TraitsPanel ─────────────────────────────────────────────  ║
║          │   │   ├── Header: "Traits"                                       ║
║          │   │   ├── Stats Row: 👥 {unitCount} | 💰 {boardCost}g           ║
║          │   │   └── Traits List (map)                                      ║
║          │   │       └── TraitRow                                           ║
║          │   │           ├── trait.name                                     ║
║          │   │           ├── TierBadge (S/A/B/C/D/F)                       ║
║          │   │           └── trait.count                                    ║
║          │   │                                                               ║
║          │   └── LobbyTracker ────────────────────────────────────────────  ║
║          │       ├── Header: "Lobby Tracker"                                ║
║          │       └── Comp List (map COMP_ARCHETYPES)                        ║
║          │           └── CompRow                                            ║
║          │               ├── StatusIcon (✓/⚠/⛔)                           ║
║          │               ├── comp.name                                      ║
║          │               └── Counter: [-] {count} [+]                       ║
║          │                                                                   ║
║          ├── CENTER COLUMN (col-span-6) ─────────────────────────────────   ║
║          │   │                                                               ║
║          │   ├── Board Container ─────────────────────────────────────────  ║
║          │   │   ├── Label: "BOARD STATE (Live from Riot API)"             ║
║          │   │   └── HexBoard ────────────────────────────────────────────  ║
║          │   │       └── Rows (4 rows, alternating offset)                  ║
║          │   │           └── Columns (7 hexes per row)                      ║
║          │   │               ├── HexUnit (if unit exists) ────────────────  ║
║          │   │               │   ├── Item Slots [⬡][⬡]                     ║
║          │   │               │   ├── Stars ★★★                             ║
║          │   │               │   ├── Hexagon Portrait (clipped img)         ║
║          │   │               │   │   └── Cost-colored border/glow           ║
║          │   │               │   └── Champion Name                          ║
║          │   │               │                                               ║
║          │   │               └── EmptyHex (if no unit) ───────────────────  ║
║          │   │                   └── Empty hexagon outline                  ║
║          │   │                                                               ║
║          │   └── ItemSuggestions ─────────────────────────────────────────  ║
║          │       ├── Header: "Items"                                        ║
║          │       └── Two-Column Grid                                        ║
║          │           ├── BUILD Column                                       ║
║          │           │   └── ItemRow (green %)                              ║
║          │           └── AVOID Column                                       ║
║          │               └── ItemRow (strikethrough, red %)                 ║
║          │                                                                   ║
║          └── RIGHT COLUMN (col-span-3) ──────────────────────────────────   ║
║              │                                                               ║
║              ├── ModelSuggestions ────────────────────────────────────────  ║
║              │   ├── Header: "Recommended"                                  ║
║              │   └── Suggestion Cards (top 4, sorted by score)              ║
║              │       └── SuggestionCard                                     ║
║              │           ├── Medal (🥇/🥈/🥉/4️⃣)                           ║
║              │           ├── comp.name                                      ║
║              │           ├── finalScore%                                    ║
║              │           └── Contestation Warning (if contested)            ║
║              │                                                               ║
║              └── PriorityUnits ───────────────────────────────────────────  ║
║                  ├── Header: "Find These"                                   ║
║                  └── Unit List (top 5 carries not on board)                 ║
║                      └── UnitRow                                            ║
║                          ├── name (tier-colored)                            ║
║                          ├── cost 💰                                        ║
║                          └── top4 %                                         ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════╗
║                           DATA STRUCTURES                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  STATE VARIABLES:                                                            ║
║  ─────────────────                                                           ║
║  units[] ─────────────────────────────────────────────────────────────────  ║
║  │  { row: 0, col: 1, name: "Ornn", cost: 5, stars: 2, items: [] }         ║
║  │  { row: 0, col: 3, name: "Sett", cost: 5, stars: 1, items: [] }         ║
║  │  { row: 1, col: 2, name: "Shen", cost: 2, stars: 2, items: [] }         ║
║  │  ...                                                                      ║
║  │                                                                           ║
║  compCounts{} ────────────────────────────────────────────────────────────  ║
║  │  { harvester: 1, soulbound: 0, blacksmith: 2, bruiser: 1, ... }         ║
║  │                                                                           ║
║  traits[] (derived) ──────────────────────────────────────────────────────  ║
║  │  [{ name: "Blacksmith", count: 1 }, { name: "Harvester", count: 1 }]    ║
║  │                                                                           ║
║  boardCost (derived) = Σ(unit.cost × unit.stars)                            ║
║                                                                              ║
║                                                                              ║
║  EMBEDDED PERFORMANCE DATA:                                                  ║
║  ──────────────────────────                                                  ║
║  TRAIT_PERFORMANCE{} ─────────────────────────────────────────────────────  ║
║  │  "Harvester": { top4: 0.88, tier: "S" }                                  ║
║  │  "Bilgewater": { top4: 0.07, tier: "F", avoid: true }                   ║
║  │                                                                           ║
║  CARRY_PERFORMANCE{} ─────────────────────────────────────────────────────  ║
║  │  "Fiddlesticks": { cost: 5, top4: 1.00, tier: "S" }                     ║
║  │  "Ornn": { cost: 5, top4: 1.00, tier: "S" }                             ║
║  │                                                                           ║
║  ITEM_PERFORMANCE{} ──────────────────────────────────────────────────────  ║
║  │  "Blue Buff": { top4: 0.86, tier: "S" }                                  ║
║  │  "Infinity Edge": { top4: 0.20, tier: "F" }                             ║
║  │                                                                           ║
║  COMP_ARCHETYPES[] ───────────────────────────────────────────────────────  ║
║     [{ id: "harvester", name: "Harvester/Fiddle", traits: [...], color }]  ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════╗
║                         RECOMMENDATION ALGORITHM                             ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  For each comp archetype:                                                    ║
║  ───────────────────────                                                     ║
║                                                                              ║
║  1. Calculate BASE SCORE                                                     ║
║     └── Average top4 rate of all traits in comp                             ║
║         baseScore = Σ(TRAIT_PERFORMANCE[trait].top4) / traits.length        ║
║                                                                              ║
║  2. Apply CONTESTATION PENALTY                                               ║
║     └── 15% reduction per player on same comp                               ║
║         penalty = compCounts[comp.id] × 0.15                                 ║
║                                                                              ║
║  3. Calculate FINAL SCORE                                                    ║
║     └── finalScore = baseScore × (1 - penalty)                              ║
║                                                                              ║
║  4. SORT by finalScore descending                                            ║
║                                                                              ║
║  5. Display TOP 4 recommendations                                            ║
║                                                                              ║
║  ┌─────────────────────────────────────────────────────────────────────┐    ║
║  │  EXAMPLE:                                                            │    ║
║  │  ─────────                                                           │    ║
║  │  Harvester base: 88%                                                 │    ║
║  │  Players contesting: 1                                               │    ║
║  │  Penalty: 1 × 15% = 15%                                              │    ║
║  │  Final: 88% × (1 - 0.15) = 88% × 0.85 = 74.8%                       │    ║
║  └─────────────────────────────────────────────────────────────────────┘    ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════╗
║                            HEX UNIT ANATOMY                                  ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║     Container: 64px × 72px                                                   ║
║     ┌──────────────────────────┐                                            ║
║     │      [⬡] [⬡]            │  ← Item slots (16×16px each)               ║
║     │        ★★★              │  ← Stars (gold, 10px)                       ║
║     │     ╱────────╲           │                                             ║
║     │    ╱          ╲          │  ← Hexagon portrait                        ║
║     │   │   [IMG]    │         │     56×48px                                 ║
║     │    ╲          ╱          │     clip-path: polygon(...)                 ║
║     │     ╲────────╱           │     2px border (cost color)                 ║
║     │       Ornn               │  ← Name (9px, white, shadow)               ║
║     └──────────────────────────┘                                            ║
║                                                                              ║
║     COST BORDER COLORS:                                                      ║
║     ───────────────────                                                      ║
║     1-cost: #6b7280 (gray)                                                   ║
║     2-cost: #22c55e (green)                                                  ║
║     3-cost: #3b82f6 (blue)                                                   ║
║     4-cost: #a855f7 (purple)                                                 ║
║     5-cost: #eab308 (gold)                                                   ║
║                                                                              ║
║     HEXAGON CLIP PATH:                                                       ║
║     ──────────────────                                                       ║
║     polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)           ║
║                                                                              ║
║          25%    75%                                                          ║
║           ╱──────╲     0%                                                    ║
║          ╱        ╲                                                          ║
║      0% │          │ 100%   50%                                              ║
║          ╲        ╱                                                          ║
║           ╲──────╱     100%                                                  ║
║          25%    75%                                                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝


╔══════════════════════════════════════════════════════════════════════════════╗
║                          HEX BOARD LAYOUT                                    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  4 rows × 7 columns                                                          ║
║  Alternating row offset: 32px                                                ║
║  Vertical overlap: -8px between rows                                         ║
║                                                                              ║
║  Row 0 (no offset):                                                          ║
║  ┌───┬───┬───┬───┬───┬───┬───┐                                              ║
║  │ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │                                              ║
║  └───┴───┴───┴───┴───┴───┴───┘                                              ║
║                                                                              ║
║  Row 1 (offset 32px):                                                        ║
║     ┌───┬───┬───┬───┬───┬───┬───┐                                           ║
║     │ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │                                           ║
║     └───┴───┴───┴───┴───┴───┴───┘                                           ║
║                                                                              ║
║  Row 2 (no offset):                                                          ║
║  ┌───┬───┬───┬───┬───┬───┬───┐                                              ║
║  │ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │                                              ║
║  └───┴───┴───┴───┴───┴───┴───┘                                              ║
║                                                                              ║
║  Row 3 (offset 32px):                                                        ║
║     ┌───┬───┬───┬───┬───┬───┬───┐                                           ║
║     │ 0 │ 1 │ 2 │ 3 │ 4 │ 5 │ 6 │                                           ║
║     └───┴───┴───┴───┴───┴───┴───┘                                           ║
║                                                                              ║
║  DEMO BOARD STATE:                                                           ║
║  ─────────────────                                                           ║
║  Row 0: [_][Ornn][_][Sett][_][_][_]                                         ║
║  Row 1: [_][_][Shen][_][_][_][_]                                            ║
║  Row 2: [_][Fiddle][_][_][Ryze][_][_]                                       ║
║  Row 3: [_][_][_][Zilean][_][_][_]                                          ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
*/
