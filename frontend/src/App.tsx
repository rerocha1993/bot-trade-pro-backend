import { Navigate, Route, Routes } from 'react-router-dom'
import { TopBar } from './components/Layout'
import Avisos from './screens/Avisos'
import Grafico from './screens/Grafico'
import Carteira from './screens/Carteira'
import Robos from './screens/Robos'

export default function App() {
  return (
    <div className="app">
      <TopBar />
      <main className="main">
        <Routes>
          <Route path="/" element={<Avisos />} />
          <Route path="/grafico" element={<Grafico />} />
          {/* a aba Nuvens virou camadas da tela Gráfico (28/10/2026) */}
          <Route path="/nuvens" element={<Navigate to="/grafico?s=COINBASE:BTC-USD" replace />} />
          <Route path="/robos" element={<Robos />} />
          <Route path="/carteira" element={<Carteira />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
