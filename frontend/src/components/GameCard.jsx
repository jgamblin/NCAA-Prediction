import { useState } from 'react'
import { Lightbulb, ChevronDown, ChevronUp } from 'lucide-react'

/**
 * GameCard component with expandable prediction explanation
 * 
 * @param {Object} game - Game object with prediction data
 * @param {boolean} showBadge - Whether to show status badge (default: true)
 * @param {string} badgeType - Type of badge to show ('predicted' or 'final' or 'scheduled')
 */
export default function GameCard({ game, showBadge = true, badgeType = 'predicted' }) {
  const [isExpanded, setIsExpanded] = useState(false)
  
  const hasPrediction = game.predicted_winner && game.confidence
  const hasExplanation = game.explanation
  const isFinished = game.game_status === 'Final'
  
  const getConfidenceBorderColor = (confidence) => {
    if (confidence >= 0.75) return 'border-green-500'
    if (confidence >= 0.60) return 'border-yellow-500'
    return 'border-gray-400'
  }
  
  const getBadgeClasses = () => {
    if (badgeType === 'predicted' && hasPrediction) {
      return 'bg-green-100 text-green-700'
    }
    if (badgeType === 'final' && isFinished) {
      return 'bg-gray-100 text-gray-700'
    }
    return 'bg-gray-100 text-gray-600'
  }
  
  const getBadgeText = () => {
    if (badgeType === 'predicted' && hasPrediction) return '✓ Predicted'
    if (badgeType === 'final' && isFinished) return 'Final'
    return 'Scheduled'
  }
  
  return (
    <div className="card hover:shadow-lg transition-shadow">
      <div className="flex flex-col sm:flex-row items-start sm:items-center sm:justify-between">
        <div className="flex-1 w-full">
          {/* Game matchup */}
          <div className="flex items-center flex-wrap gap-2 sm:gap-4 mb-2">
            <span className="text-sm text-gray-500">{game.date}</span>
            <span className="font-medium">{game.away_team}</span>
            {isFinished && <span className="text-gray-900 font-semibold">{game.away_score}</span>}
            <span className="text-gray-400">@</span>
            <span className="font-medium">{game.home_team}</span>
            {isFinished && <span className="text-gray-900 font-semibold">{game.home_score}</span>}
          </div>
          
          {/* Prediction info */}
          {hasPrediction ? (
            <div className="text-sm">
              <span className="text-gray-600">Predicted: </span>
              <span className="font-semibold">{game.predicted_winner}</span>
              <span className="text-gray-600 ml-3">Confidence: </span>
              <span className="font-semibold">{(game.confidence * 100).toFixed(1)}%</span>
            </div>
          ) : (
            <div className="text-sm text-gray-500">
              No prediction available (insufficient team data)
            </div>
          )}
          
          {/* Explanation toggle button */}
          {hasPrediction && hasExplanation && (
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="mt-2 flex items-center space-x-1 text-sm text-primary-600 hover:text-primary-700 font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary-300 rounded px-2 py-1 -ml-2"
              aria-label={`${isExpanded ? 'Hide' : 'Show'} explanation for ${game.predicted_winner}`}
              aria-expanded={isExpanded}
            >
              <Lightbulb size={16} className="flex-shrink-0" aria-hidden="true" />
              <span className="truncate">
                {isExpanded ? 'Hide explanation' : `Why ${game.predicted_winner}?`}
              </span>
              {isExpanded ? (
                <ChevronUp size={16} className="flex-shrink-0" aria-hidden="true" />
              ) : (
                <ChevronDown size={16} className="flex-shrink-0" aria-hidden="true" />
              )}
            </button>
          )}
          
          {/* Expanded explanation */}
          {isExpanded && hasExplanation && (
            <div 
              className={`mt-3 p-3 bg-gray-50 rounded-lg border-l-4 ${getConfidenceBorderColor(game.confidence)} transition-all animate-fadeIn`}
              role="region"
              aria-label="Prediction explanation"
            >
              <p className="text-sm text-gray-700 leading-relaxed">
                {game.explanation}
              </p>
            </div>
          )}
        </div>
        
        {/* Status badge */}
        {showBadge && (
          <div className="mt-2 sm:mt-0 sm:ml-4 self-start sm:self-center">
            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${getBadgeClasses()}`}>
              {getBadgeText()}
            </span>
          </div>
        )}
      </div>
    </div>
  )
}
