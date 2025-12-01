import { useState, useEffect } from 'react'
import { fetchTopTeams } from '../services/api'
import { Users, TrendingUp } from 'lucide-react'

export default function TeamsPage() {
  const [teams, setTeams] = useState([])
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    async function loadTeams() {
      try {
        const data = await fetchTopTeams()
        setTeams(data)
      } catch (error) {
        console.error('Failed to load teams:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadTeams()
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
        <h1 className="text-3xl font-bold text-gray-900">Top Teams</h1>
        <p className="text-gray-600 mt-1">Best performing teams this season</p>
      </div>
      
      {teams.length === 0 ? (
        <div className="card text-center py-12">
          <Users className="mx-auto text-gray-400 mb-4" size={48} />
          <p className="text-gray-600">No team data available</p>
        </div>
      ) : (
        <div className="card">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Rank</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Team</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-700">Win %</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-700">Avg Points</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-700">Games</th>
                </tr>
              </thead>
              <tbody>
                {teams.map((team, index) => (
                  <tr key={team.team_id} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <div className="flex items-center space-x-2">
                        <span className="font-bold text-gray-900">#{index + 1}</span>
                        {index < 3 && <TrendingUp className="text-yellow-500" size={16} />}
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <div>
                        <p className="font-semibold text-gray-900">{team.display_name}</p>
                        {team.conference && (
                          <p className="text-xs text-gray-500">{team.conference}</p>
                        )}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="font-semibold text-primary-600">
                        {team.rolling_win_pct_10 
                          ? `${(team.rolling_win_pct_10 * 100).toFixed(1)}%`
                          : 'N/A'
                        }
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center text-gray-700">
                      {team.avg_points_scored?.toFixed(1) || 'N/A'}
                    </td>
                    <td className="py-3 px-4 text-center text-gray-700">
                      {team.games_played || 0}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
