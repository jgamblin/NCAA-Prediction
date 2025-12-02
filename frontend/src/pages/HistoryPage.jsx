import { useState, useEffect } from 'react'
import { fetchPredictionHistory } from '../services/api'
import { History, CheckCircle, XCircle } from 'lucide-react'

export default function HistoryPage() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    async function loadHistory() {
      try {
        const data = await fetchPredictionHistory()
        setHistory(data)
      } catch (error) {
        console.error('Failed to load history:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadHistory()
  }, [])
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Prediction History</h1>
        <p className="text-gray-600 mt-1">Last {history.length} predictions with results</p>
      </div>
      
      {history.length === 0 ? (
        <div className="card text-center py-12">
          <History className="mx-auto text-gray-400 mb-4" size={48} />
          <p className="text-gray-600">No prediction history available</p>
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((pred) => {
            // Calculate the actual winner
            const actualWinner = pred.home_score > pred.away_score ? pred.home_team : pred.away_team
            // Check if our prediction matches the actual winner
            const isCorrect = pred.predicted_winner === actualWinner
            
            return (
              <div key={pred.id} className="card hover:shadow-lg transition-shadow">
                <div className="flex items-center justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-4">
                      <div className="text-sm text-gray-500">
                        {new Date(pred.game_date).toLocaleDateString()}
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="font-medium">{pred.away_team}</span>
                        <span className="text-gray-500">{pred.away_score}</span>
                      </div>
                      <span className="text-gray-400">@</span>
                      <div className="flex items-center space-x-2">
                        <span className="font-medium">{pred.home_team}</span>
                        <span className="text-gray-500">{pred.home_score}</span>
                      </div>
                    </div>
                    <div className="mt-2 flex items-center space-x-4 text-sm">
                      <span className="text-gray-600">
                        Predicted: <span className="font-semibold">{pred.predicted_winner}</span>
                      </span>
                      <span className="text-gray-600">
                        Confidence: <span className="font-semibold">{(pred.confidence * 100).toFixed(1)}%</span>
                      </span>
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-3">
                    {isCorrect ? (
                      <div className="flex items-center space-x-2 text-green-600">
                        <CheckCircle size={24} />
                        <span className="font-semibold">Correct</span>
                      </div>
                    ) : (
                      <div className="flex items-center space-x-2 text-red-600">
                        <XCircle size={24} />
                        <span className="font-semibold">Incorrect</span>
                      </div>
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
