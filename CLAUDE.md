# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**QvaPay P2P Monitor (Web App)** — A multi-user web application that automates monitoring
and applying QvaPay P2P offers, with live tracking. It replaced the previous Telegram bot.

- **Backend:** FastAPI (`qvapay_web/`) over a framework-agnostic domain core (`qvapay_bot/`).
- **Frontend:** React + Vite + TypeScript (`frontend/`).
- **Real-time:** per-cycle events via Server-Sent Events (`/api/events`).
- **Auth:** the web login IS the QvaPay login (email/password, optional 2FA). The backend
  fetches the bearer token and issues its own session (JWT in an httpOnly cookie). The app
  `user_id` = QvaPay `uuid`; passwords are never stored.
- Requires Python 3.13+ and Node.js 18+.
- Per-user auth/bearer state and P2P monitoring rules stored in JSON files (no database).

## Development Commands

### Setup
```bash
uv sync                          # Install Python dependencies
cd frontend && npm install       # Install frontend dependencies
```

### Run (development)
```bash
uv run uvicorn qvapay_web.app:app --reload   # Backend on :8000
cd frontend && npm run dev                   # Frontend (Vite) on :5173, proxies /api
```

### Run (production, single process)
```bash
cd frontend && npm run build && cd ..        # Build SPA into frontend/dist
uv run python web_main.py                    # FastAPI serves the SPA + API
```

### Tests
```bash
uv run pytest                                     # Run all tests (requires JWT_SECRET env)
uv run pytest tests/test_monitor_manager.py       # Run specific test file
uv run pytest -v                                  # Verbose output
```

### Linting & Code Quality
```bash
uv run ruff check qvapay_bot qvapay_web tests    # Check code style
uv run ruff format qvapay_bot qvapay_web tests   # Format code
```

## Architecture

### Core Structure

```
qvapay_bot/                  # DOMAIN CORE (framework-agnostic; reused by the web layer)
├── __init__.py              # Package marker
├── config.py                # Settings (env vars): QvaPay + JWT/CORS/web host+port
├── http_client.py           # AsyncHttpClient for HTTP requests
├── qvapay_client.py         # QvaPayClient + COMMAND_SPECS (API mapping)
├── state.py                 # BotStateStore + ChatAuthState (per-user bearer, keyed by uuid)
├── p2p_models.py            # Data models (offers, rules, evaluations, cycle report)
├── p2p_filters.py           # Offer filtering & evaluation logic
├── serialization.py         # Dataclasses -> JSON dicts (events + API responses)
├── notifier.py              # MonitorEvent + MonitorNotifier protocol
├── events.py                # EventBus (in-memory pub/sub) + WebNotifier (feeds SSE)
├── p2p_monitor.py           # P2PMonitorManager: asyncio task per user + emits events
└── p2p_repository.py        # P2PMonitorStateStore (P2P state persistence)

qvapay_web/                  # FASTAPI LAYER
├── app.py                   # FastAPI app + lifespan (restore_tasks) + StaticFiles (SPA)
├── deps.py                  # DI providers + current_user (JWT cookie -> user)
├── security.py              # JWT issue/verify (session cookie)
├── schemas.py               # Pydantic request models
└── routers/
    ├── auth.py              # POST /api/auth/login|logout, GET /api/auth/me
    ├── monitor.py           # GET /api/monitor, PUT rules, start/stop, test (dry-run)
    ├── history.py           # GET /api/history, /api/balance, /api/offers
    └── events.py            # GET /api/events (SSE stream per user)

frontend/                    # REACT SPA (Vite + TS): Login, Dashboard, Rules, History
web_main.py                  # Entry point: uvicorn qvapay_web.app:app
```

### Key Modules & Their Roles

#### `qvapay_client.py`
- **COMMAND_SPECS**: Tuple of `CommandSpec` objects mapping each logical operation to a QvaPay API endpoint
- **COMMAND_INDEX**: Dict for fast lookup by command name
- **QvaPayClient**: Wraps AsyncHttpClient; encapsulates API calls with auth/error handling
- Handles auth modes (NONE, BEARER, EITHER) and payload building

#### `state.py`
- **ChatAuthState**: Dataclass holding per-chat auth state (bearer token, app credentials, user info, pending command)
- **BotStateStore**: Loads/saves `data/bot_state.json`; keyed by chat_id
- Tracks logged-in users, KYC status, and P2P eligibility per chat

#### `p2p_monitor.py` (Most Complex)
- **P2PMonitorManager**: Main orchestrator for P2P monitoring
  - Runs one asyncio task per enabled user (`_monitor_loop`), no external scheduler
  - Evaluates offers against rules, applies the best eligible one
  - Tracks recently-applied offers, prevents duplicate applications
  - Emits `MonitorEvent`s through the injected `MonitorNotifier` (no framework coupling)
  - Persists state across restarts; `restore_tasks()` resumes enabled users on startup

#### `qvapay_web/app.py` (`create_app` + `lifespan`)
- Lifespan builds HTTP client, QvaPayClient, stores, EventBus, WebNotifier, and manager;
  stores them on `app.state`; calls `manager.restore_tasks()`; cancels tasks on shutdown
- Mounts routers under `/api` and serves the built SPA from `frontend/dist` (SPA fallback)

#### `qvapay_web/deps.py`
- DI providers read singletons from `request.app.state`
- `current_user`: decodes the JWT session cookie → `(user_id, ChatAuthState)`; 401 if the
  cookie is missing/invalid or the user has no bearer token

