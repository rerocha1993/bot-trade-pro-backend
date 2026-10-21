import { Navigate, Route, Routes } from 'react-router-dom'
import { TopBar } from './components/Layout'
import Avisos from './screens/Avisos'
import Nuvens from './screens/Nuvens'
import Robos from './screens/Robos'

export default function App() {
  return (
    <div className="app">
      <TopBar />
      <main className="main">
        <Routes>
          <Route path="/" element={<Avisos />} />
          <Route path="/nuvens" element={<Nuvens />} />
          <Route path="/robos" element={<Robos />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  )
}
