import { fetchWithRetry, readJSON, writeJSON, appendJSONL, dataPath, rateLimitedMap, fileExists } from './utils.js';

/**
 * Fetch full match detail from the tft.tools API.
 */
async function fetchMatchDetail(matchId) {
  const cacheFile = dataPath('match-details', `${matchId}.json`);

  // Check local cache first
  if (await fileExists(cacheFile)) {
    return await readJSON(cacheFile);
  }

  const url = `https://api.tft.tools/match/${matchId}`;

  try {
    const res = await fetchWithRetry(url, { maxRetries: 3, baseDelay: 500 });
    const data = await res.json();

    // Cache to disk for resume capability
    await writeJSON(cacheFile, data);

    return data;
  } catch (err) {
    return { matchId, error: err.message };
  }
}

/**
 * Transform raw match detail into clean output format.
 */
function transformMatch(raw) {
  if (!raw || raw.error || !raw.info) {
    return null;
  }

  const info = raw.info;
  const ranks = raw.ranks || {};

  const participants = (info.participants || []).map(p => {
    const rankInfo = ranks[p.name] || ranks[`${p.name}#${p.tag}`] || null;

    return {
      name: p.name,
      tag: p.tag,
      placement: p.placement,
      level: p.level,
      lastRound: p.lastRound,
      playersEliminated: p.playersEliminated || 0,
      totalDamageToPlayers: p.totalDamageToPlayers || 0,
      rank: rankInfo ? rankInfo[0] : null,
      lp: rankInfo ? rankInfo[1] : null,
      traits: (p.traits || []).map(t => ({
        name: t.name,
        numUnits: t.numUnits,
        currentTier: t.currentTier,
      })),
      units: (p.units || []).map(u => ({
        id: u.id,
        starLevel: u.tier,
        items: u.items2 || u.items || [],
        rarity: u.rarity,
      })),
    };
  });

  return {
    matchId: raw.id || raw.matchId || info.matchId,
    dateTime: info.dateTime,
    duration: info.duration,
    patch: info.patch,
    queueId: info.queueId,
    mode: info.queueId === 1100 ? 'Ranked' : info.queueId === 1090 ? 'Normal' : `Queue-${info.queueId}`,
    participants,
  };
}

/**
 * Fetch all match details, transform, and write output.
 * Supports resume via cached individual match files.
 */
export async function scrapeMatchDetails(matchIds) {
  console.log(`\nFetching details for ${matchIds.length} unique matches...`);

  const outputFile = dataPath('output.jsonl');
  const errorFile = dataPath('match-detail-errors.json');
  const errors = [];
  let written = 0;

  // Check how many are already cached
  let cachedCount = 0;
  for (const id of matchIds.slice(0, 100)) {
    if (await fileExists(dataPath('match-details', `${id}.json`))) {
      cachedCount++;
    }
  }
  if (cachedCount > 0) {
    console.log(`  Sample check: ${cachedCount}/100 already cached locally`);
  }

  // Process in batches to control memory and write output incrementally
  const BATCH_SIZE = 100;
  for (let i = 0; i < matchIds.length; i += BATCH_SIZE) {
    const batch = matchIds.slice(i, i + BATCH_SIZE);

    const results = await rateLimitedMap(batch, async (matchId) => {
      const raw = await fetchMatchDetail(matchId);
      return { matchId, raw };
    }, {
      concurrency: 5,
      delayMs: 250,
      label: `matches (batch ${Math.floor(i / BATCH_SIZE) + 1}/${Math.ceil(matchIds.length / BATCH_SIZE)})`,
    });

    // Transform and write results
    for (const result of results) {
      if (!result || !result.raw) continue;

      if (result.raw.error) {
        errors.push({ matchId: result.matchId, error: result.raw.error });
        continue;
      }

      const transformed = transformMatch(result.raw);
      if (transformed) {
        await appendJSONL(outputFile, transformed);
        written++;
      } else {
        errors.push({ matchId: result.matchId, error: 'Transform returned null' });
      }
    }

    console.log(`  Written ${written} matches to output so far`);
  }

  console.log(`\nMatch detail scraping complete:`);
  console.log(`  Total matches written: ${written}`);
  console.log(`  Errors: ${errors.length}`);

  if (errors.length > 0) {
    await writeJSON(errorFile, errors);
    console.log(`  Error log: ${errorFile}`);
  }

  // Write summary
  await writeJSON(dataPath('scrape-summary.json'), {
    completedAt: new Date().toISOString(),
    totalMatchIds: matchIds.length,
    matchesWritten: written,
    errors: errors.length,
    outputFile,
  });

  return { written, errors: errors.length };
}
