import { useState, useEffect, useMemo } from 'react'
import { 
  fetchBettingSummary, 
  fetchBettingByConfidence, 
  fetchBettingByStrategy,
  fetchCumulativeProfit,
  fetchParlayStats 
} from '../services/api'
import { TrendingUp, PieChart as PieChartIcon, BarChart3, DollarSign, Target, Award } from 'lucide-react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart
} from 'recharts'

const COLORS = {
  win: '#10b981',
  loss: '#ef4444',
  primary: '#3b82f6',
  secondary: '#8b5cf6',
  accent: '#f59e0b'
}

export default function BettingAccuracyPage() {
  const [summary, setSummary] = useState(null)
  const [byConfidence, setByConfidence] = useState([])
  const [byStrategy, setByStrategy] = useState([])
  const [profitTimeline, setProfitTimeline] = useState([])
  const [parlayStats, setParlayStats] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadData() {
      try {
        const [summaryData, confidenceData, strategyData, timelineData, parlayData] = await Promise.all([
          fetchBettingSummary(),
          fetchBettingByConfidence(),
          fetchBettingByStrategy(),
          fetchCumulativeProfit(),
          fetchParlayStats()
        ])
        
        setSummary(summaryData)
        setByConfidence(confidenceData)
        setByStrategy(strategyData)
        setProfitTimeline(timelineData)
        setParlayStats(parlayData)
      } catch (error) {
        console.error('Failed to load betting accuracy data:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadData()
  }, [])

  // Calculate win/loss data for pie chart
  const winLossData = useMemo(() => {
    if (!summary) return []
    return [
      { name: 'Wins', value: summary.wins, color: COLORS.win },
      { name: 'Losses', value: summary.losses, color: COLORS.loss }
    ]
  }, [summary])

  // Format confidence data for bar chart
  const confidenceChartData = useMemo(() => {
    return byConfidence.map(item => ({
      name: item.confidence_bucket,
      'Win Rate': (item.win_rate * 100).toFixed(1),
      'ROI': (item.roi * 100).toFixed(1),
      'Total Bets': item.total_bets
    }))
  }, [byConfidence])

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
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Betting Accuracy Analytics</h1>
        <p className="text-gray-600 mt-1">Comprehensive analysis of betting performance and profitability</p>
      </div>

      {!hasBettingData ? (
        <div className="card text-center py-12">
          <PieChartIcon className="mx-auto text-gray-400 mb-4" size={48} />
          <p className="text-gray-600 font-medium">No betting data available yet</p>
          <p className="text-sm text-gray-500 mt-2">Start placing bets to see analytics here!</p>
        </div>
      ) : (
        <>
          {/* Summary Stats Grid */}
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="card">
              <div className="flex items-center space-x-2 mb-2">
                <Target className="text-blue-500" size={20} />
                <p className="text-sm text-gray-600">Win Rate</p>
              </div>
              <p className="text-3xl font-bold text-gray-900">
                {(summary.win_rate * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 mt-1">
                {summary.wins}W - {summary.losses}L
              </p>
            </div>

            <div className="card">
              <div className="flex items-center space-x-2 mb-2">
                <DollarSign className="text-green-500" size={20} />
                <p className="text-sm text-gray-600">Total Profit</p>
              </div>
              <p className={`text-3xl font-bold ${summary.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {summary.total_profit >= 0 ? '+' : ''}${summary.total_profit?.toFixed(2)}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                ${summary.total_wagered?.toFixed(2)} wagered
              </p>
            </div>

            <div className="card">
              <div className="flex items-center space-x-2 mb-2">
                <TrendingUp className="text-purple-500" size={20} />
                <p className="text-sm text-gray-600">ROI</p>
              </div>
              <p className={`text-3xl font-bold ${summary.roi >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {(summary.roi * 100).toFixed(1)}%
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Return on investment
              </p>
            </div>

            <div className="card">
              <div className="flex items-center space-x-2 mb-2">
                <BarChart3 className="text-orange-500" size={20} />
                <p className="text-sm text-gray-600">Total Bets</p>
              </div>
              <p className="text-3xl font-bold text-gray-900">
                {summary.total_bets}
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Placed so far
              </p>
            </div>

            {parlayStats && parlayStats.total_parlays > 0 && (
              <div className="card">
                <div className="flex items-center space-x-2 mb-2">
                  <Award className="text-yellow-500" size={20} />
                  <p className="text-sm text-gray-600">Parlay Stats</p>
                </div>
                <p className="text-3xl font-bold text-gray-900">
                  {parlayStats.total_parlays}
                </p>
                <p className="text-xs text-gray-500 mt-1">
                  {parlayStats.wins}W - {parlayStats.losses}L
                </p>
              </div>
            )}
          </div>

          {/* Charts Row 1: Win/Loss Pie + Profit Timeline */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Win/Loss Distribution */}
            <div className="card">
              <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
                <PieChartIcon className="text-blue-500" />
                <span>Win/Loss Distribution</span>
              </h2>
              
              <ResponsiveContainer width="100%" height={300}>
                <PieChart>
                  <Pie
                    data={winLossData}
                    cx="50%"
                    cy="50%"
                    labelLine={false}
                    label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(1)}%`}
                    outerRadius={100}
                    fill="#8884d8"
                    dataKey="value"
                  >
                    {winLossData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>

              <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-2 gap-4 text-center">
                <div>
                  <p className="text-sm text-gray-600">Wins</p>
                  <p className="text-2xl font-bold text-green-600">{summary.wins}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-600">Losses</p>
                  <p className="text-2xl font-bold text-red-600">{summary.losses}</p>
                </div>
              </div>
            </div>

            {/* Cumulative Profit Over Time */}
            <div className="card">
              <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
                <TrendingUp className="text-green-500" />
                <span>Profit Timeline</span>
              </h2>
              
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={profitTimeline}>
                  <defs>
                    <linearGradient id="profitGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={COLORS.primary} stopOpacity={0.3}/>
                      <stop offset="95%" stopColor={COLORS.primary} stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis 
                    dataKey="date" 
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  />
                  <YAxis 
                    tick={{ fontSize: 12 }}
                    tickFormatter={(value) => `$${value.toFixed(0)}`}
                  />
                  <Tooltip 
                    formatter={(value) => [`$${Number(value).toFixed(2)}`, 'Cumulative Profit']}
                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                  />
                  <Area 
                    type="monotone" 
                    dataKey="cumulative_profit" 
                    stroke={COLORS.primary} 
                    fillOpacity={1} 
                    fill="url(#profitGradient)" 
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>

              <div className="mt-4 pt-4 border-t border-gray-200">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">Current Total Profit:</span>
                  <span className={`font-bold text-lg ${summary.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {summary.total_profit >= 0 ? '+' : ''}${summary.total_profit?.toFixed(2)}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Charts Row 2: Performance by Confidence */}
          {byConfidence.length > 0 && (
            <div className="card">
              <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
                <BarChart3 className="text-purple-500" />
                <span>Performance by Confidence Level</span>
              </h2>
              
              <ResponsiveContainer width="100%" height={350}>
                <BarChart data={confidenceChartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                  <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Bar yAxisId="left" dataKey="Win Rate" fill={COLORS.primary} name="Win Rate (%)" />
                  <Bar yAxisId="right" dataKey="ROI" fill={COLORS.secondary} name="ROI (%)" />
                </BarChart>
              </ResponsiveContainer>

              <div className="mt-6 grid grid-cols-1 md:grid-cols-2 gap-4">
                {byConfidence.map((item, index) => (
                  <div key={index} className="p-4 bg-gradient-to-br from-gray-50 to-white border border-gray-200 rounded-lg">
                    <h3 className="font-semibold text-gray-900 mb-3">{item.confidence_bucket}</h3>
                    <div className="space-y-2 text-sm">
                      <div className="flex justify-between">
                        <span className="text-gray-600">Total Bets:</span>
                        <span className="font-semibold">{item.total_bets}</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Win Rate:</span>
                        <span className="font-semibold text-blue-600">{(item.win_rate * 100).toFixed(1)}%</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Record:</span>
                        <span className="font-semibold">{item.wins}W - {item.total_bets - item.wins}L</span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">Profit:</span>
                        <span className={`font-semibold ${item.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {item.total_profit >= 0 ? '+' : ''}${item.total_profit.toFixed(2)}
                        </span>
                      </div>
                      <div className="flex justify-between">
                        <span className="text-gray-600">ROI:</span>
                        <span className={`font-semibold ${item.roi >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {(item.roi * 100).toFixed(1)}%
                        </span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Strategy Performance */}
          {byStrategy.length > 0 && (
            <div className="card">
              <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
                <Award className="text-yellow-500" />
                <span>Performance by Strategy</span>
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {byStrategy.map((strategy, index) => (
                  <div key={index} className="p-5 bg-gradient-to-br from-blue-50 to-white border-2 border-blue-200 rounded-xl">
                    <h3 className="font-bold text-lg text-gray-900 mb-4 capitalize">
                      {strategy.strategy.replace(/_/g, ' ')}
                    </h3>
                    
                    <div className="space-y-3">
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">Total Bets</span>
                        <span className="text-xl font-bold text-gray-900">{strategy.total_bets}</span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">Win Rate</span>
                        <span className="text-xl font-bold text-blue-600">
                          {(strategy.win_rate * 100).toFixed(1)}%
                        </span>
                      </div>
                      
                      <div className="flex items-center justify-between">
                        <span className="text-sm text-gray-600">Record</span>
                        <span className="text-lg font-semibold text-gray-900">
                          {strategy.wins}W - {strategy.total_bets - strategy.wins}L
                        </span>
                      </div>
                      
                      <div className="pt-3 border-t border-blue-200">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm text-gray-600">Total Profit</span>
                          <span className={`text-xl font-bold ${strategy.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {strategy.total_profit >= 0 ? '+' : ''}${strategy.total_profit.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex items-center justify-between">
                          <span className="text-sm text-gray-600">ROI</span>
                          <span className={`text-lg font-bold ${strategy.roi >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {(strategy.roi * 100).toFixed(1)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Parlay Performance */}
          {parlayStats && parlayStats.total_parlays > 0 && (
            <div className="card bg-gradient-to-br from-purple-50 to-white border-2 border-purple-200">
              <h2 className="text-xl font-bold mb-4 flex items-center space-x-2">
                <Award className="text-purple-500" />
                <span>Parlay Performance</span>
              </h2>
              
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-white rounded-lg border border-purple-100">
                  <p className="text-sm text-gray-600 mb-1">Total Parlays</p>
                  <p className="text-3xl font-bold text-gray-900">{parlayStats.total_parlays}</p>
                </div>
                
                <div className="text-center p-4 bg-white rounded-lg border border-purple-100">
                  <p className="text-sm text-gray-600 mb-1">Win Rate</p>
                  <p className="text-3xl font-bold text-purple-600">
                    {(parlayStats.win_rate * 100).toFixed(1)}%
                  </p>
                  <p className="text-xs text-gray-500 mt-1">{parlayStats.wins}W - {parlayStats.losses}L</p>
                </div>
                
                <div className="text-center p-4 bg-white rounded-lg border border-purple-100">
                  <p className="text-sm text-gray-600 mb-1">Total Profit</p>
                  <p className={`text-3xl font-bold ${parlayStats.total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {parlayStats.total_profit >= 0 ? '+' : ''}${parlayStats.total_profit.toFixed(2)}
                  </p>
                </div>
                
                <div className="text-center p-4 bg-white rounded-lg border border-purple-100">
                  <p className="text-sm text-gray-600 mb-1">ROI</p>
                  <p className={`text-3xl font-bold ${parlayStats.roi >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {parlayStats.roi.toFixed(1)}%
                  </p>
                </div>
              </div>

              <div className="mt-4 pt-4 border-t border-purple-200 grid grid-cols-2 gap-4 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-600">Biggest Win:</span>
                  <span className="font-bold text-green-600">+${parlayStats.biggest_win.toFixed(2)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600">Biggest Loss:</span>
                  <span className="font-bold text-red-600">${parlayStats.biggest_loss.toFixed(2)}</span>
                </div>
              </div>
            </div>
          )}

          {/* Key Insights */}
          <div className="card bg-gradient-to-br from-blue-50 to-white border-2 border-blue-200">
            <h2 className="text-xl font-bold mb-4 text-gray-900">📊 Key Insights</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 bg-white rounded-lg border border-blue-100">
                <p className="text-sm font-semibold text-blue-900 mb-2">Best Performing Tier</p>
                {byConfidence.length > 0 && (() => {
                  const best = [...byConfidence].sort((a, b) => b.roi - a.roi)[0]
                  return (
                    <div>
                      <p className="text-lg font-bold text-gray-900">{best.confidence_bucket}</p>
                      <p className="text-sm text-gray-600 mt-1">
                        {(best.win_rate * 100).toFixed(1)}% win rate · {(best.roi * 100).toFixed(1)}% ROI
                      </p>
                    </div>
                  )
                })()}
              </div>
              
              <div className="p-4 bg-white rounded-lg border border-blue-100">
                <p className="text-sm font-semibold text-blue-900 mb-2">Average Bet Size</p>
                <p className="text-lg font-bold text-gray-900">
                  ${(summary.total_wagered / summary.total_bets).toFixed(2)}
                </p>
                <p className="text-sm text-gray-600 mt-1">
                  Per bet across {summary.total_bets} total bets
                </p>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
