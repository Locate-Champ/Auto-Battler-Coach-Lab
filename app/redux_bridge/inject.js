/**
 * Redux Store Bridge for MetaTFT
 *
 * This script intercepts MetaTFT's Redux store and forwards board/bench data
 * to the TFT Coach backend via WebSocket.
 *
 * USAGE:
 * 1. Open MetaTFT's main window in Overwolf
 * 2. Open Developer Tools (Ctrl+Shift+I)
 * 3. Paste this script in the Console
 * 4. Or inject via Overwolf's executeInWindow API
 *
 * DATA FLOW:
 * MetaTFT Redux Store -> This Script -> WebSocket -> Python Backend -> Overlay
 */

(function() {
  'use strict';

  const WS_URL = 'ws://127.0.0.1:8765/redux';
  const RECONNECT_INTERVAL = 3000;
  const DEBUG = true;

  function log(...args) {
    if (DEBUG) console.log('[ReduxBridge]', ...args);
  }

  function error(...args) {
    console.error('[ReduxBridge]', ...args);
  }

  // Get the Redux store from MetaTFT
  function getReduxStore() {
    // Try global window.reduxStore first
    if (window.reduxStore) {
      log('Found store at window.reduxStore');
      return window.reduxStore;
    }

    // Try Overwolf's getMainWindow
    if (typeof overwolf !== 'undefined' && overwolf.windows && overwolf.windows.getMainWindow) {
      try {
        const mainWindow = overwolf.windows.getMainWindow();
        if (mainWindow && mainWindow.reduxStore) {
          log('Found store at overwolf.windows.getMainWindow().reduxStore');
          return mainWindow.reduxStore;
        }
      } catch (e) {
        error('Failed to get main window:', e);
      }
    }

    return null;
  }

  // Extract relevant data from Redux state
  // NOTE: State is nested under 'game' key: state.game.board, not state.board
  function extractGameData(state) {
    if (!state) return null;

    // The game data is nested under state.game
    const game = state.game || state;

    const data = {
      timestamp: new Date().toISOString(),
      // Board pieces (your board)
      board: game.board?.board_pieces || {},
      // Bench pieces
      bench: game.bench?.bench_pieces || {},
      // Shop pieces
      shop: game.store?.shop_pieces || {},
      // Player info (me)
      me: {
        gold: game.me?.gold || '',
        health: game.me?.health || '',
        xp: game.me?.xp || {},
        rank: game.me?.rank || '',
        summoner_name: game.me?.summoner_name || '',
      },
      // Roster (all 8 players)
      roster: game.roster?.player_status || {},
      // Match info
      match_info: game.match_info || {},
      // Carousel
      carousel: game.carousel?.carousel_pieces || {},
      // Game info
      game_info: game.game_info || {},
      // ALL 8 players' boards (board_1 through board_8)
      board_data: game.board?.board_data || {},
    };

    return data;
  }

  // Transform board_pieces to our format
  function transformBoardPieces(boardPieces) {
    if (!boardPieces || typeof boardPieces !== 'object') return [];

    const units = [];
    for (const [cellId, unit] of Object.entries(boardPieces)) {
      if (!unit || !unit.name) continue;

      // Parse cell number: "cell_1" -> 1
      const cellMatch = cellId.match(/cell_(\d+)/);
      if (!cellMatch) continue;

      const cellNum = parseInt(cellMatch[1]);
      // Convert to row/col (7 cells per row, 4 rows)
      const row = Math.floor((cellNum - 1) / 7);
      const col = (cellNum - 1) % 7;

      units.push({
        id: cellId,
        character_id: unit.name,
        name: unit.name.replace('TFT16_', '').replace('TFT15_', '').replace('TFT14_', ''),
        stars: parseInt(unit.level) || 1,
        items: [unit.item_1, unit.item_2, unit.item_3].filter(Boolean),
        position: { row, col },
      });
    }
    return units;
  }

  // Transform bench_pieces to our format
  function transformBenchPieces(benchPieces) {
    if (!benchPieces || typeof benchPieces !== 'object') return [];

    const units = [];
    for (const [slotId, unit] of Object.entries(benchPieces)) {
      if (!unit || !unit.name) continue;

      units.push({
        id: slotId,
        character_id: unit.name,
        name: unit.name.replace('TFT16_', '').replace('TFT15_', '').replace('TFT14_', ''),
        stars: parseInt(unit.level) || 1,
        items: [unit.item_1, unit.item_2, unit.item_3].filter(Boolean),
      });
    }
    return units;
  }

  // Transform shop_pieces to our format
  function transformShopPieces(shopPieces) {
    if (!shopPieces) return [];

    const entries = Array.isArray(shopPieces) ? shopPieces.entries() : Object.entries(shopPieces);
    const units = [];

    for (const [, unit] of entries) {
      if (!unit) continue;

      const characterId = unit.name || unit.character_id || '';
      if (!characterId) continue;

      units.push({
        character_id: characterId,
        name: characterId.replace('TFT16_', '').replace('TFT15_', '').replace('TFT14_', ''),
        cost: unit.cost ?? unit.tier ?? null,
      });
    }

    return units;
  }

  // WebSocket connection management
  class ReduxBridge {
    constructor() {
      this.ws = null;
      this.store = null;
      this.unsubscribe = null;
      this.lastState = null;
      this.reconnectTimer = null;
    }

    start() {
      log('Starting Redux Bridge...');
      this.store = getReduxStore();

      if (!this.store) {
        error('Redux store not found! Retrying in 2 seconds...');
        setTimeout(() => this.start(), 2000);
        return;
      }

      log('Redux store found!');
      this.connectWebSocket();
      this.subscribeToStore();
    }

    connectWebSocket() {
      if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        return;
      }

      log(`Connecting to WebSocket: ${WS_URL}`);

      try {
        this.ws = new WebSocket(WS_URL);

        this.ws.onopen = () => {
          log('WebSocket connected');
          // Send initial state
          this.sendCurrentState();
        };

        this.ws.onclose = () => {
          log('WebSocket disconnected, reconnecting...');
          this.scheduleReconnect();
        };

        this.ws.onerror = (e) => {
          error('WebSocket error:', e);
        };

        this.ws.onmessage = (event) => {
          log('Received:', event.data);
        };
      } catch (e) {
        error('Failed to connect WebSocket:', e);
        this.scheduleReconnect();
      }
    }

    scheduleReconnect() {
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
      }
      this.reconnectTimer = setTimeout(() => {
        this.connectWebSocket();
      }, RECONNECT_INTERVAL);
    }

    subscribeToStore() {
      if (!this.store || !this.store.subscribe) {
        error('Store has no subscribe method');
        return;
      }

      log('Subscribing to Redux store changes...');

      this.unsubscribe = this.store.subscribe(() => {
        this.onStateChange();
      });

      log('Subscribed successfully');
    }

    onStateChange() {
      const state = this.store.getState();
      if (!state) return;

      // State is nested under 'game' key
      const game = state.game || state;

      // Check if board or bench changed
      const currentBoard = JSON.stringify(game.board?.board_pieces);
      const currentBench = JSON.stringify(game.bench?.bench_pieces);
      const currentShop = JSON.stringify(game.store?.shop_pieces);
      const currentMe = JSON.stringify({
        gold: game.me?.gold,
        health: game.me?.health,
        xp: game.me?.xp,
        rank: game.me?.rank,
        summoner_name: game.me?.summoner_name,
      });
      const lastBoard = this.lastState?.board;
      const lastBench = this.lastState?.bench;

      const lastShop = this.lastState?.shop;
      const lastMe = this.lastState?.me;

      if (currentBoard !== lastBoard ||
          currentBench !== lastBench ||
          currentShop !== lastShop ||
          currentMe !== lastMe) {
        log('State changed (board/bench/shop/me)');
        this.lastState = {
          board: currentBoard,
          bench: currentBench,
          shop: currentShop,
          me: currentMe,
        };
        this.sendCurrentState();
      }
    }

    sendCurrentState() {
      if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
        log('WebSocket not connected, cannot send state');
        return;
      }

      const state = this.store.getState();
      const gameData = extractGameData(state);

      if (!gameData) {
        log('No game data to send');
        return;
      }

      // Transform to our format
      const message = {
        type: 'redux_state',
        timestamp: gameData.timestamp,
        board_units: transformBoardPieces(gameData.board),
        bench_units: transformBenchPieces(gameData.bench),
        shop_units: transformShopPieces(gameData.shop),
        me: gameData.me,
        roster: gameData.roster,
        // All 8 players' boards (for scouting/opponent display)
        board_data: gameData.board_data,
        raw: {
          board: gameData.board,
          bench: gameData.bench,
          shop: gameData.shop,
        },
      };

      log('Sending state:', message.board_units.length, 'board units,',
          message.bench_units.length, 'bench units');

      this.ws.send(JSON.stringify(message));
    }

    stop() {
      log('Stopping Redux Bridge...');
      if (this.unsubscribe) {
        this.unsubscribe();
        this.unsubscribe = null;
      }
      if (this.reconnectTimer) {
        clearTimeout(this.reconnectTimer);
      }
      if (this.ws) {
        this.ws.close();
        this.ws = null;
      }
    }
  }

  // Create global instance
  if (window.__reduxBridge) {
    log('Stopping existing bridge...');
    window.__reduxBridge.stop();
  }

  window.__reduxBridge = new ReduxBridge();
  window.__reduxBridge.start();

  // Expose utility functions for debugging
  window.__getReduxState = () => {
    const store = getReduxStore();
    return store ? store.getState() : null;
  };

  // Get the game-specific state (nested under 'game' key)
  window.__getGameState = () => {
    const state = window.__getReduxState();
    return state?.game || state;
  };

  window.__getBoardData = () => {
    const state = window.__getGameState();
    return state?.board?.board_pieces || null;
  };

  window.__getBenchData = () => {
    const state = window.__getGameState();
    return state?.bench?.bench_pieces || null;
  };

  // Get ALL 8 players' boards
  window.__getAllBoards = () => {
    const state = window.__getGameState();
    return state?.board?.board_data || null;
  };

  // Get player info
  window.__getPlayerInfo = () => {
    const state = window.__getGameState();
    return state?.me || null;
  };

  log('Redux Bridge initialized. Utility functions available:');
  log('  __getReduxState() - Get full Redux state');
  log('  __getGameState() - Get game state (state.game)');
  log('  __getBoardData() - Get your board pieces');
  log('  __getBenchData() - Get your bench pieces');
  log('  __getAllBoards() - Get ALL 8 players\' boards');
  log('  __getPlayerInfo() - Get your player info (gold, health, etc)');
  log('  __reduxBridge.stop() - Stop the bridge');

})();
