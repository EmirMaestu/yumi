import { useState } from 'react'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    const res = await fetch('/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ username, password }),
    })
    if (res.ok) {
      location.assign('/app/')
    } else {
      const j = await res.json().catch(() => ({}))
      setError(j.detail || 'Credenciales inválidas')
    }
  }

  return (
    <main style={{ maxWidth: 360, margin: '0 auto', padding: '64px 24px' }}>
      <div className="cap">Tu vida en común, en un mensaje</div>
      <h1 className="num-serif" style={{ fontSize: 44, margin: '12px 0 8px' }}>Entrar</h1>
      <p style={{ fontSize: 13.5, color: 'var(--color-sage)', margin: '0 0 28px' }}>
        Usá el <b>usuario</b> y la <b>clave</b> que te dio el bot de Yumi (en Telegram o WhatsApp).
        La podés cambiar escribiéndole <code>/password</code> al bot.
      </p>
      <form onSubmit={onSubmit} style={{ display: 'grid', gap: 14 }}>
        <input aria-label="Usuario" placeholder="Usuario" value={username}
          onChange={(e) => setUsername(e.target.value)} style={inputStyle} />
        <input aria-label="Contraseña" type="password" placeholder="Contraseña" value={password}
          onChange={(e) => setPassword(e.target.value)} style={inputStyle} />
        {error && <div style={{ color: 'var(--color-error)', fontSize: 13 }}>{error}</div>}
        <button type="submit" style={ctaStyle}>Entrar →</button>
      </form>

      <div style={{ height: 1, background: 'var(--color-mist)', margin: '28px 0 18px' }} />
      <div style={{ fontSize: 13.5, color: 'var(--color-sage)', lineHeight: 1.5 }}>
        <b style={{ color: 'var(--color-obsidian-ink)' }}>¿Todavía no tenés cuenta?</b><br />
        Yumi es por invitación 🌱 Pedile el link a quien te invitó, o escribinos y arrancás ahí mismo:
        <div style={{ display: 'flex', gap: 10, marginTop: 12 }}>
          <a href={TELEGRAM_URL} style={altLinkStyle}><i className="ti ti-brand-telegram" aria-hidden /> Telegram</a>
          <a href={WHATSAPP_URL} style={altLinkStyle}><i className="ti ti-brand-whatsapp" aria-hidden /> WhatsApp</a>
        </div>
      </div>
    </main>
  )
}

const TELEGRAM_URL = 'https://t.me/assistant_emir_bot'
const WHATSAPP_URL = 'https://wa.me/5492615785056'
const altLinkStyle: React.CSSProperties = {
  flex: 1, textAlign: 'center', textDecoration: 'none', border: '1px solid var(--color-mist)',
  borderRadius: 10, padding: '10px 12px', fontSize: 14, color: 'var(--color-obsidian-ink)',
}

const inputStyle: React.CSSProperties = {
  border: '1px solid var(--color-mist)', borderRadius: 10, padding: '12px 14px',
  fontSize: 16, background: 'transparent', color: 'var(--color-obsidian-ink)',
}
const ctaStyle: React.CSSProperties = {
  background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none',
  borderRadius: 10, padding: '14px 18px', fontSize: 14, fontWeight: 500,
  boxShadow: 'var(--shadow-cta)', cursor: 'pointer',
}
