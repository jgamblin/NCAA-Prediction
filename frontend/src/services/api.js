/**
 * API Service - Fetches data from static JSON files
 * No backend API needed - all data is pre-generated and served as static files
 */

// Use base path from Vite config for correct routing
const BASE_URL = `${import.meta.env.BASE_URL}data`.replace('//', '/'); // Handles base path correctly

/**
 * Generic fetch function with error handling
 */
async function fetchJSON(filename) {
  try {
    const response = await fetch(`${BASE_URL}/${filename}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    return await response.json();
  } catch (error) {
    console.error(`Failed to fetch ${filename}:`, error);
    throw error;
  }
}

/**
 * Fetch upcoming game predictions (games with predictions only)
 */
export async function fetchPredictions() {
  return fetchJSON('predictions.json');
}

/**
 * Fetch all upcoming scheduled games (with or without predictions)
 */
export async function fetchUpcomingGames() {
  return fetchJSON('upcoming_games.json');
}

/**
 * Fetch today's games with predictions
 */
export const fetchTodayGames = () => fetchJSON('today_games.json');

/**
 * Fetch prediction history (last 100 games)
 */
export const fetchPredictionHistory = () => fetchJSON('prediction_history.json');

/**
 * Fetch overall betting summary
 */
export const fetchBettingSummary = () => fetchJSON('betting_summary.json');

/**
 * Fetch betting performance by strategy
 */
export const fetchBettingByStrategy = () => fetchJSON('betting_by_strategy.json');

/**
 * Fetch betting performance by confidence level
 */
export const fetchBettingByConfidence = () => fetchJSON('betting_by_confidence.json');

/**
 * Fetch value betting opportunities
 */
export const fetchValueBets = () => fetchJSON('value_bets.json');

/**
 * Fetch cumulative profit data for charts
 */
export const fetchCumulativeProfit = () => fetchJSON('cumulative_profit.json');

/**
 * Fetch overall prediction accuracy
 */
export const fetchAccuracyOverall = () => fetchJSON('accuracy_overall.json');

/**
 * Fetch high-confidence prediction accuracy
 */
export const fetchAccuracyHighConfidence = () => fetchJSON('accuracy_high_confidence.json');

/**
 * Fetch top teams
 */
export const fetchTopTeams = () => fetchJSON('top_teams.json');

/**
 * Fetch metadata (last update time, stats, etc.)
 */
export const fetchMetadata = () => fetchJSON('metadata.json');

/**
 * Fetch all data at once (for initial load)
 */
export async function fetchAllData() {
  try {
    const [
      predictions,
      todayGames,
      bettingSummary,
      accuracyOverall,
      metadata
    ] = await Promise.all([
      fetchPredictions().catch(() => []),
      fetchTodayGames().catch(() => []),
      fetchBettingSummary().catch(() => null),
      fetchAccuracyOverall().catch(() => null),
      fetchMetadata().catch(() => null)
    ]);

    return {
      predictions,
      todayGames,
      bettingSummary,
      accuracyOverall,
      metadata
    };
  } catch (error) {
    console.error('Failed to fetch all data:', error);
    throw error;
  }
}
