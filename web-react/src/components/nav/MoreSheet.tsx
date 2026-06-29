import { useNavigate } from 'react-router-dom'
import Sheet from '../ui/Sheet'
import { MORE_LINKS } from './navItems'

// Hoja "Más": grilla con las secciones secundarias (Tareas/Listas/Hábitos/Notas/Yo).
export default function MoreSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate()
  const go = (to: string) => { navigate(to); onClose() }
  return (
    <Sheet open={open} onClose={onClose} title="Más">
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

const tile: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8,
  padding: '18px 10px', borderRadius: 14, border: '1px solid var(--color-mist)',
  background: 'var(--color-linen)', cursor: 'pointer', font: 'inherit', color: 'var(--color-obsidian-ink)',
}
