import { fetchWithRetry, writeJSON, dataPath, riotRegionToUrlSlug } from './utils.js';

const REGIONS = ['na', 'kr', 'euw'];

/**
 * Extract buildId from any tactics.tools page's __NEXT_DATA__.
 */
export async function getBuildId() {
  console.log('Fetching buildId from tactics.tools...');
  const res = await fetchWithRetry('https://tactics.tools/leaderboards');
  const html = await res.text();

  const match = html.match(/<script id="__NEXT_DATA__" type="application\/json">(.*?)<\/script>/);
  if (!match) {
    throw new Error('Could not find __NEXT_DATA__ in leaderboards page');
  }

  const nextData = JSON.parse(match[1]);
  const buildId = nextData.buildId;

  if (!buildId) {
    throw new Error('buildId not found in __NEXT_DATA__');
  }

  console.log(`  buildId: ${buildId}`);
  return buildId;
}

/**
 * Scrape leaderboard data for a single region.
 * Returns array of player objects.
 */
async function scrapeRegionLeaderboard(region) {
  console.log(`Scraping ${region.toUpperCase()} leaderboard...`);
  const res = await fetchWithRetry(`https://tactics.tools/leaderboards/${region}`);
  const html = await res.text();

  const match = html.match(/<script id="__NEXT_DATA__" type="application\/json">(.*?)<\/script>/);
  if (!match) {
    throw new Error(`Could not find __NEXT_DATA__ for ${region} leaderboard`);
  }

  const nextData = JSON.parse(match[1]);
  const entries = nextData.props?.pageProps?.data?.entries;

  if (!entries || !Array.isArray(entries)) {
    throw new Error(`No leaderboard entries found for ${region}`);
  }

  // Normalize each entry with the URL region slug
  const players = entries.map(entry => ({
    playerName: entry.playerName,
    tag: entry.tag,
    riotRegion: entry.region,
    urlRegion: riotRegionToUrlSlug(entry.region),
    rank: entry.rank,
    games: entry.games,
    patchGames: entry.patchGames,
    leaderboardRegion: region,
  }));

  console.log(`  Found ${players.length} players in ${region.toUpperCase()}`);
  return players;
}

/**
 * Scrape all region leaderboards and save to disk.
 * Returns { buildId, players: [...all players...] }
 */
export async function scrapeLeaderboards() {
  const buildId = await getBuildId();

  const allPlayers = [];

  for (const region of REGIONS) {
    const players = await scrapeRegionLeaderboard(region);
    await writeJSON(dataPath(`leaderboard-${region}.json`), players);
    allPlayers.push(...players);
  }

  console.log(`\nTotal players scraped: ${allPlayers.length}`);

  // Save buildId for later steps
  await writeJSON(dataPath('build-id.json'), { buildId, scrapedAt: new Date().toISOString() });

  return { buildId, players: allPlayers };
}
