import { useState, useEffect, useMemo } from 'react'
import { fetchHistoricalPredictions } from '../services/api'
import { TrendingUp, Target, CheckCircle, XCircle, BarChart3 } from 'lucide-react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts'

export default function AccuracyPage() {
  const [predictions, setPredictions] = useState([])
  const [loading, setLoading] = useState(true)
  const [timeframe, setTimeframe] = useState('all') // all, month, week

  useEffect(() => {
    async function loadData() {
      try {
        const data = await fetchHistoricalPredictions()
        // Filter only completed games with results
        const completed = data.filter(p => 
          p.game_status === 'Final' && 
          p.predicted_winner && 
          p.home_score != null && 
          p.away_score != null
        )
        
        // Calculate if prediction was correct and normalize field names
        completed.forEach(p => {
          const actualWinner = p.home_score > p.away_score ? p.home_team : p.away_team
          p.correct = p.predicted_winner === actualWinner
          // Normalize date field name (data has 'game_date', we need 'date')
          if (!p.date && p.game_date) {
            p.date = p.game_date
          }
        })
        
        // Deduplicate by game_id (keep most recent prediction per game)
        const uniquePredictions = Object.values(
          completed.reduce((acc, p) => {
            // Keep the one with the highest id (most recent)
            if (!acc[p.game_id] || p.id > acc[p.game_id].id) {
              acc[p.game_id] = p
            }
            return acc
          }, {})
        )
        
        setPredictions(uniquePredictions)
      } catch (error) {
        console.error('Failed to load predictions:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadData()
  }, [])

  // ALL HOOKS MUST COME BEFORE ANY CONDITIONAL RETURNS
  // Filter by timeframe - memoized to recalculate when timeframe or predictions change
  const filtered = useMemo(() => {
    if (timeframe === 'all') return predictions
    
    const now = new Date()
    const cutoffDate = new Date()
    
    if (timeframe === 'month') {
      cutoffDate.setDate(cutoffDate.getDate() - 30)
    } else if (timeframe === 'week') {
      cutoffDate.setDate(cutoffDate.getDate() - 7)
    }
    
    return predictions.filter(p => {
      if (!p.date) return false
      const predDate = new Date(p.date)
      return !isNaN(predDate.getTime()) && predDate >= cutoffDate
    })
  }, [timeframe, predictions])
  
  // Calculate overall stats
  const totalPredictions = filtered.length
  const correctPredictions = filtered.filter(p => p.correct).length
  const overallAccuracy = totalPredictions > 0 
    ? (correctPredictions / totalPredictions * 100).toFixed(1) 
    : 0

  // Accuracy by confidence level - memoized
  const accuracyByConfidence = useMemo(() => {
    const confidenceBuckets = [
      { label: 'High (≥70%)', min: 0.70, max: 1.0, color: '#10b981' },
      { label: 'Medium (60-70%)', min: 0.60, max: 0.70, color: '#f59e0b' },
      { label: 'Low (<60%)', min: 0, max: 0.60, color: '#ef4444' }
    ]

    return confidenceBuckets.map(bucket => {
      const bucketPreds = filtered.filter(p => 
        p.confidence >= bucket.min && p.confidence < bucket.max
      )
      const correct = bucketPreds.filter(p => p.correct).length
      const accuracy = bucketPreds.length > 0 
        ? (correct / bucketPreds.length * 100).toFixed(1)
        : 0
      
      return {
        name: bucket.label,
        accuracy: parseFloat(accuracy),
        total: bucketPreds.length,
        correct: correct,
        color: bucket.color
      }
    }).filter(b => b.total > 0)
  }, [filtered])

  // Accuracy over time (by week) - memoized
  const weeklyChart = useMemo(() => {
    const weeklyData = {}
    filtered.forEach(p => {
      // Skip if date is invalid
      if (!p.date) return
      
      const date = new Date(p.date)
      // Check if date is valid
      if (isNaN(date.getTime())) return
      
      // Get Monday of that week
      const monday = new Date(date)
      monday.setDate(date.getDate() - date.getDay() + 1)
      const weekKey = monday.toISOString().split('T')[0]
      
      if (!weeklyData[weekKey]) {
        weeklyData[weekKey] = { total: 0, correct: 0 }
      }
      weeklyData[weekKey].total++
      if (p.correct) weeklyData[weekKey].correct++
    })

    return Object.entries(weeklyData)
      .map(([week, data]) => ({
        week: week,
        accuracy: data.total > 0 ? (data.correct / data.total * 100).toFixed(1) : 0,
        total: data.total
      }))
      .sort((a, b) => a.week.localeCompare(b.week))
      .slice(-12) // Last 12 weeks
  }, [filtered])

  // Recent predictions - memoized
  const recentPredictions = useMemo(() => {
    return [...filtered]
      .sort((a, b) => new Date(b.date) - new Date(a.date))
      .slice(0, 20)
  }, [filtered])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading accuracy data...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Prediction Accuracy</h1>
          <p className="text-gray-600 mt-1">Track performance and analyze prediction quality</p>
        </div>
        
        {/* Timeframe filters */}
        <div className="flex items-center space-x-2">
          <span className="text-sm text-gray-600 mr-2">Period:</span>
          <button
            onClick={() => setTimeframe('week')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              timeframe === 'week'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Last 7 Days
          </button>
          <button
            onClick={() => setTimeframe('month')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              timeframe === 'month'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            Last 30 Days
          </button>
          <button
            onClick={() => setTimeframe('all')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              timeframe === 'all'
                ? 'bg-primary-600 text-white'
                : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
            }`}
          >
            All Time
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="card bg-gradient-to-br from-green-50 to-green-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-green-600 mb-1">Overall Accuracy</p>
              <p className="text-3xl font-bold text-green-900">{overallAccuracy}%</p>
              <p className="text-sm text-green-700 mt-1">
                {correctPredictions} of {totalPredictions} correct
              </p>
            </div>
            <Target className="text-green-600" size={48} />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-blue-50 to-blue-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-blue-600 mb-1">Correct Predictions</p>
              <p className="text-3xl font-bold text-blue-900">{correctPredictions}</p>
              <p className="text-sm text-blue-700 mt-1">Successful picks</p>
            </div>
            <CheckCircle className="text-blue-600" size={48} />
          </div>
        </div>

        <div className="card bg-gradient-to-br from-gray-50 to-gray-100">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600 mb-1">Incorrect Predictions</p>
              <p className="text-3xl font-bold text-gray-900">{totalPredictions - correctPredictions}</p>
              <p className="text-sm text-gray-700 mt-1">Missed picks</p>
            </div>
            <XCircle className="text-gray-600" size={48} />
          </div>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Accuracy by Confidence */}
        <div className="card">
          <h2 className="text-xl font-bold mb-4">Accuracy by Confidence Level</h2>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={accuracyByConfidence}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="name" />
              <YAxis domain={[0, 100]} />
              <Tooltip 
                formatter={(value, name, props) => {
                  if (name === 'accuracy') {
                    return [`${value}% (${props.payload.correct}/${props.payload.total})`, 'Accuracy']
                  }
                  return value
                }}
              />
              <Bar dataKey="accuracy" fill="#3b82f6" />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Accuracy Trend */}
        <div className="card">
          <h2 className="text-xl font-bold mb-4">Accuracy Trend (Weekly)</h2>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={weeklyChart}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="week" 
                tickFormatter={(date) => new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <YAxis domain={[0, 100]} />
              <Tooltip 
                labelFormatter={(date) => `Week of ${new Date(date).toLocaleDateString()}`}
                formatter={(value, name, props) => {
                  if (name === 'accuracy') {
                    return [`${value}% (${props.payload.total} games)`, 'Accuracy']
                  }
                  return value
                }}
              />
              <Line type="monotone" dataKey="accuracy" stroke="#3b82f6" strokeWidth={2} dot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Recent Predictions Table */}
      <div className="card">
        <h2 className="text-xl font-bold mb-4">Recent Predictions</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Date</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Game</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Predicted</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Actual Winner</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Score</th>
                <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Confidence</th>
                <th className="px-4 py-3 text-center text-sm font-semibold text-gray-700">Result</th>
              </tr>
            </thead>
            <tbody>
              {recentPredictions.map((pred) => {
                const actualWinner = pred.home_score > pred.away_score ? pred.home_team : pred.away_team
                const dateObj = pred.date ? new Date(pred.date) : null
                const isValidDate = dateObj && !isNaN(dateObj.getTime())
                
                return (
                  <tr key={pred.game_id} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {isValidDate ? dateObj.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {pred.away_team} @ {pred.home_team}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium">{pred.predicted_winner}</td>
                    <td className="px-4 py-3 text-sm font-medium">{actualWinner}</td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {pred.away_score}-{pred.home_score}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {(pred.confidence * 100).toFixed(1)}%
                    </td>
                    <td className="px-4 py-3 text-center">
                      {pred.correct ? (
                        <CheckCircle className="inline text-green-600" size={20} />
                      ) : (
                        <XCircle className="inline text-red-600" size={20} />
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
