from __future__ import annotations

from pathlib import Path

from qvapay_bot.state import BotStateStore


# uv run pytest -s tests/test_state_store.py
def test_state_store_shares_auth_state_between_chat_ids(tmp_path: Path) -> None:
    store = BotStateStore(tmp_path / "bot_state.json")

    state_a = store.get_chat_state(111)
    state_a.bearer_token = "token-1"
    state_a.user_uuid = "user-1"
    store.save_chat_state(111, state_a)

    state_b = store.get_chat_state(222)
    assert state_b.bearer_token == "token-1"
    assert state_b.user_uuid == "user-1"

    state_b.username = "shared-user"
    store.save_chat_state(222, state_b)

    state_a_after = store.get_chat_state(111)
    assert state_a_after.username == "shared-user"


# uv run pytest -s tests/test_state_store.py
def test_state_store_loads_legacy_chat_payload(tmp_path: Path) -> None:
    state_file = tmp_path / "bot_state.json"
    state_file.write_text(
        '{\n'
        '  "chats": {\n'
        '    "111": {\n'
        '      "bearer_token": "legacy-token",\n'
        '      "user_uuid": "legacy-user",\n'
        '      "username": "legacy-name"\n'
        '    }\n'
        '  }\n'
        '}',
        encoding="utf-8",
    )

    store = BotStateStore(state_file)
    state = store.get_chat_state(999)

    assert state.bearer_token == "legacy-token"
    assert state.user_uuid == "legacy-user"
    assert state.username == "legacy-name"
