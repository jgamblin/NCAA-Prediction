import { useState, useEffect } from 'react'
import { fetchBettingSummary, fetchValueBets } from '../services/api'
import { DollarSign, TrendingUp, Award } from 'lucide-react'

export default function BettingPage() {
  const [summary, setSummary] = useState(null)
  const [valueBets, setValueBets] = useState([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    async function loadData() {
      try {
        const [summaryData, valueBetsData] = await Promise.all([
          fetchBettingSummary(),
          fetchValueBets()
        ])
        setSummary(summaryData)
        setValueBets(valueBetsData)
      } catch (error) {
        console.error('Failed to load betting data:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadData()
  }, [])
  
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }
  
  const hasBettingData = summary && summary.total_bets > 0
  
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Betting Analytics</h1>
        <p className="text-gray-600 mt-1">Track betting performance and find value opportunities</p>
      </div>
      
      {/* Summary Cards */}
      {hasBettingData && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="card">
            <p className="text-sm text-gray-600 mb-1">Win Rate</p>
            <p className="text-3xl font-bold text-gray-900">
              {(summary.win_rate * 100).toFixed(1)}%
            </p>
          </div>
          
          <div className="card">
            <p className="text-sm text-gray-600 mb-1">Total Profit</p>
            <p className={`text-3xl font-bold ${summary.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {summary.total_profit >= 0 ? '+' : ''}{summary.total_profit?.toFixed(2)}
            </p>
          </div>
          
          <div className="card">
            <p className="text-sm text-gray-600 mb-1">ROI</p>
            <p className={`text-3xl font-bold ${summary.roi >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {(summary.roi * 100).toFixed(1)}%
            </p>
          </div>
          
          <div className="card">
            <p className="text-sm text-gray-600 mb-1">Total Bets</p>
            <p className="text-3xl font-bold text-gray-900">
              {summary.total_bets}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {summary.wins}W - {summary.losses}L
            </p>
          </div>
        </div>
      )}
      
      {/* Value Bets */}
      <div className="card">
        <h2 className="text-2xl font-bold mb-4 flex items-center space-x-2">
          <Award className="text-yellow-500" />
          <span>Value Betting Opportunities</span>
        </h2>
        
        {valueBets.length === 0 ? (
          <p className="text-gray-600 text-center py-8">
            No value bets available at the moment. Check back later!
          </p>
        ) : (
          <div className="space-y-3">
            {valueBets.map((bet) => (
              <div key={bet.id} className="p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-semibold">{bet.bet_team}</p>
                    <p className="text-sm text-gray-600">
                      vs {bet.home_team === bet.bet_team ? bet.away_team : bet.home_team}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-bold text-primary-600">
                      {(bet.confidence * 100).toFixed(1)}% confidence
                    </p>
                    <p className="text-sm text-gray-600">
                      Odds: {bet.moneyline > 0 ? '+' : ''}{bet.moneyline}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
