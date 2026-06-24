import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useVencimientos } from '../hooks/useVencimientos'
import { useAccountsWithBalances, useAccountMutations } from '../hooks/useAccounts'
import { formatMoney } from '../lib/format'
import { type Account, type CicloTotal } from '../lib/types'
import Card from '../components/ui/Card'
import AlertPill from '../components/ui/AlertPill'
import { TarjetasSkeleton } from '../components/ui/skeletons'
import EmptyState from '../components/ui/EmptyState'
import ConfirmDialog from '../components/ui/ConfirmDialog'
import CardActions from '../components/ui/CardActions'
import AccountForm from '../components/AccountForm'

function cicloTotal(arr?: CicloTotal[]): number { return (arr ?? []).reduce((s, c) => s + c.total, 0) }
function arsBalance(acc: Account): number {
  return (acc.balances ?? []).find((b) => b.currency === 'ARS')?.balance ?? (acc.balances?.[0]?.balance ?? 0)
}

export default function Tarjetas() {
  const navigate = useNavigate()
  const venc = useVencimientos()
  const accounts = useAccountsWithBalances()
  const { remove } = useAccountMutations()

  const [editCard, setEditCard] = useState<Account | null>(null)
  const [deleteCard, setDeleteCard] = useState<Account | null>(null)

  const cards = accounts.data?.filter((a) => a.type === 'credito') ?? []

  if (accounts.isLoading) return <TarjetasSkeleton />
  if (cards.length === 0) return <EmptyState>No tenés tarjetas de crédito cargadas.</EmptyState>

  return (
    <div style={{ padding: '14px 18px 24px', display: 'grid', gap: 14 }}>
      <div className="cap">Tarjetas y cuotas</div>
      {cards.map((card) => {
        const v = venc.data?.find((x) => x.account_id === card.id)
        const deuda = arsBalance(card)
        const dias = v?.next_closing ? Math.ceil((new Date(v.next_closing).getTime() - Date.now()) / 86_400_000) : null
        const hasVenc = !!v
        return (
          <Card
            key={card.id}
            style={{ cursor: 'pointer' }}
            onClick={() => navigate(`/tarjetas/${card.id}`)}
          >
            {/* Header: name left, actions right */}
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <span style={{ fontSize: 16, fontWeight: 500, flex: 1 }}>{card.name}</span>
              <CardActions
                onEdit={() => setEditCard(card)}
                onDelete={() => setDeleteCard(card)}
              />
            </div>
            {/* Deuda — primary number */}
            <div style={{ marginTop: 10 }}>
              <div className="cap">Deuda</div>
              <div className="num-serif" style={{ fontSize: 30, marginTop: 4 }}>{formatMoney(deuda)}</div>
            </div>
            {/* Secondary line */}
            {hasVenc ? (
              <div style={{ marginTop: 6, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 12, color: 'var(--color-sage)' }}>
                  Próximo resumen · cierra {v!.next_closing!.slice(8, 10)}/{v!.next_closing!.slice(5, 7)}{' '}
                  {formatMoney(cicloTotal(v!.ciclo_abierto))}
                </span>
                {dias !== null && dias >= 0 && dias <= 5 && (
                  <AlertPill>cierra en {dias} día{dias === 1 ? '' : 's'}</AlertPill>
                )}
              </div>
            ) : (
              <div style={{ marginTop: 6, fontSize: 12, color: 'var(--color-sage)' }}>
                Cargá cierre y vencimiento para ver el resumen
              </div>
            )}
          </Card>
        )
      })}

      {/* Edit modal — uses AccountForm with credit type defaults */}
      <AccountForm
        account={editCard}
        open={editCard !== null}
        onClose={() => setEditCard(null)}
        defaultType="credito"
      />

      {/* Delete confirm */}
      <ConfirmDialog
        open={deleteCard !== null}
        onOpenChange={(o) => { if (!o) setDeleteCard(null) }}
        title="¿Borrar esta tarjeta?"
        description={deleteCard ? `Se eliminará "${deleteCard.name}".` : ''}
        onConfirm={() => {
          if (deleteCard) remove.mutate(deleteCard.id)
          setDeleteCard(null)
        }}
      />
    </div>
  )
}
