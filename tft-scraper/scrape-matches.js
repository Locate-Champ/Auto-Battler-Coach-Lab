import { fetchWithRetry, readJSON, writeJSON, dataPath, rateLimitedMap, sleep } from './utils.js';
import { getBuildId } from './scrape-leaderboard.js';

const PATCH_CODE = 16030; // Patch 16.4
const RANKED_QUEUE_ID = 1100;

/**
 * Fetch match history for a single player.
 * Returns array of match IDs that match patch 16.4.
 */
async function fetchPlayerMatches(player, buildId) {
  const { playerName, tag, urlRegion } = player;
  const encodedName = encodeURIComponent(playerName);
  const encodedTag = encodeURIComponent(tag);

  const url = `https://tactics.tools/_next/data/${buildId}/en/player/${urlRegion}/${encodedName}/${encodedTag}.json?slug=${urlRegion}&slug=${encodedName}&slug=${encodedTag}`;

  try {
    const res = await fetchWithRetry(url, { maxRetries: 2, baseDelay: 1000 });
    const data = await res.json();

    const matches = data.pageProps?.initialData?.matches;
    if (!matches || !Array.isArray(matches)) {
      return { player, matchIds: [], error: 'No matches array in response' };
    }

    // Filter for patch 16.4 ranked matches
    const patchMatches = matches.filter(m => m.patch === PATCH_CODE);

    const matchIds = patchMatches.map(m => m.id);

    return { player, matchIds, total: matches.length, patchTotal: matchIds.length };
  } catch (err) {
    return { player, matchIds: [], error: err.message };
  }
}

/**
 * Scrape match histories for all players, deduplicate match IDs.
 * Can resume from a previous partial run.
 */
export async function scrapeMatchHistories(players, buildId) {
  console.log(`\nFetching match histories for ${players.length} players...`);
  console.log(`Filtering for patch code: ${PATCH_CODE} (patch 16.4)`);

  // Check for existing progress
  const progressFile = dataPath('match-progress.json');
  let progress = await readJSON(progressFile) || { completed: [], matchIds: new Set(), errors: [] };

  // Convert matchIds back to Set if loaded from JSON
  if (Array.isArray(progress.matchIds)) {
    progress.matchIds = new Set(progress.matchIds);
  }

  const completedNames = new Set(progress.completed.map(p => `${p.urlRegion}/${p.playerName}#${p.tag}`));
  const remaining = players.filter(p => !completedNames.has(`${p.urlRegion}/${p.playerName}#${p.tag}`));

  if (remaining.length < players.length) {
    console.log(`  Resuming: ${players.length - remaining.length} already done, ${remaining.length} remaining`);
    console.log(`  ${progress.matchIds.size} unique match IDs so far`);
  }

  let batchCount = 0;
  const SAVE_EVERY = 100;

  const results = await rateLimitedMap(remaining, async (player) => {
    const result = await fetchPlayerMatches(player, buildId);

    // Track results
    if (result.error) {
      progress.errors.push({ player: `${player.playerName}#${player.tag}`, region: player.urlRegion, error: result.error });
    } else {
      for (const id of result.matchIds) {
        progress.matchIds.add(id);
      }
    }
    progress.completed.push(player);
    batchCount++;

    // Periodic save
    if (batchCount % SAVE_EVERY === 0) {
      await saveProgress(progress, progressFile);
    }

    return result;
  }, {
    concurrency: 3,
    delayMs: 400,
    label: 'players',
  });

  // Final save
  await saveProgress(progress, progressFile);

  const allMatchIds = [...progress.matchIds];
  console.log(`\nMatch history scraping complete:`);
  console.log(`  Total unique match IDs: ${allMatchIds.length}`);
  console.log(`  Errors: ${progress.errors.length}`);

  // Save deduplicated match IDs
  await writeJSON(dataPath('match-ids.json'), {
    count: allMatchIds.length,
    scrapedAt: new Date().toISOString(),
    patch: PATCH_CODE,
    ids: allMatchIds,
  });

  // Save error log
  if (progress.errors.length > 0) {
    await writeJSON(dataPath('match-history-errors.json'), progress.errors);
  }

  return allMatchIds;
}

async function saveProgress(progress, filepath) {
  await writeJSON(filepath, {
    completed: progress.completed,
    matchIds: [...progress.matchIds],
    errors: progress.errors,
  });
}
