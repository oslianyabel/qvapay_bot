# Despliegue en VPS + Cloudflare Tunnel

Guía para desplegar **QvaPay P2P Monitor** en un VPS Linux (Ubuntu/Debian) y exponerlo
por HTTPS con un **túnel de Cloudflare** — sin abrir puertos entrantes.

Esta guía asume el escenario real de despliegue:

- El repositorio ya está en **`/srv/qvapay_bot`**.
- Ejecutas los comandos como **`root`**.

Arquitectura en producción:

```
Internet → Cloudflare (HTTPS) → cloudflared (túnel saliente) → 127.0.0.1:8000 (FastAPI + SPA)
```

El backend FastAPI sirve el SPA ya compilado y la API en el **mismo origen y un solo
proceso**. El puerto 8000 escucha **solo en localhost**; cloudflared abre una conexión
*saliente* hacia Cloudflare, así que **no hay que abrir puertos en el firewall**.

> ⚠️ **Un solo worker.** Los monitores corren como tareas asyncio dentro del proceso. Si
> lanzas varios workers/procesos, cada uno reanudaría los monitores y **aplicarías ofertas
> por duplicado**. Ejecuta siempre una sola instancia (como hace `web_main.py`).

---

## 0. Requisitos

- VPS con Ubuntu 22.04/24.04 (o Debian), acceso como root, repo en `/srv/qvapay_bot`.
- Un dominio gestionado en **Cloudflare** (para el túnel con nombre). Si no tienes dominio,
  al final hay una alternativa de *quick tunnel* para pruebas.
- Credenciales de QvaPay (el login de la web es el login de QvaPay).

> Si en este VPS corría el antiguo bot de Telegram como servicio, deténlo y deshabilítalo
> antes de continuar para que no compita por el estado:
> `systemctl disable --now <nombre-del-servicio-viejo>` (si existe).

---

## 1. Instalar dependencias del sistema

Paquetes base y Node.js 20 LTS (para compilar el frontend):

```bash
apt update && apt install -y git curl
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
```

Instala **uv** (gestiona Python 3.13 automáticamente). Queda en `/root/.local/bin/uv`:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
/root/.local/bin/uv --version
```

---

## 2. Construir la app

Ya tienes el código en `/srv/qvapay_bot`. Instala dependencias de Python (uv descargará
Python 3.13 si hace falta):

```bash
cd /srv/qvapay_bot
/root/.local/bin/uv sync
```

Compila el frontend (genera `frontend/dist`, que el backend sirve en producción):

```bash
cd /srv/qvapay_bot/frontend
npm ci && npm run build
```

> Si `npm ci` falla por falta de `package-lock.json`, usa `npm install`.

---

## 3. Configurar el entorno (`.env`)

Añade la configuración web al `.env` en la raíz del repo (`/srv/qvapay_bot/.env`). Si ya
tienes un `.env` de la versión anterior, estas variables se suman; las de Telegram ya no se
usan y pueden quedarse o borrarse.

Genera el secreto de sesión y anexa las variables:

```bash
cd /srv/qvapay_bot
JWT=$(openssl rand -hex 32)
cat >> .env <<EOF

