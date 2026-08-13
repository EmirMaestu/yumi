import { useEffect, useState, type CSSProperties } from 'react'
import Sheet from './ui/Sheet'
import Select from './ui/Select'
import { useAccounts } from '../hooks/useAccounts'
import { useCategories } from '../hooks/useCategories'
import { useQuickExpense } from '../hooks/useTransactions'
import { parseAmount } from '../lib/parseAmount'
import { todayISODate, dateToNoonISO } from '../lib/format'

// Diseño 1c: "hoja de gasto en un toque". Entra con el tipo resuelto (gasto),
// teclado numérico y foco en el monto; cuenta y categoría arrancan con el último
// uso (localStorage). "Cambiar tipo" cae a la hoja completa (ingreso/transfer/etc.).
const LAST_ACC = 'yumi_last_account'
const LAST_CAT = 'yumi_last_category'

// Formatea el string en construcción (dígitos + una coma decimal) a "$1.234,5".
function displayAmount(raw: string): string {
  if (!raw) return '$0'
  const [intPart, decPart] = raw.split(',')
  const grouped = (intPart || '0').replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return '$' + grouped + (raw.includes(',') ? ',' + (decPart ?? '') : '')
}

export default function KeypadExpenseSheet({ open, onClose, onChangeType }: {
  open: boolean; onClose: () => void; onChangeType: () => void
}) {
  const accounts = useAccounts()
  const categories = useCategories()
  const quick = useQuickExpense()
  const [raw, setRaw] = useState('')
  const [accountId, setAccountId] = useState<number | undefined>()
  const [categoryId, setCategoryId] = useState<number | undefined>()

  // Al abrir: limpiar monto y precargar cuenta/categoría del último uso (o la 1ª cuenta).
  useEffect(() => {
    if (!open) return
    setRaw('')
    const accs = accounts.data ?? []
    const lastAcc = Number(localStorage.getItem(LAST_ACC))
    setAccountId(accs.some((a) => a.id === lastAcc) ? lastAcc : accs[0]?.id)
    const lastCat = Number(localStorage.getItem(LAST_CAT))
    const cats = categories.data ?? []
    setCategoryId(cats.some((c) => c.id === lastCat) ? lastCat : undefined)
  }, [open, accounts.data, categories.data])

  const value = parseAmount(raw)
  const canSave = Number.isFinite(value) && value > 0 && !!accountId && !quick.isPending

  function press(key: string) {
    setRaw((cur) => {
      if (key === 'del') return cur.slice(0, -1)
      if (key === ',') return cur.includes(',') ? cur : (cur === '' ? '0,' : cur + ',')
      // dígito: límite de 2 decimales y de largo total razonable
      const dec = cur.split(',')[1]
      if (cur.includes(',') && dec && dec.length >= 2) return cur
      if (cur.replace(',', '').length >= 12) return cur
      if (cur === '0') return key // evita ceros a la izquierda
      return cur + key
    })
  }

  function save() {
    if (!canSave) return
    quick.mutate(
      { type: 'gasto', amount: value, currency: 'ARS', account_id: accountId, category_id: categoryId, occurred_at: dateToNoonISO(todayISODate()) },
      { onSuccess: () => {
        if (accountId) localStorage.setItem(LAST_ACC, String(accountId))
        if (categoryId) localStorage.setItem(LAST_CAT, String(categoryId)); else localStorage.removeItem(LAST_CAT)
        onClose()
      } },
    )
  }

  const accName = (accounts.data ?? []).find((a) => a.id === accountId)?.name
  const catName = (categories.data ?? []).find((c) => c.id === categoryId)?.name
  const accountOpts = (accounts.data ?? []).map((a) => ({ value: String(a.id), label: a.name }))
  const categoryOpts = [{ value: '', label: 'Sin categoría' }, ...(categories.data ?? []).map((c) => ({ value: String(c.id), label: c.name }))]

  const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', ',', '0', 'del']

  return (
    <Sheet open={open} onClose={onClose} title="Nuevo gasto">
      <div style={{ display: 'grid', gap: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: -8 }}>
          <button type="button" onClick={onChangeType} style={changeType}>Cambiar tipo <i className="ti ti-chevron-down" style={{ fontSize: 13 }} aria-hidden /></button>
        </div>

        {/* Monto grande + resumen de la línea */}
        <div style={{ textAlign: 'center', padding: '18px 0 6px' }}>
          <div className="num-serif" style={{ fontSize: 46, lineHeight: 1 }}>
            {displayAmount(raw)}<span style={{ color: 'var(--color-voltage)' }}>|</span>
          </div>
          <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 8 }}>
            {[accName, catName ?? 'Sin categoría', 'Hoy'].filter(Boolean).join(' · ')}
          </div>
        </div>

        {/* Chips: cuenta y categoría (último uso), fecha fija Hoy */}
        <div style={{ display: 'flex', gap: 7, justifyContent: 'center', flexWrap: 'wrap', padding: '6px 0 2px' }}>
          <Select value={accountId ? String(accountId) : undefined} onValueChange={(v) => setAccountId(Number(v))} options={accountOpts} placeholder="Cuenta…" ariaLabel="Cuenta" style={chipSelect} />
          <Select value={categoryId ? String(categoryId) : ''} onValueChange={(v) => setCategoryId(v ? Number(v) : undefined)} options={categoryOpts} placeholder="Categoría…" ariaLabel="Categoría" style={chipSelect} />
          <span style={chipStatic}>Hoy</span>
        </div>

        {/* Teclado numérico */}
        <div style={{ borderTop: '1px solid var(--color-mist)', marginTop: 12, paddingTop: 12 }}>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8 }}>
            {KEYS.map((k) => (
              <button key={k} type="button" onClick={() => press(k)} style={key(k)} aria-label={k === 'del' ? 'Borrar' : k}>
                {k === 'del' ? <i className="ti ti-backspace" style={{ fontSize: 20 }} aria-hidden /> : k}
              </button>
            ))}
          </div>
          <button type="button" onClick={save} disabled={!canSave} style={{ ...cta, opacity: canSave ? 1 : 0.5 }}>
            {quick.isPending ? 'Guardando…' : 'Guardar gasto'}
          </button>
          <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--color-sage)', marginTop: 9 }}>
            O mandale un mensaje al bot: “nafta 12.400”
          </div>
        </div>
      </div>
    </Sheet>
  )
}

