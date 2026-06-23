# Deploy — Juntu dashboard React (frontend en `/app`)

Deploy **no destructivo**: agrega el SPA React en `https://asistente.emir-maestu.site/app`.
No toca el bot de Telegram ni el dashboard viejo (que sigue en `/`). Si algo sale mal,
el rollback es quitar un bloque de Caddy.

> El frontend habla con tu API existente (`/api`, `/login`) en el mismo dominio, así que
> reusa tu login/cookie actuales. Dos features nuevas (cuotas ya pagadas, cierre/vencimiento
> al **crear** tarjeta) mandan campos que el backend todavía ignora → quedan para la tanda
> de backend. Todo lo demás funciona contra el backend actual.

## 0. Prerequisitos (en tu PC)
- Node 20+ y el repo en `…/asistente`.
- Acceso SSH al VPS: `ssh emir@217.76.48.219`.

## 1. Build de producción (en tu PC)
```bash
cd web-react
npm ci          # si es una PC limpia; si no, salteá
npm run build   # genera web-react/dist/ con base /app/
```

## 2. Subir el build al VPS (desde tu PC, en la raíz del repo)
```bash
ssh emir@217.76.48.219 'mkdir -p ~/asistente/webapp'
scp -r web-react/dist/* emir@217.76.48.219:~/asistente/webapp/
```

## 3. Servir el SPA en `/app` con Caddy (en el VPS)
Editá el Caddyfile (suele estar en `/etc/caddy/Caddyfile`) y, **dentro del bloque del sitio**
`asistente.emir-maestu.site { … }`, agregá este handle (ver `deploy/caddy-app.snippet`):

```caddy
    handle_path /app/* {
        root * /home/emir/asistente/webapp
        try_files {path} /index.html
        file_server
    }
```

Importante:
- Tiene que quedar **junto a** los otros `handle`/`reverse_proxy` del sitio (las rutas `/api`,
  `/login`, `/logout` deben seguir yendo al uvicorn como hasta ahora).
- Si tu config usa directivas sueltas (sin `handle`), igual suele funcionar; si Caddy tira
  error al recargar, copiame tu Caddyfile y lo ajusto.

Recargá Caddy:
```bash
sudo systemctl reload caddy    # o: caddy reload --config /etc/caddy/Caddyfile
```

## 4. Verificar
- Abrí `https://asistente.emir-maestu.site/app/` → debería cargar Juntu.
- Logueate con tu usuario/clave reales.
- Revisá Inicio (gasto del mes), Movimientos, Tarjetas (entrá a una tarjeta), Cuentas.
- Si algún número se ve raro, es un shape de la API distinto al asumido → anotalo y lo ajusto.

## 5. Rollback (si hace falta)
Quitá el bloque `handle_path /app/* { … }` del Caddyfile y `sudo systemctl reload caddy`.
El sitio vuelve exactamente a como estaba (el `/app` deja de existir).

## 6. Flip a `/` (más adelante, cuando el core esté validado)
1. En `web-react/vite.config.ts`: `base: '/app/'` → `base: '/'`; en `src/main.tsx`:
   `basename="/app"` → `basename="/"` y el handler 401 `/app/login` → `/login`. Rebuild.
2. En Caddy: servir el SPA en `/` y mover el dashboard viejo a `handle_path /legacy/* { … }`.
3. Actualizar el link de "Otras secciones" del menú si cambió.

## Pendiente — tanda de backend (para que funcionen 2 features nuevas)
- `POST/PATCH /api/recurring`: aceptar `installments_fired` (cuotas ya pagadas).
- `POST /api/accounts`: aceptar `closing_day`/`due_day` (cierre/vencimiento al crear tarjeta;
  hoy solo se setean editando después).
Se aplican en `~/asistente/` (los .py) y se reinician los servicios:
`sudo systemctl restart asistente asistente-web`.
