import { useState, useEffect } from 'react'
import { fetchAllTeams } from '../services/api'
import { Users, Search } from 'lucide-react'

export default function TeamsPage() {
  const [teams, setTeams] = useState([])
  const [filteredTeams, setFilteredTeams] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  
  useEffect(() => {
    async function loadTeams() {
      try {
        const data = await fetchAllTeams()
        setTeams(data)
        setFilteredTeams(data)
      } catch (error) {
        console.error('Failed to load teams:', error)
      } finally {
        setLoading(false)
      }
    }
    
    loadTeams()
  }, [])
  
  // Filter teams based on search
  useEffect(() => {
    let filtered = teams
    
    // Apply search filter
    if (searchQuery) {
      filtered = filtered.filter(team => 
        team.display_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    
    setFilteredTeams(filtered)
  }, [searchQuery, teams])
  
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
        <h1 className="text-3xl font-bold text-gray-900">All Teams</h1>
        <p className="text-gray-600 mt-1">{teams.length} teams • {filteredTeams.length} showing</p>
      </div>
      
      {/* Search */}
      <div className="card">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={20} />
          <input
            type="text"
            placeholder="Search teams..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          />
        </div>
      </div>
      
      {filteredTeams.length === 0 ? (
        <div className="card text-center py-12">
          <Users className="mx-auto text-gray-400 mb-4" size={48} />
          <p className="text-gray-600 font-medium">No teams found</p>
          <p className="text-sm text-gray-500 mt-2">Try a different search or filter</p>
        </div>
      ) : (
        <div className="card">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Team</th>
                  <th className="text-left py-3 px-4 font-semibold text-gray-700">Conference</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-700">Record</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-700">Our Accuracy</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-700">Predictions</th>
                  <th className="text-center py-3 px-4 font-semibold text-gray-700">Avg Confidence</th>
                </tr>
              </thead>
              <tbody>
                {filteredTeams.map((team) => (
                  <tr key={team.display_name} className="border-b hover:bg-gray-50">
                    <td className="py-3 px-4">
                      <p className="font-semibold text-gray-900">{team.display_name}</p>
                    </td>
                    <td className="py-3 px-4 text-gray-600 text-sm">
                      {team.conference}
                    </td>
                    <td className="py-3 px-4 text-center text-gray-700">
                      <span className="font-medium">{team.wins}</span>
                      <span className="text-gray-500">-</span>
                      <span className="font-medium">{team.losses}</span>
                      <span className="text-xs text-gray-400 ml-2">
                        ({(team.win_pct * 100).toFixed(0)}%)
                      </span>
                    </td>
                    <td className="py-3 px-4 text-center">
                      {team.predictions_made > 0 ? (
                        <span className="font-semibold text-primary-600">
                          {(team.prediction_accuracy * 100).toFixed(1)}%
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center text-gray-700">
                      {team.predictions_made > 0 ? (
                        <>
                          <span className="font-medium">{team.correct_predictions}</span>
                          <span className="text-gray-500">/{team.predictions_made}</span>
                        </>
                      ) : (
                        <span className="text-gray-400">0</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center text-gray-700">
                      {team.predictions_made > 0 ? (
                        `${(team.avg_confidence * 100).toFixed(1)}%`
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          
          {/* Pagination hint for large result sets */}
          {filteredTeams.length > 100 && (
            <div className="mt-4 text-center text-sm text-gray-500">
              Showing {filteredTeams.length} teams. Use search to narrow results.
            </div>
          )}
        </div>
      )}
    </div>
  )
}
