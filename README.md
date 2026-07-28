## QvaPay P2P Monitor (Web App)

Aplicación web multi-usuario que automatiza el monitoreo y la aplicación de ofertas P2P
de QvaPay, con seguimiento en vivo. Sustituye al antiguo bot de Telegram.

- **Backend:** FastAPI (Python 3.13+) reutilizando el núcleo de dominio (`qvapay_bot/`).
- **Frontend:** React + Vite + TypeScript (`frontend/`).
- **Tiempo real:** eventos por ciclo vía Server-Sent Events (`/api/events`).
- **Login:** el inicio de sesión de la web **es** el login de QvaPay (email/contraseña,
  2FA opcional). El backend obtiene el bearer y emite una sesión propia (JWT en cookie
  httpOnly). El `user_id` de la app = `uuid` de QvaPay; no se almacenan contraseñas.

### Arquitectura

```
qvapay_bot/      # Núcleo: cliente QvaPay, modelos, filtros/evaluación, monitor, persistencia JSON
  p2p_monitor.py # Orquestador: tareas asyncio por usuario + notificaciones vía MonitorNotifier
  notifier.py    # MonitorEvent + protocolo MonitorNotifier
  events.py      # EventBus en memoria + WebNotifier (alimenta el SSE)
  serialization.py  # dataclasses -> dicts JSON
qvapay_web/      # Capa FastAPI: security (JWT), deps (DI + auth), routers, app (lifespan)
frontend/        # SPA React (Login, Dashboard, Reglas, Historial)
web_main.py      # Entry point
```

### Requisitos

- Python 3.13+ y [uv](https://docs.astral.sh/uv/).
- Node.js 18+ (para el frontend).

### Variables de entorno

Obligatoria:

- `JWT_SECRET`: clave para firmar las sesiones (usa ≥ 32 bytes).

Opcionales (con valores por defecto):

- `QVAPAY_BASE_URL` (`https://api.qvapay.com`)
- `BOT_STATE_FILE` (`data/bot_state.json`) — credenciales/bearer por usuario.
- `BOT_P2P_STATE_FILE` (`data/p2p_monitor_state.json`) — reglas, historial y estado del monitor.
- `HTTP_TIMEOUT_SECONDS` (`30`)
- `JWT_EXPIRE_MINUTES` (`10080` = 7 días)
- `CORS_ORIGINS` (`http://localhost:5173,http://127.0.0.1:5173`)
- `WEB_HOST` (`127.0.0.1`), `WEB_PORT` (`8000`)
- `COOKIE_SECURE` (`false`) — ponlo en `true` detrás de HTTPS.
- `WEB_RELOAD` (`false`) — recarga automática al usar `python web_main.py`.

Ejemplo mínimo de `.env`:

```
JWT_SECRET=cambia-esto-por-una-clave-larga-y-aleatoria
```

### Desarrollo

Backend (terminal 1):

```bash
uv sync
uv run uvicorn qvapay_web.app:app --reload
```

Frontend (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Abre el dev server de Vite (por defecto `http://localhost:5173`); las llamadas a `/api`
se redirigen al backend en `:8000`.

### Producción (un solo proceso)

Compila el frontend y arranca el backend, que sirve el SPA desde `frontend/dist`:

```bash
cd frontend && npm run build && cd ..
uv run python web_main.py
```

### Flujo de uso

1. Inicia sesión con tus credenciales de QvaPay.
2. Configura las reglas del monitor (tipo de oferta, moneda, ratios, montos, KYC/VIP,
   intervalo) en **Reglas**.
3. Enciende el monitor en el **Dashboard**. Cada ciclo lee las ofertas P2P, evalúa
   contra tus reglas, aplica la mejor oferta elegible y emite eventos en vivo.
4. Revisa las ofertas aplicadas y descartadas en **Historial**.

### Tests y linting

```bash
uv run pytest
uv run ruff check qvapay_bot qvapay_web tests
```

### Notas

- El estado se guarda en archivos JSON (sin base de datos). El `bot_state.json` anterior
  estaba indexado por `chat_id` de Telegram; con el nuevo esquema (clave = `uuid` de
  QvaPay) esos registros se ignoran y se repueblan al primer login. Respalda `data/`
  antes de migrar.
- Los bearer tokens de QvaPay se guardan server-side en `bot_state.json` en texto plano
  (igual que antes). Protege ese archivo y define `JWT_SECRET`.
- El monitor corre como tareas asyncio dentro del proceso FastAPI; al reiniciar, el
  `lifespan` reanuda los monitores de los usuarios con estado `enabled`.
