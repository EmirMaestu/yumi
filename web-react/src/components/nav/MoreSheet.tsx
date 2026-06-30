import { useNavigate } from 'react-router-dom'
import Sheet from '../ui/Sheet'
import { MORE_LINKS } from './navItems'
import { useMe } from '../../hooks/useMe'

// Hoja "Más": encabezado con tu perfil (→ Yo) + grilla de secciones.
export default function MoreSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const { data: me } = useMe()
  const go = (to: string) => { navigate(to); onClose() }
  const initial = (me?.name?.[0] ?? '·').toUpperCase()

  return (
    <Sheet open={open} onClose={onClose} title="Más">
      <button onClick={() => go('/yo')} style={header}>
        <span style={avatar}>{initial}</span>
        <span style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
          <span style={{ fontSize: 15, fontWeight: 500, color: 'var(--color-obsidian-ink)' }}>{me?.name ?? 'Mi cuenta'}</span>
          <span style={{ fontSize: 12.5, color: 'var(--color-voltage-ink, var(--color-sage))' }}>Ver perfil y ajustes →</span>
        </span>
      </button>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {MORE_LINKS.map((i) => (
          <button key={i.to} onClick={() => go(i.to)} style={tile}>
            <i className={`ti ${i.icon}`} style={{ fontSize: 22, color: 'var(--color-sage)' }} aria-hidden />
            <span style={{ fontSize: 14, fontWeight: 500 }}>{i.label}</span>
          </button>
        ))}
      </div>
    </Sheet>
  )
}

const header: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 11, width: '100%',
  background: 'none', border: 'none', cursor: 'pointer', font: 'inherit', textAlign: 'left',
  padding: '4px 2px 14px', marginBottom: 12, borderBottom: '1px solid var(--color-mist)',
}
const avatar: React.CSSProperties = {
  width: 38, height: 38, borderRadius: '50%', flexShrink: 0,
  background: 'var(--color-pollen)', color: 'var(--voltage-on-dark)',
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', fontSize: 15, fontWeight: 500,
}
const tile: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
  padding: '18px 10px', borderRadius: 14, border: '1px solid var(--color-mist)',
  background: 'var(--color-linen)', cursor: 'pointer', font: 'inherit', color: 'var(--color-obsidian-ink)',
}
