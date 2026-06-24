import http from 'node:http'

const day = 86400000
const fmt = (d) => new Date(d).toISOString().slice(0, 10)
const now = Date.now()

const routes = {
  'GET /api/me': { id: 1, name: 'Emir', username: 'emir', color: '#2bee4b', scope: 'both', others: [{ name: 'Lisa', scope_value: 'user:Lisa' }] },
  'GET /api/overview2': {
    patrimonio_ars: 2480500, patrimonio_usd: 2067, blue: 1200,
    kpis: { gasto_mes: 612300, gasto_prev_alt: 540000, ingreso_mes: 980000, deuda_tarjetas: 340000, cuotas_futuras: 340000, cuotas_n: 8, disponible: 1140000 },
    cashflow: [
      { ym: '2026-02', ingresos: 900000, gastos: 610000 },
      { ym: '2026-03', ingresos: 950000, gastos: 705000 },
      { ym: '2026-04', ingresos: 980000, gastos: 640000 },
      { ym: '2026-05', ingresos: 980000, gastos: 590000 },
      { ym: '2026-06', ingresos: 980000, gastos: 612300 },
    ],
    hoy: [
      { tipo: 'evento', titulo: 'Cena con los viejos', sub: 'Casa de mamá', hora: '21:00' },
      { tipo: 'recordatorio', titulo: 'Llamar al plomero', sub: 'Recordatorio', hora: '10:30' },
      { tipo: 'tarea', titulo: 'Pagar el alquiler', sub: 'Tarea · prioridad alta', hora: 'hoy' },
      { tipo: 'recurrente', titulo: 'Movistar $7.000', sub: 'Recurrente · se cobra hoy', hora: 'auto' },
    ],
    por_categoria: [
      { cat: 'Comida', color: '#516254', total: 210000 },
      { cat: 'Transporte', total: 98000 },
      { cat: 'Servicios', total: 76000 },
      { cat: 'Ocio', total: 54000 },
      { cat: 'Salud', total: 39000 },
    ],
    mes_nombre: 'junio', year: 2026, dia: 23,
  },
  'GET /api/vencimientos': [
    { account_id: 1, account_name: 'Visa Galicia', icon: null, last_closing: fmt(now - 27 * day), next_closing: fmt(now + 3 * day), next_due: fmt(now + 13 * day), ciclo_cerrado: [{ currency: 'ARS', total: 145000 }], ciclo_abierto: [{ currency: 'ARS', total: 62000 }] },
    { account_id: 2, account_name: 'Naranja', next_closing: fmt(now + 9 * day), next_due: fmt(now + 19 * day), ciclo_cerrado: [{ currency: 'ARS', total: 88500 }], ciclo_abierto: [{ currency: 'ARS', total: 21000 }] },
    { account_id: 3, account_name: 'Santander', next_closing: fmt(now + 1 * day), next_due: fmt(now + 11 * day), ciclo_cerrado: [{ currency: 'ARS', total: 106500 }], ciclo_abierto: [] },
  ],
  'GET /api/transactions': {
    items: [
      { id: 101, type: 'gasto', amount: 5400, currency: 'ARS', description: 'Coca y facturas', occurred_at: '2026-06-22', account_id: 4, acc_name: 'Mercado Pago', cat_name: 'Comida' },
      { id: 102, type: 'gasto', amount: 38000, currency: 'ARS', description: 'Nafta', occurred_at: '2026-06-21', account_id: 2, acc_name: 'Naranja', cat_name: 'Transporte' },
      { id: 103, type: 'ingreso', amount: 480000, currency: 'ARS', description: 'Sueldo', occurred_at: '2026-06-20', account_id: 5, acc_name: 'Banco Galicia', cat_name: 'Sueldo' },
      { id: 104, type: 'gasto', amount: 12000, currency: 'ARS', description: 'Farmacia', occurred_at: '2026-06-19', account_id: 4, acc_name: 'Mercado Pago', cat_name: 'Salud' },
      { id: 105, type: 'gasto', amount: 130, currency: 'USD', description: 'Spotify + Netflix', occurred_at: '2026-06-18', account_id: 1, acc_name: 'Visa Galicia', cat_name: 'Suscripciones' },
    ],
    total: 5,
  },
  'GET /api/overview': {
    accounts: [
      { id: 4, name: 'Mercado Pago', type: 'billetera', active: 1, balances: [{ currency: 'ARS', balance: 184300 }] },
      { id: 5, name: 'Banco Galicia', type: 'banco', active: 1, balances: [{ currency: 'ARS', balance: 760000 }, { currency: 'USD', balance: 1200 }] },
      { id: 6, name: 'Takenos', type: 'inversion', active: 1, balances: [{ currency: 'USD', balance: 866 }] },
      { id: 1, name: 'Visa Galicia', type: 'credito', active: 1, balances: [{ currency: 'ARS', balance: -207000 }] },
    ],
  },
  'GET /api/accounts': [
    { id: 4, name: 'Mercado Pago', type: 'billetera', active: 1 },
    { id: 5, name: 'Banco Galicia', type: 'banco', active: 1 },
    { id: 1, name: 'Visa Galicia', type: 'credito', active: 1, closing_day: 25, due_day: 5 },
    { id: 2, name: 'Naranja', type: 'credito', active: 1, closing_day: 3, due_day: 13 },
  ],
  'GET /api/categories': [
    { id: 1, name: 'Comida' }, { id: 2, name: 'Transporte' }, { id: 3, name: 'Servicios' },
    { id: 4, name: 'Ocio' }, { id: 5, name: 'Salud' }, { id: 6, name: 'Suscripciones' },
  ],
  'GET /api/recurring': [
    { id: 9, description: 'Heladera Whirlpool', amount: 66000, currency: 'ARS', account_id: 1, next_occurrence: fmt(now + 13 * day), active: 1, total_installments: 12, installments_fired: 4 },
    { id: 10, description: 'Notebook', amount: 80000, currency: 'ARS', account_id: 1, next_occurrence: fmt(now + 13 * day), active: 1, total_installments: 6, installments_fired: 1 },
    { id: 11, description: 'Zapatillas', amount: 21300, currency: 'ARS', account_id: 2, next_occurrence: fmt(now + 19 * day), active: 1, total_installments: 3, installments_fired: 1 },
  ],
  'GET /api/cotizacion': { blue: { compra: 1180, venta: 1220 }, oficial: { compra: 980, venta: 1020 }, mep: { compra: 1150, venta: 1170 } },
  'GET /api/tareas': [
    { id: 201, text: 'Pagar el alquiler', priority: 'alta', due_at: fmt(now), status: 'pendiente', completed_at: null, shared: 1, user_id: 1, created_at: fmt(now - day) },
    { id: 202, text: 'Comprar regalo de cumple', priority: 'media', due_at: fmt(now + 4 * day), status: 'pendiente', completed_at: null, shared: 0, user_id: 1, created_at: fmt(now - 2 * day) },
    { id: 203, text: 'Renovar la SUBE', priority: 'baja', due_at: null, status: 'pendiente', completed_at: null, shared: 1, user_id: 1, created_at: fmt(now - 3 * day) },
    { id: 204, text: 'Sacar turno médico', priority: 'media', due_at: null, status: 'hecha', completed_at: fmt(now - day), shared: 0, user_id: 1, created_at: fmt(now - 5 * day) },
  ],
  // tags stored as a JSON string by the backend (json.dumps), mirror that here
  'GET /api/notas': [
    { id: 301, text: 'Wifi vecino: ClaroAR_8821 / clave 5tg9hh2k', tags: '["claves"]', shared: 1, user_id: 1, created_at: fmt(now - day) },
    { id: 302, text: 'Idea: planear viaje a Bariloche en septiembre', tags: '["viajes","ideas"]', shared: 1, user_id: 1, created_at: fmt(now - 6 * day) },
    { id: 303, text: 'Talle de zapatillas de Lisa: 38', tags: null, shared: 0, user_id: 1, created_at: fmt(now - 10 * day) },
  ],
  'GET /api/eventos': [
    { id: 401, title: 'Cena con los viejos', starts_at: fmt(now) + 'T21:00', location: 'Casa de mamá', notes: '', user_id: 1 },
    { id: 402, title: 'Turno dentista', starts_at: fmt(now + day) + 'T15:30', location: 'Av. Santa Fe 1200', notes: 'Llevar credencial', user_id: 1 },
    { id: 403, title: 'Aniversario 🎉', starts_at: fmt(now + 5 * day) + 'T20:00', location: '', notes: '', user_id: 1 },
  ],
  'GET /api/recordatorios': [
    { id: 501, text: 'Llamar al plomero', remind_at: fmt(now) + ' 10:30', fired: 0, source: 'web', user_id: 1 },
    { id: 502, text: 'Sacar la basura', remind_at: fmt(now + day) + ' 08:00', fired: 0, source: 'bot', user_id: 1 },
  ],
  'GET /api/habitos': {
    days: 7,
    items: [
      { id: 601, name: 'Gimnasio', value: 1, unit: 'vez', note: '', logged_at: fmt(now), user_id: 1 },
      { id: 602, name: 'Agua', value: 2, unit: 'litros', note: '', logged_at: fmt(now), user_id: 1 },
      { id: 603, name: 'Gimnasio', value: 1, unit: 'vez', note: '', logged_at: fmt(now - 2 * day), user_id: 1 },
      { id: 604, name: 'Leer', value: 20, unit: 'min', note: '', logged_at: fmt(now - day), user_id: 1 },
    ],
    resumen: [
      { name: 'Gimnasio', cnt: 2, total: 2, unit: 'vez' },
      { name: 'Agua', cnt: 1, total: 2, unit: 'litros' },
      { name: 'Leer', cnt: 1, total: 20, unit: 'min' },
    ],
  },
  'GET /api/listas': {
    lists: [
      {
        id: 701, name: 'Supermercado', icon: '🛒', kind: 'compras', target_date: null, recurrence: null, pend: 3, total: 4,
        items: [
          { id: 7011, text: 'Leche', done: 0, qty: 2, unit: 'L', category: 'Lácteos' },
          { id: 7012, text: 'Pan', done: 0, qty: 1, unit: '', category: 'Panadería' },
          { id: 7013, text: 'Huevos', done: 0, qty: 12, unit: '', category: '' },
          { id: 7014, text: 'Café', done: 1, qty: 1, unit: '', category: '' },
        ],
      },
      {
        id: 702, name: 'Farmacia', icon: '💊', kind: 'compras', target_date: null, recurrence: null, pend: 1, total: 1,
        items: [{ id: 7021, text: 'Ibuprofeno', done: 0, qty: 1, unit: '', category: '' }],
      },
    ],
  },
  'GET /api/listas/templates': {
    templates: [
      { id: 801, name: 'Súper básico', icon: '🛒', kind: 'compras' },
      { id: 802, name: 'Asado', icon: '🥩', kind: 'compras' },
    ],
  },
}

