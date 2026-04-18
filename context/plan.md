# Plan de migración: Bot manual → python-telegram-bot

## Contexto

El bot actual implementa todo el ciclo de polling manualmente:
- `AsyncHttpClient` (basado en `urllib`) llama a `getUpdates` en un `while True`
- El dispatch de comandos, callbacks y FSM (pending commands) se manejan a mano en `QvaPayTelegramBot`
- El envío de mensajes usa llamadas HTTP directas a la API de Telegram
- El monitor P2P corre como `asyncio.Task` gestionado por `P2PMonitorManager`

La librería `python-telegram-bot` (PTB) v22.x provee: `Application`, `CommandHandler`, `CallbackQueryHandler`, `ConversationHandler`, `MessageHandler`, `filters`, `JobQueue`, `CallbackContext`, y gestión automática de polling.

## Dependencias

1. Instalar: `uv add python-telegram-bot`
2. Eliminar de `pyproject.toml`: `requests` (no se usa realmente, el bot usa `urllib`)
3. Conservar: `python-dotenv`

## Módulos que NO cambian

| Módulo | Razón |
|---|---|
| `config.py` | Solo eliminar `telegram_api_base_url`, `telegram_file_base_url`, `telegram_poll_timeout_seconds` (PTB los maneja internamente) |
| `http_client.py` | Sigue usándose para llamadas a la API de QvaPay (no a Telegram) |
| `qvapay_client.py` | Sin cambios, solo consume la API de QvaPay |
| `p2p_models.py` | Sin cambios |
| `p2p_filters.py` | Sin cambios |
| `p2p_formatter.py` | Sin cambios |
| `p2p_repository.py` | Sin cambios |
| `state.py` | Sin cambios (BotStateStore, ChatAuthState, PendingCommandState siguen igual) |

## Módulos que CAMBIAN

### 1. `config.py` — Simplificar Settings

- Eliminar campos: `telegram_api_base_url`, `telegram_file_base_url`, `telegram_poll_timeout_seconds`
- PTB solo necesita `telegram_bot_token` para construir `Application`

### 2. `telegram_bot.py` — Reescritura mayor

Este es el cambio principal. La clase `QvaPayTelegramBot` (~1700 líneas) se refactoriza:

#### 2.1 Estructura nueva del módulo

Dividir `telegram_bot.py` en varios módulos dentro de un paquete `qvapay_bot/handlers/`:

```
qvapay_bot/
  handlers/
    __init__.py          # build_application() factory
    common.py            # funciones aux: send_text, split_text, allowed_chat_filter
    command_handlers.py  # handlers de comandos: help, cancel, auth_status, login, balance, etc.
    callback_handlers.py # handlers de CallbackQuery (inline buttons)
    conversation.py      # ConversationHandler para flujos FSM (rules, pending commands)
    monitor_handlers.py  # monitor_on, monitor_off, monitor_status, monitor_test, history
    api_commands.py      # ejecución genérica de comandos QvaPay API
```

#### 2.2 Mapeo de la arquitectura actual → PTB

| Actual | PTB |
|---|---|
| `while True: getUpdates()` | `Application.run_polling()` |
| `_handle_update()` dispatch manual | `CommandHandler`, `MessageHandler`, `CallbackQueryHandler` registrados en `Application` |
| `_dispatch_command()` con `if/elif` | Un `CommandHandler` por comando o grupo de comandos |
| `PendingCommandState` FSM manual | `ConversationHandler` con estados explícitos |
| `_handle_callback_query()` con prefijos | `CallbackQueryHandler(pattern=r"^prefix")` por cada prefijo |
| `_send_text()` vía HTTP | `context.bot.send_message()` o `update.message.reply_text()` |
| `_send_message_with_keyboard()` vía HTTP | `update.message.reply_text(reply_markup=InlineKeyboardMarkup(...))` |
| `_answer_callback_query()` vía HTTP | `update.callback_query.answer()` |
| `_extract_photo_upload()` vía HTTP getFile | `context.bot.get_file()` + `file.download_as_bytearray()` |
| `allowed_chat_ids` check manual | `filters.Chat(chat_ids)` en cada handler |
| `P2PMonitorManager` con `asyncio.Task` | Mantener como está (tasks manuales), o migrar a `JobQueue.run_repeating()` |

#### 2.3 ConversationHandler para flujos FSM

El bot actual tiene un sistema de pending commands con `PendingCommandState`. Esto se mapea a `ConversationHandler`:

**Flujo de reglas (`/rules`)**:
```
entry_points: [CommandHandler("rules", rules_start)]
states:
  RULE_NAME: [CallbackQueryHandler(pattern=r"^prn:", rule_name_selected)]
  RULE_VALUE: [
    CallbackQueryHandler(pattern=r"^prc:", rule_coin_selected),
    CallbackQueryHandler(pattern=r"^pot:", offer_type_selected),
    MessageHandler(filters.TEXT & ~filters.COMMAND, rule_value_received),
  ]
fallbacks: [CommandHandler("cancel", cancel)]
```

**Flujo de comandos API con campos faltantes**:
```
entry_points: [CommandHandler(api_commands, api_command_start)]
states:
  WAITING_FIELD: [
    MessageHandler(filters.TEXT & ~filters.COMMAND, field_received),
    MessageHandler(filters.PHOTO, photo_received),
  ]
fallbacks: [CommandHandler("cancel", cancel)]
```

**Flujo 2FA para login**:
```
entry_points: [CommandHandler("login", login_start)]  
states:
  WAITING_2FA: [MessageHandler(filters.TEXT & ~filters.COMMAND, two_factor_received)]
fallbacks: [CommandHandler("cancel", cancel)]
```