const changeType: CSSProperties = { background: 'none', border: 'none', cursor: 'pointer', font: 'inherit', fontSize: 12, fontWeight: 500, color: 'var(--color-sage)', display: 'inline-flex', alignItems: 'center', gap: 3 }
const chipSelect: CSSProperties = { fontSize: 11.5, fontWeight: 600, padding: '7px 12px', borderRadius: 999 }
const chipStatic: CSSProperties = { fontSize: 11.5, fontWeight: 600, color: 'var(--color-obsidian-ink)', border: '1px solid var(--color-mist)', borderRadius: 999, padding: '8px 14px', alignSelf: 'center' }
const cta: CSSProperties = { marginTop: 10, width: '100%', background: 'var(--color-voltage)', color: 'var(--voltage-on-dark)', border: 'none', borderRadius: 14, padding: 15, fontWeight: 600, fontSize: 15, cursor: 'pointer', font: 'inherit', boxShadow: 'var(--shadow-cta)' }

function key(k: string): CSSProperties {
  return {
    background: 'var(--color-mist)', border: 'none', borderRadius: 11, padding: '13px 0',
    textAlign: 'center', fontSize: 20, fontWeight: 500, cursor: 'pointer', font: 'inherit',
    color: k === ',' || k === 'del' ? 'var(--color-sage)' : 'var(--color-obsidian-ink)',
  }
}
