import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import PredictionsPage from './pages/PredictionsPage'
import BettingPage from './pages/BettingPage'
import BettingAccuracyPage from './pages/BettingAccuracyPage'
import TeamsPage from './pages/TeamsPage'
import HistoryPage from './pages/HistoryPage'
import AccuracyPage from './pages/AccuracyPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/predictions" element={<PredictionsPage />} />
        <Route path="/betting" element={<BettingPage />} />
        <Route path="/betting-accuracy" element={<BettingAccuracyPage />} />
        <Route path="/teams" element={<TeamsPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/accuracy" element={<AccuracyPage />} />
      </Routes>
    </Layout>
  )
}

export default App
