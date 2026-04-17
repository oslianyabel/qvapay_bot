from __future__ import annotations

import json
import os
from typing import Any

import requests
from config import EMAIL, PASSWORD

BASE_URL = os.getenv("QVAPAY_BASE_URL", "https://api.qvapay.com").rstrip("/")
LOGIN_URL = f"{BASE_URL}/auth/login"
REQUEST_TIMEOUT_SECONDS = 30


def build_headers() -> dict[str, str]:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "qvapay-login-test/1.0",
    }


def print_response(step_name: str, response: requests.Response) -> None:
    print(f"\n[{step_name}] status={response.status_code}")

    try:
        payload: Any = response.json()
    except json.JSONDecodeError:
        print(response.text)
        return

    print(json.dumps(payload, indent=2, ensure_ascii=True))


def send_login(payload: dict[str, Any]) -> requests.Response:
    return requests.post(
        LOGIN_URL,
        headers=build_headers(),
        json=payload,
        timeout=REQUEST_TIMEOUT_SECONDS,
    )


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    TWO_FACTOR_CODE = input("Introduce el codigo 2FA: ")
    first_payload: dict[str, Any] = {
        "email": EMAIL,
        "password": PASSWORD,
        "remember": True,
    }
    first_response = send_login(first_payload)
    print_response("login-step-1", first_response)

    if first_response.status_code == 202:
        second_payload: dict[str, Any] = {
            **first_payload,
            "two_factor_code": TWO_FACTOR_CODE,
        }
        second_response = send_login(second_payload)
        print_response("login-step-2", second_response)
        if not second_response.ok:
            fail(
                "Login failed in step 2. Update TWO_FACTOR_CODE with a valid OTP or 2FA code."
            )
        return

    if not first_response.ok:
        fail("Login failed in step 1. Check EMAIL and PASSWORD.")


if __name__ == "__main__":
    main()