#### 2.4 Filtro de chat autorizado

Crear un filtro reutilizable:
```python
allowed_filter = filters.Chat(chat_ids=settings.allowed_chat_ids)
```
Aplicar en cada handler: `CommandHandler("help", help_handler, filters=allowed_filter)`

#### 2.5 Datos compartidos via `bot_data`

Inyectar en `Application.bot_data` las dependencias compartidas:
```python
app.bot_data["settings"] = settings
app.bot_data["qvapay_client"] = qvapay_client
app.bot_data["state_store"] = state_store
app.bot_data["p2p_repository"] = p2p_repository
app.bot_data["p2p_monitor_manager"] = p2p_monitor_manager
```
Acceder en handlers via `context.bot_data["state_store"]`.

#### 2.6 Handlers de CallbackQuery

Reemplazar el bloque monolítico `_handle_callback_query()` con handlers individuales:

```python
# Cada prefijo de callback_data → un CallbackQueryHandler
CallbackQueryHandler(applied_detail_handler, pattern=r"^adh:")
CallbackQueryHandler(applied_list_page_handler, pattern=r"^adlp:")
CallbackQueryHandler(cancel_p2p_handler, pattern=r"^cp2p:")
CallbackQueryHandler(monitor_on_confirm_handler, pattern=r"^mon_on:")
# Los de reglas (prn:, prc:, pot:) van dentro del ConversationHandler
```

### 3. `p2p_monitor.py` — Cambios menores

- Las callbacks `send_text` y `send_message_with_keyboard` ahora usan `context.bot.send_message()` en lugar del HTTP client directo
- Opción: adaptar `SendText` y `SendMessageWithKeyboard` para recibir el `Bot` de PTB
- Los `asyncio.Task` del monitor pueden mantenerse tal cual, o migrarse a `Application.create_task()` para mejor manejo de errores

### 4. `main.py` — Simplificar

```python
from qvapay_bot.config import Settings
from qvapay_bot.handlers import build_application

def main() -> None:
    configure_logging()
    settings = Settings.from_env()
    app = build_application(settings)
    app.run_polling()

if __name__ == "__main__":
    main()
```

Ya no se necesita `asyncio.run()` porque `run_polling()` lo maneja.

## Secuencia de tareas

### Fase 1: Preparación
1. Instalar `python-telegram-bot` con `uv add python-telegram-bot`
2. Simplificar `config.py` (eliminar campos de Telegram API manual)
3. Crear paquete `qvapay_bot/handlers/`

### Fase 2: Infraestructura PTB
4. Crear `handlers/__init__.py` con factory `build_application(settings)` que construya el `Application`
5. Crear `handlers/common.py` con utilidades compartidas (split_text, format helpers, allowed_filter)
6. Adaptar `p2p_monitor.py` para que `send_text`/`send_message_with_keyboard` usen `Bot` de PTB

### Fase 3: Handlers simples (sin estado)
7. Migrar `/help`, `/start` → `CommandHandler`
8. Migrar `/auth_status` → `CommandHandler`
9. Migrar `/balance` → `CommandHandler`
10. Migrar `/monitor_off`, `/monitor_status`, `/rules_show`, `/history`, `/monitor_test` → `CommandHandler`
11. Migrar `/monitor_on` → `CommandHandler` + confirmación vía `CallbackQueryHandler`
12. Migrar CallbackQueryHandlers independientes (adh:, adlp:, cp2p:, mon_on:)

### Fase 4: ConversationHandlers (flujos con estado)
13. Migrar `/rules` → `ConversationHandler` con estados RULE_NAME → RULE_VALUE
14. Migrar comandos API genéricos (list_p2p, mark_p2p_paid, rate_p2p, etc.) → `ConversationHandler` para campos faltantes
15. Migrar `/login` + flujo 2FA → `ConversationHandler` con estado WAITING_2FA

### Fase 5: Integración y error handling
16. Registrar `error_handler` global que envíe errores al dev por Telegram
17. Actualizar `main.py` para usar `build_application()` + `run_polling()`
18. Adaptar `post_init` para restaurar tareas del monitor P2P

### Fase 6: Limpieza
19. Eliminar el antiguo `telegram_bot.py`
20. Eliminar llamadas HTTP a la API de Telegram del `http_client.py` (si ya no se usan)
21. Ejecutar `uv run ruff check` y corregir errores
22. Ejecutar tests existentes y verificar que pasen
23. Probar el bot manualmente

## Riesgos y decisiones pendientes

1. **ConversationHandler vs FSM manual**: **DECISIÓN → Aceptar pérdida de persistencia**. Al reiniciar el bot se pierden flujos en curso. Se usa `ConversationHandler` puro de PTB sin `persistent=True`.

2. **Monitor P2P**: **DECISIÓN → Migrar a `JobQueue.run_repeating()`**. Refactorizar `P2PMonitorManager` para usar JobQueue de PTB en lugar de `asyncio.Task` manuales.

3. **Tests**: Los tests actuales no testean `telegram_bot.py` directamente (testean filters, formatter, repository). No deberían romperse.

## Estimación de complejidad

| Fase | Archivos afectados | Complejidad |
|---|---|---|
| Fase 1 | config.py, pyproject.toml | Baja |
| Fase 2 | handlers/__init__.py, common.py, p2p_monitor.py | Media |
| Fase 3 | handlers/command_handlers.py, callback_handlers.py, monitor_handlers.py | Media |
| Fase 4 | handlers/conversation.py, api_commands.py | Alta |
| Fase 5 | main.py, handlers/__init__.py | Baja |
| Fase 6 | Limpieza general | Baja |
