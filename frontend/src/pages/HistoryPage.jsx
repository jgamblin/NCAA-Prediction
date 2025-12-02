import { useState, useEffect } from 'react'
import { fetchPredictionHistory } from '../services/api'
import { History, CheckCircle, XCircle, ChevronLeft, ChevronRight } from 'lucide-react'

const ITEMS_PER_PAGE = 50

export default function HistoryPage() {
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [currentPage, setCurrentPage] = useState(1)
  
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
  
  // Calculate pagination
  const totalPages = Math.ceil(history.length / ITEMS_PER_PAGE)
  const startIndex = (currentPage - 1) * ITEMS_PER_PAGE
  const endIndex = startIndex + ITEMS_PER_PAGE
  const currentItems = history.slice(startIndex, endIndex)
  
  const goToPage = (page) => {
    setCurrentPage(page)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  
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
        <p className="text-gray-600 mt-1">
          {history.length} total predictions 
          {totalPages > 1 && ` • Page ${currentPage} of ${totalPages}`}
        </p>
      </div>
      
      {history.length === 0 ? (
        <div className="card text-center py-12">
          <History className="mx-auto text-gray-400 mb-4" size={48} />
          <p className="text-gray-600">No prediction history available</p>
        </div>
      ) : (
        <>
          <div className="space-y-3">
            {currentItems.map((pred) => {
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
        
        {/* Pagination Controls */}
        {totalPages > 1 && (
          <div className="card">
            <div className="flex items-center justify-between">
              <button
                onClick={() => goToPage(currentPage - 1)}
                disabled={currentPage === 1}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                  currentPage === 1
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-primary-600 text-white hover:bg-primary-700'
                }`}
              >
                <ChevronLeft size={20} />
                <span>Previous</span>
              </button>
              
              <div className="flex items-center space-x-2">
                {/* Page Numbers */}
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  // Show first 3, current +/- 1, and last page
                  let pageNum
                  if (totalPages <= 5) {
                    pageNum = i + 1
                  } else if (currentPage <= 3) {
                    pageNum = i + 1
                  } else if (currentPage >= totalPages - 2) {
                    pageNum = totalPages - 4 + i
                  } else {
                    pageNum = currentPage - 2 + i
                  }
                  
                  return (
                    <button
                      key={pageNum}
                      onClick={() => goToPage(pageNum)}
                      className={`w-10 h-10 rounded-lg font-medium transition-colors ${
                        currentPage === pageNum
                          ? 'bg-primary-600 text-white'
                          : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                      }`}
                    >
                      {pageNum}
                    </button>
                  )
                })}
                
                {totalPages > 5 && currentPage < totalPages - 2 && (
                  <>
                    <span className="text-gray-400">...</span>
                    <button
                      onClick={() => goToPage(totalPages)}
                      className="w-10 h-10 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 font-medium"
                    >
                      {totalPages}
                    </button>
                  </>
                )}
              </div>
              
              <button
                onClick={() => goToPage(currentPage + 1)}
                disabled={currentPage === totalPages}
                className={`flex items-center space-x-2 px-4 py-2 rounded-lg font-medium transition-colors ${
                  currentPage === totalPages
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : 'bg-primary-600 text-white hover:bg-primary-700'
                }`}
              >
                <span>Next</span>
                <ChevronRight size={20} />
              </button>
            </div>
          </div>
        )}
      </>
      )}
    </div>
  )
}
