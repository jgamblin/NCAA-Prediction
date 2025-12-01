import { useState, useEffect } from 'react'
import { fetchPredictions } from '../services/api'
import { TrendingUp, Trophy, AlertCircle } from 'lucide-react'

export default function PredictionsPage() {
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all') // all, high, medium, low
  
  useEffect(() => {
    async function loadPredictions() {
      try {
        const data = await fetchPredictions()
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
  
  const filteredPredictions = predictions.filter(pred => {
    if (filter === 'all') return true
    const { label } = getConfidenceLabel(pred.confidence)
    return label.toLowerCase() === filter
  })
  
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Upcoming Predictions</h1>
          <p className="text-gray-600 mt-1">{predictions.length} games with predictions</p>
        </div>
        
        {/* Filter Buttons */}
        <div className="flex items-center space-x-2">
          {['all', 'high', 'medium', 'low'].map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-lg font-medium capitalize transition-colors ${
                filter === f
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>
      
      {filteredPredictions.length === 0 ? (
        <div className="card text-center py-12">
          <AlertCircle className="mx-auto text-gray-400 mb-4" size={48} />
          <h3 className="text-xl font-semibold text-gray-700 mb-2">No predictions available</h3>
          <p className="text-gray-600">Check back soon for new game predictions</p>
        </div>
      ) : (
        <div className="grid gap-4">
          {filteredPredictions.map((prediction) => {
            const { label, color } = getConfidenceLabel(prediction.confidence)
            const badgeColors = {
              green: 'badge-success',
              yellow: 'badge-warning',
              gray: 'badge badge-info'
            }
            
            return (
              <div key={prediction.game_id} className="card hover:shadow-lg transition-shadow">
                <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0">
                  {/* Teams */}
                  <div className="flex-1">
                    <div className="flex items-center space-x-6">
                      <div className="text-center flex-1">
                        <p className="text-lg font-semibold text-gray-900">{prediction.away_team}</p>
                        <p className="text-sm text-gray-500">Away</p>
                        {prediction.away_moneyline && (
                          <p className="text-xs text-gray-600 mt-1">
                            {prediction.away_moneyline > 0 ? '+' : ''}{prediction.away_moneyline}
                          </p>
                        )}
                      </div>
                      
                      <div className="flex flex-col items-center">
                        <span className="text-2xl text-gray-400">@</span>
                        <span className="text-xs text-gray-500">{prediction.date}</span>
                      </div>
                      
                      <div className="text-center flex-1">
                        <p className="text-lg font-semibold text-gray-900">{prediction.home_team}</p>
                        <p className="text-sm text-gray-500">Home</p>
                        {prediction.home_moneyline && (
                          <p className="text-xs text-gray-600 mt-1">
                            {prediction.home_moneyline > 0 ? '+' : ''}{prediction.home_moneyline}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {/* Prediction */}
                  <div className="md:w-64 text-right">
                    <div className="flex items-center justify-end space-x-3">
                      <div>
                        <div className="flex items-center justify-end space-x-2 mb-1">
                          <Trophy className="text-primary-600" size={18} />
                          <span className="font-bold text-lg text-gray-900">
                            {prediction.predicted_winner}
                          </span>
                        </div>
                        <div className="text-2xl font-bold text-primary-600">
                          {(prediction.confidence * 100).toFixed(1)}%
                        </div>
                        <span className={`${badgeColors[color]} mt-2`}>
                          {label} Confidence
                        </span>
                      </div>
                    </div>
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
