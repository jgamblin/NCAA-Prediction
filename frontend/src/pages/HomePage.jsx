import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { TrendingUp, DollarSign, Target, Calendar, ArrowRight } from 'lucide-react'
import { fetchTodayGames, fetchBettingSummary, fetchHistoricalPredictions, fetchMetadata } from '../services/api'

export default function HomePage() {
  const [todayGames, setTodayGames] = useState([])
  const [bettingSummary, setBettingSummary] = useState(null)
  const [accuracy, setAccuracy] = useState(null)
  const [metadata, setMetadata] = useState(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    async function loadData() {
      try {
        const [games, betting, history, meta] = await Promise.all([
          fetchTodayGames(),
          fetchBettingSummary(),
          fetchHistoricalPredictions(),
          fetchMetadata()
        ])
        
        // Calculate accuracy from same source as Accuracy page
        const completed = history.filter(p => 
          p.game_status === 'Final' && 
          p.predicted_winner && 
          p.home_score != null && 
          p.away_score != null
        )
        
        const correct = completed.filter(p => {
          const actualWinner = p.home_score > p.away_score ? p.home_team : p.away_team
          return p.predicted_winner === actualWinner
        }).length
        
        const acc = {
          total_predictions: completed.length,
          correct_predictions: correct,
          accuracy: completed.length > 0 ? correct / completed.length : 0
        }
        
        setTodayGames(games)
        setBettingSummary(betting)
        setAccuracy(acc)
        setMetadata(meta)
      } catch (error) {
        console.error('Failed to load homepage data:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadData()
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
  
  const lastUpdated = metadata?.last_updated ? new Date(metadata.last_updated).toLocaleString() : 'Unknown'
  
  return (
    <div className="space-y-6">
      {/* Hero Section */}
      <div className="bg-gradient-to-r from-primary-600 to-primary-800 rounded-xl shadow-lg p-8 text-white">
        <h1 className="text-4xl font-bold mb-2">NCAA Basketball Predictions</h1>
        <p className="text-primary-100 text-lg">
          Machine learning powered predictions updated daily
        </p>
        <div className="mt-4 flex items-center space-x-4 text-sm">
          <div className="flex items-center space-x-2">
            <Calendar size={16} />
            <span>Last updated: {lastUpdated}</span>
          </div>
          <div className="flex items-center space-x-2">
            <Target size={16} />
            <span>{metadata?.database_stats?.total_games?.toLocaleString() || 0} games tracked</span>
          </div>
        </div>
      </div>
      
      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Accuracy Card */}
        <div className="card hover:shadow-lg transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-700">Prediction Accuracy</h3>
            <div className="p-2 bg-green-100 rounded-lg">
              <Target className="text-green-600" size={20} />
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-3xl font-bold text-gray-900">
              {accuracy ? `${(accuracy.accuracy * 100).toFixed(1)}%` : 'N/A'}
            </div>
            <p className="text-sm text-gray-600">
              {accuracy?.correct_predictions || 0} of {accuracy?.total_predictions || 0} correct
            </p>
            <Link to="/accuracy" className="text-primary-600 text-sm font-medium flex items-center space-x-1 hover:underline">
              <span>View More</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
        
        {/* Betting Performance Card */}
        <div className="card hover:shadow-lg transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-700">Betting Performance</h3>
            <div className="p-2 bg-blue-100 rounded-lg">
              <DollarSign className="text-blue-600" size={20} />
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-3xl font-bold text-gray-900">
              {bettingSummary && bettingSummary.total_bets > 0
                ? `${(bettingSummary.win_rate * 100).toFixed(1)}%`
                : 'N/A'
              }
            </div>
            <p className="text-sm text-gray-600">
              {bettingSummary?.wins || 0}W - {bettingSummary?.losses || 0}L
              {bettingSummary && bettingSummary.total_bets > 0 && (
                <span className={`ml-2 ${bettingSummary.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  ({bettingSummary.total_profit >= 0 ? '+' : ''}{bettingSummary.total_profit?.toFixed(2)} units)
                </span>
              )}
            </p>
            <Link to="/betting" className="text-primary-600 text-sm font-medium flex items-center space-x-1 hover:underline">
              <span>View betting analytics</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
        
        {/* Today's Games Card */}
        <div className="card hover:shadow-lg transition-shadow">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-700">Today's Games</h3>
            <div className="p-2 bg-purple-100 rounded-lg">
              <TrendingUp className="text-purple-600" size={20} />
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-3xl font-bold text-gray-900">
              {todayGames.length}
            </div>
            <p className="text-sm text-gray-600">
              {todayGames.length === 0 ? 'No games scheduled' : 'games with predictions'}
            </p>
            <Link to="/predictions" className="text-primary-600 text-sm font-medium flex items-center space-x-1 hover:underline">
              <span>View all predictions</span>
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </div>
      
      {/* Today's Games List */}
      {todayGames.length > 0 ? (
        <div className="card">
          <h2 className="text-2xl font-bold mb-4">Today's Games</h2>
          <div className="space-y-3">
            {todayGames.slice(0, 5).map((game) => {
              const isFinished = game.game_status === 'Final'
              const hasPrediction = game.predicted_winner && game.confidence
              
              return (
                <div 
                  key={game.game_id} 
                  className="card hover:shadow-lg transition-shadow"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      {/* Game matchup - similar to History page */}
                      <div className="flex items-center space-x-4 mb-2">
                        <span className="font-medium">{game.away_team}</span>
                        {isFinished && <span className="text-gray-900 font-semibold">{game.away_score}</span>}
                        <span className="text-gray-400">@</span>
                        <span className="font-medium">{game.home_team}</span>
                        {isFinished && <span className="text-gray-900 font-semibold">{game.home_score}</span>}
                      </div>
                      
                      {/* Prediction info - matching History page style */}
                      {hasPrediction ? (
                        <div className="text-sm">
                          <span className="text-gray-600">Predicted: </span>
                          <span className="font-semibold">{game.predicted_winner}</span>
                          <span className="text-gray-600 ml-3">Confidence: </span>
                          <span className="font-semibold">{(game.confidence * 100).toFixed(1)}%</span>
                        </div>
                      ) : (
                        <div className="text-sm text-gray-500">
                          No prediction available
                        </div>
                      )}
                    </div>
                    
                    {/* Status badge on right */}
                    <div className="flex items-center space-x-3">
                      {isFinished ? (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-700">
                          Final
                        </span>
                      ) : (
                        <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-700">
                          Scheduled
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
          {todayGames.length > 5 && (
            <Link 
              to="/predictions"
              className="mt-4 block text-center text-primary-600 hover:text-primary-700 font-medium"
            >
              View all {todayGames.length} games →
            </Link>
          )}
        </div>
      ) : (
        <div className="card text-center py-12">
          <Calendar className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-xl font-semibold text-gray-700 mb-2">No games today</h3>
          <p className="text-gray-600 mb-4">Check back tomorrow for new predictions</p>
          <Link to="/predictions" className="btn btn-primary inline-flex items-center space-x-2">
            <span>View upcoming games</span>
            <ArrowRight size={16} />
          </Link>
        </div>
      )}
    </div>
  )
}
