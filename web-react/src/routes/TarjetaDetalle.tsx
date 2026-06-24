import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { useAccountsWithBalances, useAccountMutations } from '../hooks/useAccounts'
import { useVencimientos } from '../hooks/useVencimientos'
import { useRecurring, useRecurringMutations } from '../hooks/useRecurring'
import { type Account, type CicloTotal, type Recurring } from '../lib/types'
import { formatMoney } from '../lib/format'
import Card from '../components/ui/Card'
import Modal from '../components/ui/Modal'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import CardActions from '../components/ui/CardActions'
import { TarjetaDetalleSkeleton } from '../components/ui/skeletons'
import EmptyState from '../components/ui/EmptyState'
import AccountForm from '../components/AccountForm'

function cicloTotal(arr?: CicloTotal[]): number { return (arr ?? []).reduce((s, c) => s + c.total, 0) }
function arsBalance(acc: Account): number {
  return (acc.balances ?? []).find((b) => b.currency === 'ARS')?.balance ?? (acc.balances?.[0]?.balance ?? 0)
}

// ---- Cuota form types ----
interface CuotaForm {
  description: string
  amount: number
  total_installments: number
  installments_fired: number
}

function CuotaModal({
  open,
  onClose,
  initial,
  title,
  onSubmit,
}: {
  open: boolean
  onClose: () => void
  initial?: Partial<CuotaForm>
  title: string
  onSubmit: (data: CuotaForm) => void
}) {
  const { register, handleSubmit, reset, watch } = useForm<CuotaForm>({
    defaultValues: { description: '', amount: 0, total_installments: 1, installments_fired: 0, ...initial },
  })
  const totalWatched = watch('total_installments')
  const submit = (data: CuotaForm) => { onSubmit(data); reset() }
  return (
    <Modal open={open} onClose={() => { onClose(); reset() }} title={title}>
      <form onSubmit={handleSubmit(submit)} style={{ display: 'grid', gap: 12 }}>
        <input
          {...register('description', { required: true })}
          placeholder="Descripción"
          style={inputStyle}
        />
        <label style={labelStyle}>
          Monto por cuota
          <input
            type="number"
            {...register('amount', { valueAsNumber: true, min: 0 })}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Total de cuotas
          <input
            type="number"
            {...register('total_installments', { valueAsNumber: true, min: 1 })}
            style={inputStyle}
          />
        </label>
        <label style={labelStyle}>
          Cuotas ya pagadas
          <input
            type="number"
            {...register('installments_fired', { valueAsNumber: true, min: 0, max: totalWatched })}
            style={inputStyle}
          />
          <span style={{ fontSize: 11, color: 'var(--color-sage)', marginTop: 2 }}>
            Cuántas de las {totalWatched ?? '?'} ya pagaste
          </span>
        </label>
        <button type="submit" style={ctaBtn}>Guardar</button>
      </form>
    </Modal>
  )
}

