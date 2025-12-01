import { Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import HomePage from './pages/HomePage'
import PredictionsPage from './pages/PredictionsPage'
import BettingPage from './pages/BettingPage'
import TeamsPage from './pages/TeamsPage'
import HistoryPage from './pages/HistoryPage'

function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/predictions" element={<PredictionsPage />} />
        <Route path="/betting" element={<BettingPage />} />
        <Route path="/teams" element={<TeamsPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Routes>
    </Layout>
  )
}

export default App
