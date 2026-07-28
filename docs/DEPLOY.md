# Despliegue en VPS + Cloudflare Tunnel

Guía para desplegar **QvaPay P2P Monitor** en un VPS Linux (Ubuntu/Debian) y exponerlo
por HTTPS con un **túnel de Cloudflare** — sin abrir puertos entrantes.

Arquitectura en producción:

```
Internet → Cloudflare (HTTPS) → cloudflared (túnel saliente) → 127.0.0.1:8000 (FastAPI + SPA)
```

El backend FastAPI sirve el SPA ya compilado y la API en el **mismo origen y un solo
proceso**. El puerto 8000 queda escuchando **solo en localhost**; cloudflared abre una
conexión *saliente* hacia Cloudflare, así que **no hay que abrir puertos en el firewall**.

> ⚠️ **Un solo worker.** Los monitores corren como tareas asyncio dentro del proceso. Si
> lanzas varios workers/procesos, cada uno reanudaría los monitores y **aplicarías ofertas
> por duplicado**. Ejecuta siempre una sola instancia (como hace `web_main.py`).

---

## 0. Requisitos

- Un VPS con Ubuntu 22.04/24.04 (o Debian) y acceso SSH con sudo.
- Un dominio gestionado en **Cloudflare** (para el túnel con nombre). Si no tienes dominio,
  al final hay una alternativa de *quick tunnel* para pruebas.
- Credenciales de QvaPay (el login de la web es el login de QvaPay).

---

## 1. Preparar el VPS

Crea un usuario dedicado (no ejecutes la app como root):

```bash
sudo adduser --system --group --home /opt/qvapay qvapay
```

Instala dependencias base (git, curl) y Node.js 20 LTS (para compilar el frontend):

```bash
sudo apt update && sudo apt install -y git curl
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

Instala **uv** (gestiona Python 3.13 automáticamente) para el usuario `qvapay`:

```bash
sudo -u qvapay bash -lc 'curl -LsSf https://astral.sh/uv/install.sh | sh'
```

`uv` queda en `/opt/qvapay/.local/bin/uv`. Compruébalo:

```bash
sudo -u qvapay /opt/qvapay/.local/bin/uv --version
```

---

## 2. Clonar y construir la app

```bash
sudo -u qvapay git clone <repo-url> /opt/qvapay/app
cd /opt/qvapay/app
```

Instala dependencias de Python (uv descargará Python 3.13 si hace falta):

```bash
sudo -u qvapay /opt/qvapay/.local/bin/uv sync
```

Compila el frontend (genera `frontend/dist`, que el backend sirve en producción):

```bash
sudo -u qvapay bash -lc 'cd /opt/qvapay/app/frontend && npm ci && npm run build'
```

---

## 3. Configurar el entorno (`.env`)

Genera un secreto para las sesiones y crea el `.env` en la raíz del repo:

```bash
JWT=$(openssl rand -hex 32)
sudo -u qvapay tee /opt/qvapay/app/.env >/dev/null <<EOF
JWT_SECRET=$JWT
WEB_HOST=127.0.0.1
WEB_PORT=8000
COOKIE_SECURE=true
EOF
```

- `COOKIE_SECURE=true` porque Cloudflare sirve por HTTPS (la cookie de sesión solo viaja
  cifrada).
- `WEB_HOST=127.0.0.1` deja el puerto accesible solo localmente (lo consume cloudflared).
- No hace falta `CORS_ORIGINS`: el SPA se sirve desde el mismo origen que la API.

Protege el archivo de estado (guarda los bearer de QvaPay en texto plano):

```bash
sudo chmod 600 /opt/qvapay/app/.env
# data/ se crea al arrancar; asegúrate de que solo lo lea el usuario qvapay:
sudo -u qvapay mkdir -p /opt/qvapay/app/data && sudo chmod 700 /opt/qvapay/app/data
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
User=qvapay
Group=qvapay
WorkingDirectory=/opt/qvapay/app
ExecStart=/opt/qvapay/.local/bin/uv run python web_main.py
Restart=on-failure
RestartSec=5
# Endurecimiento básico
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Actívalo:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now qvapay
sudo systemctl status qvapay --no-pager
```

Comprueba que responde en local:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/
curl -s http://127.0.0.1:8000/api/auth/me   # -> {"detail":"Not authenticated"}
```

Logs de la app:

```bash
journalctl -u qvapay -f
```

---

## 5. Instalar cloudflared

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb -o /tmp/cloudflared.deb
sudo dpkg -i /tmp/cloudflared.deb
cloudflared --version
```

Autentícate (abre la URL que imprime en un navegador donde tengas sesión de Cloudflare y
elige tu dominio):

```bash
cloudflared tunnel login
```

Esto guarda un certificado en `~/.cloudflared/cert.pem`.

---

## 6. Crear el túnel y la ruta DNS

```bash
cloudflared tunnel create qvapay
```

Anota el **UUID** del túnel y la ruta del archivo de credenciales que imprime
(`~/.cloudflared/<UUID>.json`).

Apunta un subdominio al túnel (crea el registro DNS en Cloudflare automáticamente):

```bash
cloudflared tunnel route dns qvapay app.tudominio.com
```

---

## 7. Configuración e instalación como servicio

Crea `/etc/cloudflared/config.yml`:

```yaml
tunnel: qvapay
credentials-file: /root/.cloudflared/<UUID>.json

ingress:
  - hostname: app.tudominio.com
    service: http://127.0.0.1:8000
  - service: http_status:404
```

> Copia el `<UUID>.json` a `/root/.cloudflared/` (o ajusta `credentials-file` a donde
> quedó, p. ej. `/home/tu-usuario/.cloudflared/<UUID>.json`).

Instala y arranca cloudflared como servicio del sistema:

```bash
sudo cloudflared service install
sudo systemctl enable --now cloudflared
sudo systemctl status cloudflared --no-pager
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
cd /opt/qvapay/app
sudo -u qvapay git pull
sudo -u qvapay /opt/qvapay/.local/bin/uv sync
sudo -u qvapay bash -lc 'cd frontend && npm ci && npm run build'
sudo systemctl restart qvapay
```

(cloudflared no necesita reinicio salvo que cambies `config.yml`.)

---

## 10. Operación y seguridad

- **Backups:** respalda `/opt/qvapay/app/data/` (estado de auth y de monitores). Es todo
  JSON; cópialo antes de actualizar.
- **Secretos:** `JWT_SECRET` y `data/bot_state.json` (bearer de QvaPay en claro) deben
  quedar solo legibles por el usuario `qvapay`.
- **Firewall:** con el túnel no necesitas exponer el 8000. Puedes cerrar todo el entrante
  salvo SSH (`sudo ufw allow OpenSSH && sudo ufw enable`).
- **Un solo proceso:** no añadas `--workers` ni levantes varias instancias (duplicaría los
  monitores y las aplicaciones de ofertas).
- **Reinicios:** systemd reinicia la app si cae; al arrancar, reanuda los monitores que
  estaban activos (`restore_tasks`).

---

## Alternativa rápida (sin dominio, solo pruebas)

Si solo quieres una URL temporal para probar, sin dominio ni configuración:

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Imprime una URL `https://<algo>.trycloudflare.com` que apunta a tu app mientras el comando
siga corriendo. No es persistente ni apta para producción, pero sirve para una demo.
