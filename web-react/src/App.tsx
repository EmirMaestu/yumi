import { Routes, Route, Navigate } from 'react-router-dom'
import AppLayout from './components/nav/AppLayout'
import Login from './routes/Login'
import Hoy from './routes/Hoy'
import Inicio from './routes/Inicio'
import Movimientos from './routes/Movimientos'
import Tarjetas from './routes/Tarjetas'
import TarjetaDetalle from './routes/TarjetaDetalle'
import Cuentas from './routes/Cuentas'
import Categorias from './routes/Categorias'
import Perfil from './routes/Perfil'
import Recurrentes from './routes/Recurrentes'
import Tareas from './routes/Tareas'
import Notas from './routes/Notas'
import Habitos from './routes/Habitos'
import Listas from './routes/Listas'
import Agenda from './routes/Agenda'
import Buscar from './routes/Buscar'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<AppLayout />}>
        <Route path="/" element={<Hoy />} />
        <Route path="/finanzas" element={<Inicio />} />
        <Route path="/movimientos" element={<Movimientos />} />
        <Route path="/tarjetas" element={<Tarjetas />} />
        <Route path="/tarjetas/:id" element={<TarjetaDetalle />} />
        <Route path="/cuentas" element={<Cuentas />} />
        <Route path="/categorias" element={<Categorias />} />
        <Route path="/perfil" element={<Perfil />} />
        <Route path="/recurrentes" element={<Recurrentes />} />
        <Route path="/tareas" element={<Tareas />} />
        <Route path="/notas" element={<Notas />} />
        <Route path="/habitos" element={<Habitos />} />
        <Route path="/listas" element={<Listas />} />
        <Route path="/agenda" element={<Agenda />} />
        <Route path="/buscar" element={<Buscar />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
