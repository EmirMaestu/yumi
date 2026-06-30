import { useState } from 'react'
import { getThemePref, setThemePref, type ThemePref } from '../lib/theme'
import Card from './ui/Card'

const OPTS: { v: ThemePref; label: string; icon: string }[] = [
  { v: 'system', label: 'Sistema', icon: 'ti-device-mobile' },
  { v: 'light', label: 'Claro', icon: 'ti-sun' },
  { v: 'dark', label: 'Oscuro', icon: 'ti-moon' },
]

export default function ThemeToggle() {
  const [pref, setPref] = useState<ThemePref>(getThemePref())
  const choose = (p: ThemePref) => { setThemePref(p); setPref(p) }
  return (
    <Card style={{ display: 'grid', gap: 8 }}>
      <div style={{ fontSize: 14, fontWeight: 600 }}>🎨 Tema</div>
      <div style={{ display: 'flex', gap: 4, background: 'var(--color-mist)', borderRadius: 10, padding: 3 }}>
        {OPTS.map((o) => (
          <button key={o.v} onClick={() => choose(o.v)} style={{
            flex: 1, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 5,
            padding: '8px 6px', borderRadius: 8, border: 'none', cursor: 'pointer', font: 'inherit', fontSize: 13,
            background: pref === o.v ? 'var(--color-linen)' : 'transparent',
            color: pref === o.v ? 'var(--color-obsidian-ink)' : 'var(--color-sage)',
            fontWeight: pref === o.v ? 500 : 400,
          }}>
            <i className={`ti ${o.icon}`} style={{ fontSize: 15 }} aria-hidden /> {o.label}
          </button>
        ))}
      </div>
    </Card>
  )
}
