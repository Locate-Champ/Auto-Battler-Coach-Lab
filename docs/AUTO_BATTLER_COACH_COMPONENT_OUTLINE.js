/*
 * Auto-Battler Coach Companion - Component Outline
 *
 * App
 *  - Header
 *  - LiveBoard
 *  - CoachingPanel
 *    - Items
 *    - Position
 *    - Economy
 *    - Shop
 *  - PoolTracker
 *  - MetaComps
 */

export const componentOutline = {
  app: {
    header: true,
    liveBoard: true,
    coachingPanel: ["items", "position", "economy", "shop"],
    poolTracker: true,
    metaComps: true,
  },
};
