import { readJSON, dataPath } from './utils.js';
import { scrapeLeaderboards, getBuildId } from './scrape-leaderboard.js';
import { scrapeMatchHistories } from './scrape-matches.js';
import { scrapeMatchDetails } from './scrape-details.js';

const STEPS = ['leaderboard', 'matches', 'details'];

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    step: null,       // Run a specific step only
    regions: null,    // Filter regions (comma-separated)
    queueId: 1100,   // Default: Ranked only
  };

  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--step' && args[i + 1]) {
      options.step = args[++i];
    } else if (args[i] === '--regions' && args[i + 1]) {
      options.regions = args[++i].split(',');
    } else if (args[i] === '--queue' && args[i + 1]) {
      options.queueId = parseInt(args[++i], 10);
    }
  }

  return options;
}

async function runLeaderboard() {
  console.log('=== Step 1: Scraping Leaderboards ===\n');
  return await scrapeLeaderboards();
}

async function runMatches(providedPlayers, providedBuildId) {
  console.log('=== Step 2: Fetching Match Histories ===\n');

  let players = providedPlayers;
  let buildId = providedBuildId;

  // Load from disk if not provided
  if (!players) {
    const allPlayers = [];
    for (const region of ['na', 'kr', 'euw']) {
      const data = await readJSON(dataPath(`leaderboard-${region}.json`));
      if (data) allPlayers.push(...data);
    }
    if (allPlayers.length === 0) {
      throw new Error('No leaderboard data found. Run the leaderboard step first.');
    }
    players = allPlayers;
  }

  if (!buildId) {
    const buildData = await readJSON(dataPath('build-id.json'));
    if (buildData) {
      buildId = buildData.buildId;
    } else {
      console.log('  buildId not cached, fetching fresh...');
      buildId = await getBuildId();
    }
  }

  return await scrapeMatchHistories(players, buildId);
}

async function runDetails(providedMatchIds) {
  console.log('=== Step 3: Fetching Match Details ===\n');

  let matchIds = providedMatchIds;

  if (!matchIds) {
    const data = await readJSON(dataPath('match-ids.json'));
    if (!data || !data.ids) {
      throw new Error('No match IDs found. Run the matches step first.');
    }
    matchIds = data.ids;
  }

  return await scrapeMatchDetails(matchIds);
}

async function main() {
  const options = parseArgs();
  const startTime = Date.now();

  console.log('TFT Patch 16.4 Match Data Scraper');
  console.log('==================================\n');

  try {
    if (options.step) {
      // Run single step
      if (!STEPS.includes(options.step)) {
        console.error(`Unknown step: ${options.step}. Valid steps: ${STEPS.join(', ')}`);
        process.exit(1);
      }

      if (options.step === 'leaderboard') await runLeaderboard();
      else if (options.step === 'matches') await runMatches();
      else if (options.step === 'details') await runDetails();
    } else {
      // Run all steps
      const { buildId, players } = await runLeaderboard();
      const matchIds = await runMatches(players, buildId);
      await runDetails(matchIds);
    }

    const elapsed = ((Date.now() - startTime) / 1000 / 60).toFixed(1);
    console.log(`\nAll done! Total time: ${elapsed} minutes`);
  } catch (err) {
    console.error(`\nFatal error: ${err.message}`);
    console.error(err.stack);
    process.exit(1);
  }
}

main();
