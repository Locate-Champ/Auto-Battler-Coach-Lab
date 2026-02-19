import fs from 'fs/promises';
import path from 'path';

import { fileURLToPath } from 'url';
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DATA_DIR = path.join(__dirname, 'data');

/**
 * Sleep for given milliseconds.
 */
export function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Fetch with retry and exponential backoff.
 */
export async function fetchWithRetry(url, { maxRetries = 3, baseDelay = 500, timeout = 30000 } = {}) {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeout);

      const res = await fetch(url, {
        signal: controller.signal,
        headers: {
          'User-Agent': 'TFT-Coach-Scraper/1.0 (personal project)',
          'Accept': 'application/json, text/html',
        },
      });

      clearTimeout(timer);

      if (res.status === 429 || res.status === 503) {
        const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 500;
        console.warn(`  Rate limited (${res.status}) on ${url}, retrying in ${Math.round(delay)}ms...`);
        await sleep(delay);
        continue;
      }

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`);
      }

      return res;
    } catch (err) {
      if (attempt === maxRetries) {
        throw new Error(`Failed after ${maxRetries + 1} attempts: ${url} - ${err.message}`);
      }
      const delay = baseDelay * Math.pow(2, attempt) + Math.random() * 500;
      console.warn(`  Error on ${url}: ${err.message}, retrying in ${Math.round(delay)}ms...`);
      await sleep(delay);
    }
  }
}

/**
 * Rate-limited concurrent executor.
 * Processes items with concurrency limit and delay between requests.
 */
export async function rateLimitedMap(items, fn, { concurrency = 5, delayMs = 300, label = 'items' } = {}) {
  const results = [];
  let completed = 0;
  let errors = 0;
  const total = items.length;
  const startTime = Date.now();

  // Process in batches
  for (let i = 0; i < items.length; i += concurrency) {
    const batch = items.slice(i, i + concurrency);
    const batchResults = await Promise.allSettled(
      batch.map(item => fn(item))
    );

    for (const result of batchResults) {
      if (result.status === 'fulfilled') {
        results.push(result.value);
      } else {
        errors++;
        results.push(null);
      }
      completed++;
    }

    // Progress log every 50 items or at end
    if (completed % 50 === 0 || completed === total) {
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1);
      const rate = (completed / (Date.now() - startTime) * 1000).toFixed(1);
      console.log(`  [${completed}/${total}] ${label} processed (${errors} errors, ${elapsed}s, ${rate}/s)`);
    }

    // Delay between batches (not after the last one)
    if (i + concurrency < items.length) {
      await sleep(delayMs);
    }
  }

  return results;
}

/**
 * Map Riot API region codes to tactics.tools URL slugs.
 */
export function riotRegionToUrlSlug(riotRegion) {
  const map = {
    'na1': 'na',
    'kr': 'kr',
    'euw1': 'euw',
    'eun1': 'eune',
    'br1': 'br',
    'jp1': 'jp',
    'la1': 'lan',
    'la2': 'las',
    'oc1': 'oce',
    'tr1': 'tr',
    'ru': 'ru',
    'ph2': 'ph',
    'sg2': 'sg',
    'th2': 'th',
    'tw2': 'tw',
    'vn2': 'vn',
  };
  return map[riotRegion] || riotRegion;
}

/**
 * Read JSON file, return null if it doesn't exist.
 */
export async function readJSON(filepath) {
  try {
    const content = await fs.readFile(filepath, 'utf-8');
    return JSON.parse(content);
  } catch {
    return null;
  }
}

/**
 * Write JSON file, creating directories as needed.
 */
export async function writeJSON(filepath, data) {
  await fs.mkdir(path.dirname(filepath), { recursive: true });
  await fs.writeFile(filepath, JSON.stringify(data, null, 2), 'utf-8');
}

/**
 * Append a line to a JSONL file.
 */
export async function appendJSONL(filepath, data) {
  await fs.mkdir(path.dirname(filepath), { recursive: true });
  await fs.appendFile(filepath, JSON.stringify(data) + '\n', 'utf-8');
}

/**
 * Get the data directory path.
 */
export function getDataDir() {
  return DATA_DIR;
}

/**
 * Get path within data directory.
 */
export function dataPath(...segments) {
  return path.join(DATA_DIR, ...segments);
}

/**
 * Check if a file exists.
 */
export async function fileExists(filepath) {
  try {
    await fs.access(filepath);
    return true;
  } catch {
    return false;
  }
}
