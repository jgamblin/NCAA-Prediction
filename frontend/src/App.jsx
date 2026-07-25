import { useEffect, useMemo, useState } from 'react'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import PredictionsPage from './pages/PredictionsPage'
import BettingPage from './pages/BettingPage'
import BettingAccuracyPage from './pages/BettingAccuracyPage'
import TeamsPage from './pages/TeamsPage'
import HistoryPage from './pages/HistoryPage'
import AccuracyPage from './pages/AccuracyPage'
import './styles/animations.css'
import { buildAppHref, getCurrentPath } from './utils/routing'

const routes = {
  '/': <HomePage />,
  '/predictions': <PredictionsPage />,
  '/betting': <BettingPage />,
  '/betting-accuracy': <BettingAccuracyPage />,
  '/teams': <TeamsPage />,
  '/history': <HistoryPage />,
  '/accuracy': <AccuracyPage />,
}

function NotFoundPage() {
  return (
    <div className="card text-center py-12">
      <h2 className="text-2xl font-bold text-gray-900">Page not found</h2>
      <p className="mt-3 text-gray-600">The page you requested does not exist.</p>
      <a href={buildAppHref('/')} className="btn btn-primary inline-flex items-center mt-6">
        Return home
      </a>
    </div>
  )
}

function App() {
  const [currentPath, setCurrentPath] = useState(() => getCurrentPath())

  useEffect(() => {
    const handleLocationChange = () => setCurrentPath(getCurrentPath())

    window.addEventListener('hashchange', handleLocationChange)
    window.addEventListener('popstate', handleLocationChange)

    return () => {
      window.removeEventListener('hashchange', handleLocationChange)
      window.removeEventListener('popstate', handleLocationChange)
    }
  }, [])

  const currentPage = useMemo(() => {
    return routes[currentPath] ?? <NotFoundPage />
  }, [currentPath])

  return (
    <Layout currentPath={currentPath}>
      {currentPage}
    </Layout>
  )
}

export default App