# --- Web app ---
JWT_SECRET=$JWT
WEB_HOST=127.0.0.1
WEB_PORT=8000
COOKIE_SECURE=true
EOF
chmod 600 .env
```

- `COOKIE_SECURE=true` porque Cloudflare sirve por HTTPS (la cookie de sesión solo viaja
  cifrada; sin esto no podrás iniciar sesión).
- `WEB_HOST=127.0.0.1` deja el puerto accesible solo localmente (lo consume cloudflared).
- No hace falta `CORS_ORIGINS`: el SPA se sirve desde el mismo origen que la API.

Protege el directorio de estado (guarda los bearer de QvaPay en texto plano):

```bash
mkdir -p /srv/qvapay_bot/data && chmod 700 /srv/qvapay_bot/data
```

---

## 4. Servicio systemd de la app

Crea `/etc/systemd/system/qvapay.service`:

```ini
[Unit]
Description=QvaPay P2P Monitor (FastAPI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/srv/qvapay_bot
ExecStart=/root/.local/bin/uv run python web_main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Actívalo:

```bash
systemctl daemon-reload
systemctl enable --now qvapay
systemctl status qvapay --no-pager
```

Comprueba que responde en local:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/    # -> 200
curl -s http://127.0.0.1:8000/api/auth/me                          # -> {"detail":"Not authenticated"}
```

Logs de la app:

```bash
journalctl -u qvapay -f
```

---

## 5. Instalar cloudflared

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
dpkg -i /tmp/cloudflared.deb
cloudflared --version
```

Autentícate (abre la URL que imprime en un navegador donde tengas sesión de Cloudflare y
elige tu dominio). Guarda `~/.cloudflared/cert.pem` (es decir, `/root/.cloudflared/cert.pem`):

```bash
cloudflared tunnel login
```

---

## 6. Crear el túnel y la ruta DNS

```bash
cloudflared tunnel create qvapay
```

Anota el **UUID** del túnel y la ruta del archivo de credenciales que imprime
(`/root/.cloudflared/<UUID>.json`).

Apunta un subdominio al túnel (crea el registro DNS en Cloudflare automáticamente):

```bash
cloudflared tunnel route dns qvapay app.tudominio.com
```

---

## 7. Configuración e instalación como servicio

Crea `/etc/cloudflared/config.yml` (sustituye `<UUID>` y el hostname):

```yaml
tunnel: qvapay
credentials-file: /root/.cloudflared/<UUID>.json

ingress:
  - hostname: app.tudominio.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

Instala y arranca cloudflared como servicio del sistema:

```bash
cloudflared service install
systemctl enable --now cloudflared
systemctl status cloudflared --no-pager
```

---

## 8. Verificación

Desde cualquier lugar:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://app.tudominio.com/
```

Abre `https://app.tudominio.com` en el navegador → deberías ver la pantalla de login.
Inicia sesión con tus credenciales de QvaPay, crea monitores en **Reglas** y arráncalos en
el **Dashboard** (los eventos en vivo llegan por SSE a través del túnel).

---

## 9. Actualizar a una nueva versión

```bash
cd /srv/qvapay_bot
git pull
/root/.local/bin/uv sync
cd frontend && npm ci && npm run build && cd ..
systemctl restart qvapay
```

(cloudflared no necesita reinicio salvo que cambies `config.yml`.)

---

## 10. Operación y seguridad

- **Backups:** respalda `/srv/qvapay_bot/data/` (estado de auth y de monitores). Es todo
  JSON; cópialo antes de actualizar.
- **Secretos:** `.env` y `data/bot_state.json` (bearer de QvaPay en claro) quedan en
  `chmod 600/700`. No los subas a git.
- **Firewall:** con el túnel no necesitas exponer el 8000. Puedes cerrar todo el entrante
  salvo SSH (`ufw allow OpenSSH && ufw enable`).
- **Un solo proceso:** no añadas `--workers` ni levantes varias instancias (duplicaría los
  monitores y las aplicaciones de ofertas).
- **Reinicios:** systemd reinicia la app si cae; al arrancar, reanuda los monitores que
  estaban activos (`restore_tasks`).
- **(Opcional) Endurecer:** ejecutar como root es lo más directo, pero para producción es
  más seguro crear un usuario dedicado (`adduser --system --group qvapay`), dar permisos de
  `/srv/qvapay_bot` a ese usuario y poner `User=qvapay` en el servicio.

---

## Alternativa rápida (sin dominio, solo pruebas)

Si solo quieres una URL temporal para probar, sin dominio ni configuración:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Imprime una URL `https://<algo>.trycloudflare.com` que apunta a tu app mientras el comando
siga corriendo. No es persistente ni apta para producción, pero sirve para una demo.
