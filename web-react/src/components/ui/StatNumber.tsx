import { Link } from 'react-router-dom'

// Si recibe `to`, el stat se vuelve clickeable (navegación contextual).
export default function StatNumber({ label, children, to }: { label: string; children: React.ReactNode; to?: string }) {
  const inner = (
    <>
      <div className="cap" style={{ fontSize: 10.5 }}>{label}</div>
      <div style={{ fontSize: 15, fontWeight: 500, marginTop: 3 }}>{children}</div>
    </>
  )
  if (to) return <Link to={to} style={{ flex: 1, textDecoration: 'none', color: 'inherit' }}>{inner}</Link>
  return <div style={{ flex: 1 }}>{inner}</div>
}
