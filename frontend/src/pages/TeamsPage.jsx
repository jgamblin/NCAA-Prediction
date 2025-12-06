import { useState, useEffect } from 'react'
import { fetchAllTeams } from '../services/api'
import { Users, Search, ChevronUp, ChevronDown } from 'lucide-react'

export default function TeamsPage() {
  const [teams, setTeams] = useState([])
  const [filteredTeams, setFilteredTeams] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [loading, setLoading] = useState(true)
  const [sortKey, setSortKey] = useState('prediction_accuracy')
  const [sortDirection, setSortDirection] = useState('desc')
  const [hideNoConference, setHideNoConference] = useState(true)
  
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
  
  // Sort function
  const sortTeams = (teamsToSort, key, direction) => {
    return [...teamsToSort].sort((a, b) => {
      let aVal = a[key]
      let bVal = b[key]
      
      // Handle string sorting (for team names, conference)
      if (typeof aVal === 'string' || typeof bVal === 'string') {
        // Convert to strings and handle empty values
        aVal = String(aVal || '')
        bVal = String(bVal || '')
        return direction === 'asc' 
          ? aVal.localeCompare(bVal)
          : bVal.localeCompare(aVal)
      }
      
      // Special handling for prediction_accuracy - treat teams with 0 predictions as lowest
      if (key === 'prediction_accuracy') {
        const aHasPredictions = a.predictions_made > 0
        const bHasPredictions = b.predictions_made > 0
        
        // If one has predictions and one doesn't, prioritize the one with predictions
        if (aHasPredictions && !bHasPredictions) return direction === 'desc' ? -1 : 1
        if (!aHasPredictions && bHasPredictions) return direction === 'desc' ? 1 : -1
      }
      
      // Handle numeric sorting
      if (direction === 'asc') {
        return aVal - bVal
      } else {
        return bVal - aVal
      }
    })
  }
  
  // Handle sort header click
  const handleSort = (key) => {
    let newDirection = 'desc'
    
    // If clicking same column, toggle direction
    if (sortKey === key) {
      newDirection = sortDirection === 'asc' ? 'desc' : 'asc'
    }
    
    setSortKey(key)
    setSortDirection(newDirection)
  }
  
  // Filter and sort teams
  useEffect(() => {
    let filtered = teams
    
    // Apply search filter
    if (searchQuery) {
      filtered = filtered.filter(team => 
        team.display_name.toLowerCase().includes(searchQuery.toLowerCase())
      )
    }
    
    // Apply conference filter
    if (hideNoConference) {
      filtered = filtered.filter(team => 
        team.conference && team.conference.trim() !== ''
      )
    }
    
    // Apply sorting
    filtered = sortTeams(filtered, sortKey, sortDirection)
    
    setFilteredTeams(filtered)
  }, [searchQuery, teams, sortKey, sortDirection, hideNoConference])
  
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
      
      {/* Search and Filters */}
      <div className="card">
        <div className="space-y-4">
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
          
          <div className="flex items-center">
            <label className="flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={hideNoConference}
                onChange={(e) => setHideNoConference(e.target.checked)}
                className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
              />
              <span className="ml-2 text-sm text-gray-700">
                Hide teams without conference
              </span>
            </label>
          </div>
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
                  <th 
                    className="text-left py-3 px-4 font-semibold text-gray-700 cursor-pointer hover:bg-gray-50"
                    onClick={() => handleSort('display_name')}
                  >
                    <div className="flex items-center">
                      Team
                      {sortKey === 'display_name' && (
                        sortDirection === 'asc' ? <ChevronUp size={16} className="ml-1" /> : <ChevronDown size={16} className="ml-1" />
                      )}
                    </div>
                  </th>
                  <th 
                    className="text-left py-3 px-4 font-semibold text-gray-700 cursor-pointer hover:bg-gray-50"
                    onClick={() => handleSort('conference')}
                  >
                    <div className="flex items-center">
                      Conference
                      {sortKey === 'conference' && (
                        sortDirection === 'asc' ? <ChevronUp size={16} className="ml-1" /> : <ChevronDown size={16} className="ml-1" />
                      )}
                    </div>
                  </th>
                  <th 
                    className="text-center py-3 px-4 font-semibold text-gray-700 cursor-pointer hover:bg-gray-50"
                    onClick={() => handleSort('win_pct')}
                  >
                    <div className="flex items-center justify-center">
                      Record
                      {sortKey === 'win_pct' && (
                        sortDirection === 'asc' ? <ChevronUp size={16} className="ml-1" /> : <ChevronDown size={16} className="ml-1" />
                      )}
                    </div>
                  </th>
                  <th 
                    className="text-center py-3 px-4 font-semibold text-gray-700 cursor-pointer hover:bg-gray-50"
                    onClick={() => handleSort('prediction_accuracy')}
                  >
                    <div className="flex items-center justify-center">
                      Our Accuracy
                      {sortKey === 'prediction_accuracy' && (
                        sortDirection === 'asc' ? <ChevronUp size={16} className="ml-1" /> : <ChevronDown size={16} className="ml-1" />
                      )}
                    </div>
                  </th>
                  <th 
                    className="text-center py-3 px-4 font-semibold text-gray-700 cursor-pointer hover:bg-gray-50"
                    onClick={() => handleSort('predictions_made')}
                  >
                    <div className="flex items-center justify-center">
                      Predictions
                      {sortKey === 'predictions_made' && (
                        sortDirection === 'asc' ? <ChevronUp size={16} className="ml-1" /> : <ChevronDown size={16} className="ml-1" />
                      )}
                    </div>
                  </th>
                  <th 
                    className="text-center py-3 px-4 font-semibold text-gray-700 cursor-pointer hover:bg-gray-50"
                    onClick={() => handleSort('avg_confidence')}
                  >
                    <div className="flex items-center justify-center">
                      Avg Confidence
                      {sortKey === 'avg_confidence' && (
                        sortDirection === 'asc' ? <ChevronUp size={16} className="ml-1" /> : <ChevronDown size={16} className="ml-1" />
                      )}
                    </div>
                  </th>
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