export default function TarjetaDetalle() {
  const { id } = useParams()
  const accId = Number(id)
  const navigate = useNavigate()

  const accounts = useAccountsWithBalances()
  const vencimientos = useVencimientos()
  const recurring = useRecurring()
  const { remove: removeAccount } = useAccountMutations()
  const { create, update, remove } = useRecurringMutations()

  const [editAccountOpen, setEditAccountOpen] = useState(false)
  const [deleteAccountOpen, setDeleteAccountOpen] = useState(false)
  const [addCuotaOpen, setAddCuotaOpen] = useState(false)
  const [editCuota, setEditCuota] = useState<Recurring | null>(null)
  const [deleteCuota, setDeleteCuota] = useState<Recurring | null>(null)

  const isLoading = accounts.isLoading || vencimientos.isLoading || recurring.isLoading

  if (isLoading) {
    return <TarjetaDetalleSkeleton />
  }

  const account = accounts.data?.find((a) => a.id === accId) ?? null
  const venc = vencimientos.data?.find((v) => v.account_id === accId)
  const cuotas = (recurring.data ?? []).filter(
    (r) => r.account_id === accId && r.total_installments,
  )

  if (!account) {
    return (
      <div style={{ padding: 18 }}>
        <Link to="/tarjetas" style={backLinkStyle}>← Tarjetas</Link>
        <EmptyState>Tarjeta no encontrada.</EmptyState>
      </div>
    )
  }

  // Money calculations
  const deuda = arsBalance(account)
  const abierto = cicloTotal(venc?.ciclo_abierto)
  const cerrado = cicloTotal(venc?.ciclo_cerrado)
  const enCuotas = cuotas.reduce(
    (s, r) => s + r.amount * ((r.total_installments ?? 0) - (r.installments_fired ?? 0)),
    0,
  )

  const fmtDay = (dateStr?: string) =>
    dateStr ? `${dateStr.slice(8, 10)}/${dateStr.slice(5, 7)}` : '—'

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 16 }}>
      {/* Back link + header */}
      <div>
        <Link to="/tarjetas" style={backLinkStyle}>← Tarjetas</Link>
        <div style={{ display: 'flex', alignItems: 'center', marginTop: 8 }}>
          <h1 style={{ flex: 1, fontSize: 22, fontWeight: 600, margin: 0 }}>{account.name}</h1>
          <CardActions
            onEdit={() => setEditAccountOpen(true)}
            onDelete={() => setDeleteAccountOpen(true)}
          />
        </div>
      </div>

      {/* Money summary */}
      <Card>
        {/* HERO: Deuda total */}
        <div style={{ marginBottom: 16 }}>
          <div className="cap" style={{ marginBottom: 4 }}>Deuda total</div>
          <div className="num-serif" style={{ fontSize: 34 }}>{formatMoney(deuda)}</div>
        </div>
        <div style={{ height: 1, background: 'var(--color-mist)', marginBottom: 14 }} />
        {/* Stats row: 3 columns */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
          <div>
            <div className="cap" style={{ fontSize: 10 }}>
              Próximo resumen{venc?.next_closing ? ` (cierra ${fmtDay(venc.next_closing)})` : ''}
            </div>
            <div className="num-serif" style={{ fontSize: 16, marginTop: 2 }}>{formatMoney(abierto)}</div>
            {venc?.next_due && (
              <div style={{ fontSize: 10, color: 'var(--color-sage)', marginTop: 2 }}>
                vence {fmtDay(venc.next_due)}
              </div>
            )}
          </div>
          <div>
            <div className="cap" style={{ fontSize: 10 }}>Resumen cerrado a pagar</div>
            <div className="num-serif" style={{ fontSize: 16, marginTop: 2 }}>{formatMoney(cerrado)}</div>
          </div>
          <div>
            <div className="cap" style={{ fontSize: 10 }}>Comprometido a futuro</div>
            <div className="num-serif" style={{ fontSize: 16, marginTop: 2 }}>{formatMoney(enCuotas)}</div>
          </div>
        </div>
        {/* Explainer */}
        <div style={{ marginTop: 12, fontSize: 11, color: 'var(--color-sage)', fontStyle: 'italic' }}>
          Lo que gastás en el ciclo en curso pasa a "a pagar" cuando la tarjeta cierra.
        </div>
      </Card>

      {/* Cuotas section */}
      <div>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
          <div className="cap" style={{ flex: 1 }}>Cuotas</div>
          <button onClick={() => setAddCuotaOpen(true)} style={ghostBtn}>+ Agregar cuota</button>
        </div>

        {cuotas.length === 0
          ? <EmptyState>Sin cuotas activas.</EmptyState>
          : cuotas.map((r) => {
            const fired = r.installments_fired ?? 0
            const total = r.total_installments ?? 0
            const restante = r.amount * (total - fired)
            const isPaused = r.active === 0
            return (
              <Card
                key={r.id}
                style={{ marginBottom: 10, opacity: isPaused ? 0.55 : 1 }}
              >
                <div style={{ display: 'flex', alignItems: 'center' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{r.description}</div>
                    <div style={{ fontSize: 12, color: 'var(--color-sage)', marginTop: 2 }}>
                      {fired}/{total} cuotas · {formatMoney(r.amount, r.currency)} c/u
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
                    <button
                      onClick={() =>
                        update.mutate({ id: r.id, active: isPaused ? 1 : 0 })
                      }
                      style={pauseBtn}
                    >
                      {isPaused ? 'Reactivar' : 'Pausar'}
                    </button>
                    <CardActions
                      onEdit={() => setEditCuota(r)}
                      onDelete={() => setDeleteCuota(r)}
                    />
                  </div>
                </div>
                <div style={{ marginTop: 8, fontSize: 13 }}>
                  Total restante:{' '}
                  <span className="num-serif" style={{ fontSize: 16 }}>{formatMoney(restante, r.currency)}</span>
                </div>
              </Card>
            )
          })
        }
      </div>

      {/* Edit account modal */}
      <AccountForm
        account={account}
        open={editAccountOpen}
        onClose={() => setEditAccountOpen(false)}
        defaultType="credito"
      />

      {/* Delete account confirm */}
      <ConfirmDialog
        open={deleteAccountOpen}
        onOpenChange={(o) => { if (!o) setDeleteAccountOpen(false) }}
        title="¿Borrar esta tarjeta?"
        description={`Se eliminará "${account.name}".`}
        onConfirm={() => {
          removeAccount.mutate(account.id)
          setDeleteAccountOpen(false)
          navigate('/tarjetas')
        }}
      />

      {/* Add cuota modal */}
      <CuotaModal
        open={addCuotaOpen}
        onClose={() => setAddCuotaOpen(false)}
        title="Nueva cuota"
        onSubmit={(data) => {
          create.mutate({
            description: data.description,
            amount: data.amount,
            account_id: accId,
            day_of_month: 1,
            total_installments: data.total_installments,
            installments_fired: data.installments_fired,
            currency: 'ARS',
          })
          setAddCuotaOpen(false)
        }}
      />

      {/* Edit cuota modal */}
      <CuotaModal
        open={editCuota !== null}
        onClose={() => setEditCuota(null)}
        title="Editar cuota"
        initial={
          editCuota
            ? {
              description: editCuota.description,
              amount: editCuota.amount,
              total_installments: editCuota.total_installments ?? 1,
              installments_fired: editCuota.installments_fired ?? 0,
            }
            : undefined
        }
        onSubmit={(data) => {
          if (editCuota) {
            update.mutate({
              id: editCuota.id,
              description: data.description,
              amount: data.amount,
              total_installments: data.total_installments,
              installments_fired: data.installments_fired,
            })
          }
          setEditCuota(null)
        }}
      />

      {/* Delete cuota confirm */}
      <ConfirmDialog
        open={deleteCuota !== null}
        onOpenChange={(o) => { if (!o) setDeleteCuota(null) }}
        title="¿Borrar esta cuota?"
        description={deleteCuota ? `Se eliminará "${deleteCuota.description}".` : ''}
        onConfirm={() => {
          if (deleteCuota) remove.mutate(deleteCuota.id)
          setDeleteCuota(null)
        }}
      />
    </div>
  )
}

const backLinkStyle: React.CSSProperties = {
  fontSize: 13,
  color: 'var(--color-sage)',
  textDecoration: 'none',
}
const ghostBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--color-mist)',
  borderRadius: 10,
  padding: '7px 14px',
  fontSize: 13,
  cursor: 'pointer',
}
const ctaBtn: React.CSSProperties = {
  background: 'var(--color-voltage)',
  color: 'var(--voltage-on-dark)',
  border: 'none',
  borderRadius: 10,
  padding: '14px',
  fontWeight: 500,
  cursor: 'pointer',
}
const inputStyle: React.CSSProperties = {
  border: '1px solid var(--color-mist)',
  borderRadius: 10,
  padding: '10px 12px',
  fontSize: 14,
  background: 'var(--color-linen)',
  width: '100%',
  boxSizing: 'border-box',
}
const labelStyle: React.CSSProperties = { display: 'grid', gap: 4, fontSize: 13, color: 'var(--color-sage)' }
const pauseBtn: React.CSSProperties = {
  background: 'transparent',
  border: '1px solid var(--color-mist)',
  borderRadius: 8,
  padding: '3px 10px',
  fontSize: 12,
  cursor: 'pointer',
  color: 'var(--color-sage)',
}
