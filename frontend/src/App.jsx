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
import { getCurrentPath } from './utils/routing'

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
    const routes = {
      '/': <HomePage />,
      '/predictions': <PredictionsPage />,
      '/betting': <BettingPage />,
      '/betting-accuracy': <BettingAccuracyPage />,
      '/teams': <TeamsPage />,
      '/history': <HistoryPage />,
      '/accuracy': <AccuracyPage />,
    }

    return routes[currentPath] ?? <HomePage />
  }, [currentPath])

  return (
    <Layout currentPath={currentPath}>
      {currentPage}
    </Layout>
  )
}

export default App
