import { Navigate, Route, Routes } from 'react-router-dom'
import { TopBar } from './components/Layout'
import BotDetail from './screens/BotDetail'
import BotForm from './screens/BotForm'
import Dashboard from './screens/Dashboard'
import Historico from './screens/Historico'
import Mercado from './screens/Mercado'
import Pontos from './screens/Pontos'
import Range from './screens/Range'
import Sentimento from './screens/Sentimento'
import Trader from './screens/Trader'

export default function App() {
  return (
    <div className="app">
      <TopBar />
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/bots/novo" element={<BotForm />} />
          <Route path="/bots/:id" element={<BotDetail />} />
          <Route path="/bots/:id/editar" element={<BotForm />} />
          <Route path="/trader" element={<Trader />} />
          <Route path="/mercado" element={<Mercado />} />
          <Route path="/pontos" element={<Pontos />} />
          <Route path="/range" element={<Range />} />
          <Route path="/sentimento" element={<Sentimento />} />
          <Route path="/historico" element={<Historico />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
