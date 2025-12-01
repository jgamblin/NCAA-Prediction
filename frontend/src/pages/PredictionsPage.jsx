import { useState, useEffect } from 'react'
import { fetchUpcomingGames } from '../services/api'
import { TrendingUp, Trophy, AlertCircle } from 'lucide-react'

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all') // all, with-predictions, no-predictions
  
  useEffect(() => {
    async function loadPredictions() {
      try {
        const data = await fetchUpcomingGames()
        setPredictions(data)
      } catch (error) {
        console.error('Failed to load predictions:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadPredictions()
  }, [])
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading predictions...</p>
        </div>
      </div>
    )
  }
  
  const getConfidenceLabel = (confidence) => {
    if (confidence >= 0.70) return { label: 'High', color: 'green' }
    if (confidence >= 0.60) return { label: 'Medium', color: 'yellow' }
    return { label: 'Low', color: 'gray' }
  }
  
  const filteredPredictions = predictions.filter(game => {
    if (filter === 'all') return true
    if (filter === 'with-predictions') return game.predicted_winner && game.confidence
    if (filter === 'no-predictions') return !game.predicted_winner
    return true
  })
  
  const gamesWithPredictions = predictions.filter(g => g.predicted_winner && g.confidence).length
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Upcoming Games</h1>
          <p className="text-gray-600 mt-1">
            {predictions.length} scheduled games ({gamesWithPredictions} with predictions)
          </p>
        </div>
        
        {/* Filter Buttons */}
        <div className="flex items-center space-x-2">
          <button
            onClick={() => setFilter('all')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              filter === 'all'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            All Games
          </button>
          <button
            onClick={() => setFilter('with-predictions')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              filter === 'with-predictions'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            With Predictions
          </button>
          <button
            onClick={() => setFilter('no-predictions')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              filter === 'no-predictions'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            No Predictions
          </button>
        </div>
      </div>
      
      {filteredPredictions.length === 0 ? (
        <div className="card text-center py-12">
          <AlertCircle className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-xl font-semibold text-gray-700 mb-2">No predictions available</h3>
          <p className="text-gray-600">Check back soon for new game predictions</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredPredictions.map((game) => {
            const hasPrediction = game.predicted_winner && game.confidence
            
            return (
              <div key={game.game_id} className="card hover:shadow-lg transition-shadow">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    {/* Game matchup - matching Home page style */}
                    <div className="flex items-center space-x-4 mb-2">
                      <span className="text-sm text-gray-500">{game.date}</span>
                      <span className="font-medium">{game.away_team}</span>
                      <span className="text-gray-400">@</span>
                      <span className="font-medium">{game.home_team}</span>
                    </div>
                    
                    {/* Prediction info - matching Home page style */}
                    {hasPrediction ? (
                      <div className="text-sm">
                        <span className="text-gray-600">Predicted: </span>
                        <span className="font-semibold">{game.predicted_winner}</span>
                        <span className="text-gray-600 ml-3">Confidence: </span>
                        <span className="font-semibold">{(game.confidence * 100).toFixed(1)}%</span>
                      </div>
                    ) : (
                      <div className="text-sm text-gray-500">
                        No prediction available (insufficient team data)
                      </div>
                    )}
                  </div>
                  
                  {/* Status badge on right */}
                  <div className="flex items-center space-x-3">
                    {hasPrediction ? (
                      <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-700">
                        ✓ Predicted
                      </span>
                    ) : (
                      <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-600">
                        Scheduled
                      </span>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
