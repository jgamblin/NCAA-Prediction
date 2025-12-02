import { Link, useLocation } from 'react-router-dom'
import { Home, TrendingUp, DollarSign, Users, History, Target } from 'lucide-react'

export default function Layout({ children }) {
  const location = useLocation()
  
  const navItems = [
    { path: '/', label: 'Home', icon: Home },
    { path: '/predictions', label: 'Predictions', icon: TrendingUp },
    { path: '/betting', label: 'Betting', icon: DollarSign },
    { path: '/teams', label: 'Teams', icon: Users },
    { path: '/history', label: 'History', icon: History },
    { path: '/accuracy', label: 'Accuracy', icon: Target },
  ]
  
  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="container mx-auto px-4">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-primary-600 rounded-lg flex items-center justify-center">
                <span className="text-white text-2xl font-bold">🏀</span>
              </div>
              <div>
                <h1 className="text-xl font-bold text-gray-900">NCAA Predictions</h1>
                <p className="text-xs text-gray-500">Machine Learning Powered</p>
              </div>
            </Link>
            
            {/* Navigation */}
            <nav className="hidden md:flex items-center space-x-1">
              {navItems.map(({ path, label, icon: Icon }) => {
                const isActive = location.pathname === path
                return (
                  <Link
                    key={path}
                    to={path}
                    className={`
                      flex items-center space-x-2 px-4 py-2 rounded-lg
                      transition-colors duration-200
                      ${isActive
                        ? 'bg-primary-50 text-primary-700 font-medium'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                      }
                    `}
                  >
                    <Icon size={18} />
                    <span>{label}</span>
                  </Link>
                )
              })}
            </nav>
          </div>
        </div>
      </header>
      
      {/* Mobile Navigation */}
      <nav className="md:hidden bg-white border-b">
        <div className="container mx-auto px-4">
          <div className="flex justify-around py-2">
            {navItems.map(({ path, label, icon: Icon }) => {
              const isActive = location.pathname === path
              return (
                <Link
                  key={path}
                  to={path}
                  className={`
                    flex flex-col items-center space-y-1 px-3 py-2 rounded-lg
                    ${isActive
                      ? 'text-primary-600'
                      : 'text-gray-500'
                    }
                  `}
                >
                  <Icon size={20} />
                  <span className="text-xs">{label}</span>
                </Link>
              )
            })}
          </div>
        </div>
      </nav>
      
      {/* Main Content */}
      <main className="flex-1 container mx-auto px-4 py-6">
        {children}
      </main>
      
      {/* Footer */}
      <footer className="bg-gray-100 border-t mt-12">
        <div className="container mx-auto px-4 py-6">
          <div className="flex flex-col md:flex-row justify-between items-center space-y-4 md:space-y-0">
            <div className="text-center md:text-left">
              <p className="text-sm text-gray-600">
                NCAA Basketball Predictions powered by Machine Learning
              </p>
              <p className="text-xs text-gray-500 mt-1">
                Data updated daily via GitHub Actions
              </p>
            </div>
            <div className="flex items-center space-x-4 text-sm text-gray-600">
              <a
                href="https://github.com/jgamblin/NCAA-Prediction"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-primary-600 transition-colors"
              >
                GitHub
              </a>
              <span>•</span>
              <span>177x faster with DuckDB</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  )
}
