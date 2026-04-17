## QvaPay Telegram Bot

Telegram bot that exposes one command for each QvaPay API endpoint documented in [docs](docs).

### Features

- Long polling bot implemented with the Python standard library only.
- One Telegram command per documented QvaPay endpoint.
- Per-chat authentication state for bearer token and app credentials.
- Support for JSON payloads, query parameters, path parameters and P2P chat image upload.

### Requirements

- Python 3.13 or newer.
- A Telegram bot token stored in the `TELEGRAM_BOT_TOKEN` environment variable or in a local `.env` file.

### Environment variables

- `TELEGRAM_BOT_TOKEN`: Telegram bot token.
- `TELEGRAM_DEV_CHAT_ID`: Optional. Telegram chat id that receives developer error notifications.
- `QVAPAY_BASE_URL`: Optional. Defaults to `https://api.qvapay.com`.
- `BOT_STATE_FILE`: Optional. Defaults to `data/bot_state.json`.
- `BOT_P2P_STATE_FILE`: Optional. Defaults to `data/p2p_monitor_state.json`.
- `HTTP_TIMEOUT_SECONDS`: Optional. Defaults to `30`.
- `TELEGRAM_POLL_TIMEOUT_SECONDS`: Optional. Defaults to `25`.

### Run

```bash
python main.py
```

### Authentication utilities

Use these helper commands before protected endpoints:

- `/set_token token=...`
- `/set_app app_id=... app_secret=...`
- `/cancel`
- `/clear_auth`
- `/auth_status`

The `/login` command also stores the returned bearer token automatically for the current chat.

### P2P monitor commands

These commands work in interactive mode and persist their state per chat:

- `/p2p_monitor_on`
- `/p2p_monitor_off`
- `/p2p_monitor_status`
- `/p2p_rules`
- `/p2p_rules_show`
- `/p2p_applied_list`
- `/p2p_applied_detail`
- `/p2p_monitor_test_once`

The monitor uses a separate JSON state file and restores active monitoring after process restarts when the chat still has a bearer token configured.

### Command format

Commands use `key=value` pairs. Values with spaces must be quoted.

If a command requires parameters and you do not send them inline, the bot asks for them one by one in the following messages. Send `/cancel` to abort the current action.

Examples:

```text
/average
/login email="user@example.com" password="secret" remember=true
/check_session
/list_p2p
/mark_p2p_paid uuid=offer-uuid tx_id=REF-123
/transaction_detail uuid=transaction-uuid
```

For P2P chat images, send a photo with this caption:

```text
/send_p2p_chat uuid=offer-uuid message="Payment proof"
```

### Documented endpoint coverage

Implemented commands:

- `/login`
- `/check_session`
- `/logout`
- `/list_p2p`
- `/p2p_detail`
- `/apply_p2p`
- `/cancel_p2p`
- `/mark_p2p_paid`
- `/rate_p2p`
- `/get_p2p_chat`
- `/send_p2p_chat`
- `/average`
- `/list_payment_links`
- `/list_transactions`
- `/transaction_detail`
- `/profile`

### Notes

- The file [docs/crear 2FA.md](docs/crear%202FA.md) currently duplicates the session endpoints already documented in [docs/sesiones.md](docs/sesiones.md). No separate 2FA creation endpoint was documented there, so no dedicated command was added for it.
- The bot stores chat credentials in a local JSON file to make repeated calls easier during development.
- The P2P monitor stores rules, histories and worker state in a separate JSON file so authentication and monitoring concerns remain isolated.
- Applied-offer listings currently do not include web links because the QvaPay documentation in [docs/listar p2p.md](docs/listar%20p2p.md) and [docs/detalles p2p.md](docs/detalles%20p2p.md) does not confirm a stable frontend route for a P2P offer UUID.
