import { useState, useEffect } from 'react'
import { fetchUpcomingGames } from '../services/api'
import { AlertCircle } from 'lucide-react'
import GameCard from '../components/GameCard'

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('with-predictions')
  const [dateFilter, setDateFilter] = useState('today')
  
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
  
  // Date filtering
  const getFilteredByDate = () => {
    if (dateFilter === 'all') return predictions
    
    const today = new Date().toISOString().split('T')[0]
    
    if (dateFilter === 'today') {
      return predictions.filter(g => g.date === today)
    }
    
    if (dateFilter === 'week') {
      const weekFromNow = new Date()
      weekFromNow.setDate(weekFromNow.getDate() + 7)
      const weekDate = weekFromNow.toISOString().split('T')[0]
      return predictions.filter(g => g.date >= today && g.date <= weekDate)
    }
    
    return predictions
  }
  
  const dateFilteredGames = getFilteredByDate()
  
  const filteredPredictions = dateFilteredGames.filter(game => {
    if (filter === 'all') return true
    if (filter === 'with-predictions') return game.predicted_winner && game.confidence
    if (filter === 'no-predictions') return !game.predicted_winner
    return true
  })
  
  const gamesWithPredictions = dateFilteredGames.filter(g => g.predicted_winner && g.confidence).length
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-1">
          {dateFilter === 'today' ? "Today's Games" : 
           dateFilter === 'week' ? "This Week's Games" : 
           "All Upcoming Games"}
        </h1>
        <p className="text-gray-600">
          {dateFilteredGames.length} games ({gamesWithPredictions} with predictions)
        </p>
      </div>

      {/* Date Filter Buttons */}
      <div className="flex items-center flex-wrap gap-2">
        <span className="text-sm text-gray-600 mr-2">Show:</span>
        <button
          onClick={() => setDateFilter('today')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            dateFilter === 'today'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          Today
        </button>
        <button
          onClick={() => setDateFilter('week')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            dateFilter === 'week'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          This Week
        </button>
        <button
          onClick={() => setDateFilter('all')}
          className={`px-4 py-2 rounded-lg font-medium transition-colors ${
            dateFilter === 'all'
              ? 'bg-primary-600 text-white'
              : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
          }`}
        >
          All Upcoming
        </button>
      </div>

      {/* Prediction Filter Buttons */}
      <div className="flex items-center flex-wrap gap-2">
        <span className="text-sm text-gray-600 mr-2">Filter:</span>
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
      
      {filteredPredictions.length === 0 ? (
        <div className="card text-center py-12">
          <AlertCircle className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-xl font-semibold text-gray-700 mb-2">No predictions available</h3>
          <p className="text-gray-600">Check back soon for new game predictions</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filteredPredictions.map((game) => (
            <GameCard 
              key={game.game_id} 
              game={game}
              showBadge={true}
              badgeType="predicted"
            />
          ))}
        </div>
      )}
    </div>
  )
}
