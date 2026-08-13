import { useState, type CSSProperties } from 'react'
import { useHousehold } from '../hooks/useHousehold'
import Card from './ui/Card'
import SettingHeader from './ui/SettingHeader'

// Tarjeta "Tu pareja / familia": integrantes del hogar + invitar (Telegram/WhatsApp),
// respetando el plan. Reemplaza el "solo por /invitar en Telegram".
export default function HouseholdCard() {
  const { data: h, isLoading } = useHousehold()
  const [copied, setCopied] = useState(false)

  if (isLoading || !h) return null

  const copy = async () => {
    const link = h.telegram || h.whatsapp || ''
    if (!link) return
    try {
      await navigator.clipboard.writeText(link)
      setCopied(true); setTimeout(() => setCopied(false), 1600)
    } catch { /* ignore */ }
  }

  return (
    <Card style={{ display: 'grid', gap: 12 }}>
      <SettingHeader icon="ti-users" title="Tu pareja / familia" />

      {/* Integrantes */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {h.members.map((m) => (
          <span key={m.id} style={chip}>
            <span style={{ ...dot, background: m.color || 'var(--color-pollen)' }}>{m.name.slice(0, 1).toUpperCase()}</span>
            {m.name}{m.is_me ? ' (vos)' : ''}
          </span>
        ))}
      </div>

      {h.cap <= 1 ? (
        <p style={hint}>
          Tu plan es <b>individual</b>. Para compartir con tu pareja o familia (listas, gastos, agenda),
          actualizá a un plan <b>Pareja</b> o superior.
        </p>
      ) : h.slots <= 0 ? (
        <p style={hint}>
          Tu hogar está completo: <b>{h.current}/{h.cap}</b> integrantes para tu plan ({h.plan}).
          Actualizá el plan para sumar a más.
        </p>
      ) : (
        <>
          <p style={hint}>
            Te queda{h.slots !== 1 ? 'n' : ''} <b>{h.slots}</b> lugar{h.slots !== 1 ? 'es' : ''} (plan {h.plan}).
            Mandale el link a tu pareja; cuando lo abra, comparten todo.
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {h.whatsapp && (
              <a href={h.whatsapp} target="_blank" rel="noreferrer" style={waBtn}>
                <i className="ti ti-brand-whatsapp" aria-hidden /> Invitar por WhatsApp
              </a>
            )}
            {h.telegram && (
              <a href={h.telegram} target="_blank" rel="noreferrer" style={tgBtn}>
                <i className="ti ti-brand-telegram" aria-hidden /> Telegram
              </a>
            )}
            <button onClick={copy} style={copyBtn}>
              <i className={`ti ${copied ? 'ti-check' : 'ti-copy'}`} aria-hidden /> {copied ? 'Copiado' : 'Copiar link'}
            </button>
          </div>
        </>
      )}
    </Card>
  )
}

const hint: CSSProperties = { margin: 0, fontSize: 12.5, color: 'var(--color-sage)', lineHeight: 1.5 }
const chip: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 13,
  background: 'var(--color-mist)', borderRadius: 9999, padding: '4px 10px 4px 4px',
}
const dot: CSSProperties = {
  width: 22, height: 22, borderRadius: '50%', display: 'inline-flex', alignItems: 'center',
  justifyContent: 'center', fontSize: 11, fontWeight: 600, color: 'var(--voltage-on-dark, #1a1a1a)',
}
const baseBtn: CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, borderRadius: 10, padding: '9px 14px',
  fontSize: 13, fontWeight: 500, cursor: 'pointer', textDecoration: 'none', border: 'none', font: 'inherit',
}
const waBtn: CSSProperties = { ...baseBtn, background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)' }
const tgBtn: CSSProperties = { ...baseBtn, background: 'var(--color-mist)', color: 'var(--color-obsidian-ink)' }
const copyBtn: CSSProperties = { ...baseBtn, background: 'transparent', border: '1px solid var(--color-mist)', color: 'var(--color-sage)' }
