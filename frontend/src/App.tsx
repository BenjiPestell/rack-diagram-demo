import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Designer from './components/designer/Designer'
import Inspector from './components/inspector/Inspector'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/"               element={<Designer />} />
        <Route path="/rack_inspector" element={<Inspector />} />
      </Routes>
    </BrowserRouter>
  )
}
