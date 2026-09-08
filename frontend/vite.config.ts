import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Em desenvolvimento o Vite faz proxy para a API (uvicorn em :8000); em produção o build é servido
// pelo FastAPI em /painel e as chamadas são relativas à mesma origem.
const API = process.env.VITE_API_URL || 'http://localhost:8000'
const ROTAS_API = ['/status', '/bots', '/bot-control', '/backtest', '/inverse', '/logs', '/coins', '/indicadores',
  '/pontos-institucionais', '/orderblocks', '/institucional', '/api']

export default defineConfig({
  plugins: [react()],
  base: '/painel/',
  server: {
    port: 5173,
    proxy: Object.fromEntries(ROTAS_API.map((r) => [r, { target: API, changeOrigin: true }])),
  },
  build: { outDir: 'dist', sourcemap: false },
})