const server = http.createServer((req, res) => {
  const url = req.url.split('?')[0]
  const key = `${req.method} ${url}`
  res.setHeader('Content-Type', 'application/json')
  if (req.method === 'POST' && url === '/login') { res.setHeader('Set-Cookie', 'session=mock; Path=/'); res.end(JSON.stringify({ ok: true, name: 'Emir' })); return }
  if (req.method === 'POST' && url === '/api/set_scope') { res.end(JSON.stringify({ ok: true })); return }
  // Respect ?past= / ?include_fired= so future/past sets are disjoint (mirrors prod)
  if (req.method === 'GET' && url === '/api/eventos') {
    const past = /[?&]past=true/.test(req.url)
    const items = routes['GET /api/eventos'].filter((e) => (new Date(e.starts_at) < new Date()) === past)
    res.end(JSON.stringify(items)); return
  }
  if (req.method === 'GET' && url === '/api/recordatorios') {
    const incFired = /[?&]include_fired=true/.test(req.url)
    const items = routes['GET /api/recordatorios'].filter((r) => incFired || !r.fired)
    res.end(JSON.stringify(items)); return
  }
  if (key in routes) { res.end(JSON.stringify(routes[key])); return }
  if (req.method === 'GET' && url.startsWith('/api/')) { res.end('[]'); return }
  // Generic mutations for any /api/* (create/update/delete/toggle/snooze/done/etc.)
  if (['POST', 'PATCH', 'PUT', 'DELETE'].includes(req.method) && url.startsWith('/api/')) {
    res.end(JSON.stringify({ ok: true, id: 999, done: 1 })); return
  }
  res.statusCode = 404; res.end('{}')
})
server.listen(8000, () => console.log('mock api on :8000'))