#### `p2p_filters.py`
- Evaluates offers against user rules (coin, ratio, amount, KYC/VIP requirements)
- Sorts eligible offers by ratio (best first)
- Builds offer snapshots and history entries

#### `p2p_repository.py`
- **P2PMonitorStateStore**: Loads/saves `data/p2p_monitor_state.json`
- Stores per-user: enabled status, rules, polling interval, applied offer history

### Data Flow: P2P Monitoring

1. User logs in (QvaPay credentials) → session cookie issued; `user_id` = QvaPay uuid
2. User edits rules via `PUT /api/monitor/rules` (saved to the P2P repository)
3. User starts monitoring via `POST /api/monitor/start` → `manager.restart_user(user_id)`
   schedules the asyncio loop
4. Each cycle (every N seconds):
   - Fetch current P2P offers from the API
   - Evaluate each offer against rules (`p2p_filters.py`)
   - Select the best eligible offer:
     - Check cooldown (don't re-apply within 1 hour)
     - Lock to prevent race conditions
     - Try to apply; track result (matched, applied, lost_race, rejected, etc.)
   - Emit events (`cycle_started`, `offer_selected`, `apply_result`, `cycle_completed`,
     `error`, `balance_low`, `monitor_stopped`) → SSE → dashboard
5. On restart: `lifespan` calls `restore_tasks()` to resume enabled users
6. User stops via `POST /api/monitor/stop` → `manager.stop_user(user_id)` cancels the task

### State Persistence

- **Auth State** (`data/bot_state.json`):
  - Per-user bearer token and QvaPay metadata (uuid, username, kyc, p2p_enabled)
  - Keyed by QvaPay uuid; survives restarts (used to restore monitor tasks)

- **P2P Monitor State** (`data/p2p_monitor_state.json`):
  - Per-user: enabled/disabled status, rules, polling interval, target type
  - Offer histories (applied, lost_race, filtered, discarded, notified; last 25 each)
  - Separate file keeps monitoring concerns isolated from auth

## Important Patterns

### Async Context
- All route handlers and monitor code are async; use `await` for API calls and state saves
- No blocking I/O (the HTTP client offloads urllib calls to threads)

### Shared State (DI)
- Singletons live on `app.state` and are accessed via `qvapay_web/deps.py` providers:
  `settings`, `qvapay_client`, `state_store`, `repository`, `event_bus`, `manager`
- Tests override these via `app.dependency_overrides` (see `tests/test_web_api.py`)

### Events & SSE
- The manager emits `MonitorEvent`s via `MonitorNotifier`; `WebNotifier` publishes them to
  the per-user `EventBus`; `GET /api/events` streams them as SSE (with ~15s heartbeats)
- `qvapay_bot/serialization.py` converts domain dataclasses to JSON for events and the API

### Error Handling
- Route handlers raise `HTTPException`; the monitor loop catches exceptions, records
  `last_error`, and emits an `error` event (rate-limited via a per-message cooldown)

### Filtering & Validation
- Offer evaluation (p2p_filters.py) returns `OfferEvaluation` with reasons for rejection
- Monitor rules validated before saving (min < max, positive amounts, etc.)
- API payloads built via `QvaPayClient` (handles auth modes, field types)

## Environment Variables

Required:
- `JWT_SECRET`: Secret for signing session cookies (use ≥ 32 bytes)

Optional (with defaults):
- `QVAPAY_BASE_URL`: Defaults to `https://api.qvapay.com`
- `BOT_STATE_FILE`: Defaults to `data/bot_state.json` (per-user bearer, keyed by QvaPay uuid)
- `BOT_P2P_STATE_FILE`: Defaults to `data/p2p_monitor_state.json`
- `HTTP_TIMEOUT_SECONDS`: Defaults to `30`
- `JWT_EXPIRE_MINUTES`: Defaults to `10080` (7 days)
- `CORS_ORIGINS`: Defaults to the Vite dev server origins (`http://localhost:5173,...`)
- `WEB_HOST` / `WEB_PORT`: Defaults to `127.0.0.1` / `8000`
- `COOKIE_SECURE`: Defaults to `false`; set `true` behind HTTPS
- `WEB_RELOAD`: Defaults to `false`; enables auto-reload for `python web_main.py`

## Testing

- **conftest.py**: Sets up test path (PROJECT_ROOT)
- **Tests cover**:
  - Offer filtering logic (`test_p2p_filters.py`)
  - P2P state repository (`test_p2p_repository.py`)
  - Monitor manager end-to-end with a fake notifier + fake QvaPay client (`test_monitor_manager.py`)
  - Web API auth + monitor flow via `fastapi.testclient.TestClient` (`test_web_api.py`)
- Requires `JWT_SECRET` in the environment (`JWT_SECRET=test uv run pytest`)
- Async tests run via `asyncio.run(...)`; no `pytest-asyncio` dependency
- Add new tests to `tests/`; pytest auto-discovers `test_*.py` files

## Notes for Future Work

- State files are JSON; backups recommended before major refactors
- P2P monitoring uses asyncio locks to prevent race conditions on apply
- No database; all state in-memory + JSON files (simple, portable, suitable for development)
- Frontend is a standalone Vite app in `frontend/`; the backend serves its `dist/` build in
  production and proxies during development
