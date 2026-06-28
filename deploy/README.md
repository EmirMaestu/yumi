# Deploy runbook (Yumi)

Flujo: PR → checks (CI) → merge a `main` → (staging, fase futura) → **release** → producción.
El repo es el único source of truth; el VPS se actualiza desde git con `deploy.sh`.

## Publicar a producción
1. Mergeá tus PRs a `main` (CI en verde).
2. En el último PR antes de releasear, en `CHANGELOG.md` mové lo de `## [Unreleased]` a
   `## [X.Y.Z] - YYYY-MM-DD`.
3. GitHub → Actions → **release** → Run → escribí `X.Y.Z`.
   Eso crea el tag `vX.Y.Z`, la GitHub Release (notas = esa sección del CHANGELOG) y dispara
   `deploy-prod`, que en el VPS corre `deploy.sh <tag> prod`: backup DB → checkout del tag →
   rsync de código → pip → frontend → restart → **health-check**; si falla, **rollback** y aviso
   a tu Telegram.

## Rollback manual
```bash
ssh emir@217.76.48.219 'cd ~/yumi && bash deploy/deploy.sh <tag_anterior> prod'
```

## Versionado (SemVer)
- MINOR (`0.X.0`) por cada tanda de features. PATCH (`0.0.X`) por fixes.
- La versión la elegís vos al correr el workflow `release`.

## Logs
- Deploy: GitHub → Actions → `deploy-prod`.
- App: `journalctl -u asistente -n 80` / `journalctl -u asistente-web -n 80`.
- Monitoreo: timer `yumi-health.timer` corre `deploy/check.sh` cada 5 min y avisa al owner
  ante caída/recuperación (dedup por estado en `~/asistente/.health_state`).

## Qué PRESERVA el deploy (no lo toca el rsync)
`.env`, `data.db*`, `venv/`, `backups/`, `voice/`, `photos/`, `vapid_private.pem`,
`credenciales*` (ver `deploy/rsync-excludes.txt`). Todo lo demás en el run-dir se hace espejo
del repo (`vps_current/`), así que el junk (`apply_*.py`, `*.bak*`) se limpia solo.

## Secrets de GitHub (Settings → Secrets → Actions)
- `VPS_SSH_KEY` — clave privada SSH dedicada de deploy.
- `VPS_HOST` — `217.76.48.219`.
- `VPS_USER` — `emir`.

## Primer setup en el VPS (una vez)
- `git clone https://github.com/EmirMaestu/yumi.git ~/yumi`
- Instalar `deploy/yumi-deploy.sudoers` en `/etc/sudoers.d/yumi-deploy` (restart sin password).
- `chown -R emir:emir /var/www/juntu /var/www/yumi-landing` (deploy del frontend sin sudo).
- Agregar `OWNER_CHAT_ID=<tu_chat_id>` a `~/asistente/.env`.
- Instalar/activar `yumi-health.timer`.
