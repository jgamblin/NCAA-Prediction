import { useState, useEffect } from 'react'
import { fetchBettingSummary, fetchValueBets, fetchParlays, fetchParlayStats } from '../services/api'
import { DollarSign, TrendingUp, Award, TrendingDown, AlertCircle, Calendar, Layers } from 'lucide-react'

export default function BettingPage() {
  const [summary, setSummary] = useState(null)
  const [valueBets, setValueBets] = useState([])
  const [parlays, setParlays] = useState([])
  const [parlayStats, setParlayStats] = useState(null)
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    async function loadData() {
      try {
        const [summaryData, valueBetsData, parlaysData, parlayStatsData] = await Promise.all([
          fetchBettingSummary(),
          fetchValueBets(),
          fetchParlays(),
          fetchParlayStats()
        ])
        setSummary(summaryData)
        setValueBets(valueBetsData)
        
        // Filter parlays to only show today's or unsettled parlays
        const today = new Date().toISOString().split('T')[0]
        const filteredParlays = parlaysData.filter(parlay => {
          const parlayDate = new Date(parlay.date).toISOString().split('T')[0]
          return !parlay.settled || parlayDate === today
        })
        
        setParlays(filteredParlays)
        setParlayStats(parlayStatsData)
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
      
      {/* Parlays Section */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold flex items-center space-x-2">
            <Layers className="text-purple-500" />
            <span>Today's Parlay Bet</span>
          </h2>
          {parlayStats && parlayStats.total_parlays > 0 && (
            <div className="text-sm text-gray-600">
              <span className="font-semibold">{parlayStats.wins}W - {parlayStats.losses}L</span>
              <span className="mx-2">|</span>
              <span className={parlayStats.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}>
                {parlayStats.total_profit >= 0 ? '+' : ''}${parlayStats.total_profit.toFixed(2)}
              </span>
            </div>
          )}
        </div>
        
        {parlays && parlays.length > 0 ? (
          
          <div className="space-y-4">
            {parlays.map((parlay) => (
              <div 
                key={parlay.id}
                className="p-5 bg-gradient-to-br from-purple-50 to-white border-2 border-purple-200 rounded-xl"
              >
                {/* Parlay Header */}
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-xs text-gray-500 uppercase tracking-wide">3-Leg Parlay</p>
                    <p className="text-lg font-bold text-gray-900">
                      {new Date(parlay.date).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-500 uppercase tracking-wide">
                      {parlay.settled ? (parlay.won ? 'Won' : 'Lost') : 'Pending'}
                    </p>
                    <p className={`text-2xl font-bold ${
                      !parlay.settled ? 'text-gray-600' :
                      parlay.won ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {parlay.settled ? 
                        (parlay.won ? `+$${parlay.profit.toFixed(2)}` : `-$${Math.abs(parlay.profit).toFixed(2)}`) :
                        `$${parlay.potential_payout.toFixed(2)}`
                      }
                    </p>
                  </div>
                </div>
                
                {/* Parlay Legs */}
                <div className="space-y-3 mb-4">
                  {parlay.legs.map((leg) => {
                    const isHome = leg.bet_team === leg.home_team
                    const opponent = isHome ? leg.away_team : leg.home_team
                    const legStatus = !parlay.settled ? 'pending' : leg.won ? 'won' : 'lost'
                    
                    return (
                      <div 
                        key={leg.leg_number}
                        className={`p-3 rounded-lg border-2 ${
                          legStatus === 'pending' ? 'bg-white border-gray-200' :
                          legStatus === 'won' ? 'bg-green-50 border-green-300' :
                          'bg-red-50 border-red-300'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-3">
                            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                              legStatus === 'pending' ? 'bg-gray-200 text-gray-600' :
                              legStatus === 'won' ? 'bg-green-200 text-green-700' :
                              'bg-red-200 text-red-700'
                            }`}>
                              {leg.leg_number}
                            </div>
                            <div>
                              <p className="font-semibold text-gray-900">{leg.bet_team}</p>
                              <p className="text-xs text-gray-500">vs {opponent}</p>
                            </div>
                          </div>
                          <div className="text-right">
                            <p className="font-bold text-gray-900">
                              {leg.moneyline > 0 ? '+' : ''}{leg.moneyline}
                            </p>
                            <p className="text-xs text-gray-500">{(leg.confidence * 100).toFixed(1)}%</p>
                          </div>
                        </div>
                        {legStatus !== 'pending' && (
                          <div className="mt-2 pt-2 border-t border-gray-200 flex items-center justify-between text-xs">
                            <span className="text-gray-600">Result:</span>
                            <span className={leg.won ? 'text-green-600 font-semibold' : 'text-red-600 font-semibold'}>
                              {leg.actual_winner} won {leg.home_score}-{leg.away_score}
                            </span>
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
                
                {/* Parlay Summary */}
                <div className="pt-4 border-t border-purple-200">
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Bet Amount</p>
                      <p className="font-bold text-lg text-gray-900">${parlay.bet_amount.toFixed(2)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-1">Combined Odds</p>
                      <p className="font-bold text-lg text-purple-600">{parlay.combined_odds.toFixed(2)}x</p>
                    </div>
                    <div>
                      <p className="text-xs text-gray-500 mb-1">{parlay.settled ? 'Payout' : 'Potential'}</p>
                      <p className="font-bold text-lg text-green-600">${parlay.settled ? parlay.actual_payout.toFixed(2) : parlay.potential_payout.toFixed(2)}</p>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <Layers className="mx-auto text-gray-400 mb-4" size={48} />
            <p className="text-gray-600 font-medium">No parlay bet for today</p>
            <p className="text-sm text-gray-500 mt-2">
              Parlays require at least 3 eligible high-confidence games with moneylines.
            </p>
            <p className="text-xs text-gray-400 mt-1">
              Check back tomorrow or view historical parlays on the Bet Analytics page!
            </p>
          </div>
        )}
      </div>
      
      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start space-x-3">
        <AlertCircle className="text-blue-600 flex-shrink-0 mt-0.5" size={20} />
        <div className="text-sm text-blue-900">
          <p className="font-semibold mb-1">What is Value Betting?</p>
          <p>
            Value betting finds opportunities where our model's confidence is significantly higher than
            what the odds imply. The "edge" shows how much extra value we believe exists.
          </p>
        </div>
      </div>
      
      {/* Value Bets */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold flex items-center space-x-2">
            <Award className="text-yellow-500" />
            <span>Today's Value Bets</span>
          </h2>
          <div className="flex items-center space-x-2 text-sm text-gray-600">
            <Calendar size={16} />
            <span>{new Date().toLocaleDateString()}</span>
          </div>
        </div>
        
        {valueBets.length === 0 ? (
          <div className="text-center py-12">
            <TrendingDown className="mx-auto text-gray-400 mb-4" size={48} />
            <p className="text-gray-600 font-medium">No value bets found today</p>
            <p className="text-sm text-gray-500 mt-2">
              Check back tomorrow for new opportunities!
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {valueBets.map((bet, index) => {
              const opponent = bet.home_team === bet.bet_team ? bet.away_team : bet.home_team
              const isAway = bet.away_team === bet.bet_team
              const edgePercent = (bet.value_score * 100).toFixed(1)
              const confidencePercent = (bet.confidence * 100).toFixed(1)
              
              return (
                <div 
                  key={bet.id} 
                  className="p-5 bg-gradient-to-br from-gray-50 to-white border border-gray-200 rounded-xl hover:shadow-md transition-shadow"
                >
                  {/* Header */}
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center space-x-3">
                      <div className="w-8 h-8 bg-yellow-100 rounded-full flex items-center justify-center">
                        <span className="text-yellow-700 font-bold text-sm">#{index + 1}</span>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wide">Pick</p>
                        <p className="text-lg font-bold text-gray-900">{bet.bet_team}</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-xs text-gray-500 uppercase tracking-wide">Edge</p>
                      <p className="text-2xl font-bold text-green-600">+{edgePercent}%</p>
                    </div>
                  </div>
                  
                  {/* Matchup */}
                  <div className="flex items-center justify-center space-x-3 mb-4 py-3 bg-white rounded-lg border border-gray-100">
                    <span className={`font-semibold ${isAway ? 'text-primary-600' : 'text-gray-700'}`}>
                      {bet.away_team}
                    </span>
                    <span className="text-gray-400 font-medium">@</span>
                    <span className={`font-semibold ${!isAway ? 'text-primary-600' : 'text-gray-700'}`}>
                      {bet.home_team}
                    </span>
                  </div>
                  
                  {/* Stats Grid */}
                  <div className="grid grid-cols-3 gap-4">
                    <div className="text-center">
                      <p className="text-xs text-gray-500 mb-1">Confidence</p>
                      <p className="font-bold text-lg text-primary-600">{confidencePercent}%</p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-gray-500 mb-1">Odds</p>
                      <p className="font-bold text-lg text-gray-900">
                        {bet.moneyline > 0 ? '+' : ''}{bet.moneyline}
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-xs text-gray-500 mb-1">Suggested Bet</p>
                      <p className="font-bold text-lg text-green-600">${bet.bet_amount.toFixed(2)}</p>
                    </div>
                  </div>
                  
                  {/* Potential Payout */}
                  <div className="mt-4 pt-4 border-t border-gray-200">
                    <div className="flex items-center justify-between text-sm">
                      <span className="text-gray-600">Potential Profit:</span>
                      <span className="font-semibold text-gray-900">
                        ${(bet.moneyline > 0 
                          ? bet.bet_amount * (bet.moneyline / 100)
                          : bet.bet_amount * (100 / Math.abs(bet.moneyline))
                        ).toFixed(2)}
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}
            
            {/* Summary */}
            <div className="mt-6 p-4 bg-primary-50 rounded-lg border border-primary-200">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-primary-900 font-medium">Total Suggested Bankroll</p>
                  <p className="text-xs text-primary-700 mt-0.5">
                    Across {valueBets.length} opportunities
                  </p>
                </div>
                <p className="text-2xl font-bold text-primary-600">
                  ${valueBets.reduce((sum, bet) => sum + bet.bet_amount, 0).toFixed(2)}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
