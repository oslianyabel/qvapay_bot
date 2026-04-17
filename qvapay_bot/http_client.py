from __future__ import annotations

import asyncio
import json
import mimetypes
import uuid
from dataclasses import dataclass
from email.message import Message
from typing import TypeAlias
from urllib import error, parse, request

JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]


@dataclass(slots=True, frozen=True)
class FileUpload:
    filename: str
    content: bytes
    content_type: str | None = None


@dataclass(slots=True, frozen=True)
class HttpResponse:
    status_code: int
    headers: dict[str, str]
    body: JsonValue | str | None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def content_type(self) -> str:
        return self.headers.get("Content-Type", "")


class AsyncHttpClient:
    def __init__(self, timeout_seconds: float) -> None:
        self._timeout_seconds = timeout_seconds

    async def request(
        self,
        method: str,
        url: str,
        *,
        headers: dict[str, str] | None = None,
        query: dict[str, JsonValue] | None = None,
        json_body: JsonValue | None = None,
        multipart_fields: dict[str, JsonValue] | None = None,
        multipart_files: dict[str, FileUpload] | None = None,
        timeout_seconds: float | None = None,
    ) -> HttpResponse:
        return await asyncio.to_thread(
            self._request_sync,
            method,
            url,
            headers or {},
            query or {},
            json_body,
            multipart_fields or {},
            multipart_files or {},
            timeout_seconds or self._timeout_seconds,
        )

    async def get_bytes(
        self,
        url: str,
        *,
        timeout_seconds: float | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        return await asyncio.to_thread(
            self._get_bytes_sync,
            url,
            timeout_seconds or self._timeout_seconds,
        )

    def _request_sync(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        query: dict[str, JsonValue],
        json_body: JsonValue | None,
        multipart_fields: dict[str, JsonValue],
        multipart_files: dict[str, FileUpload],
        timeout_seconds: float,
    ) -> HttpResponse:
        request_url = self._build_url(url, query)
        request_headers = {"User-Agent": "qvapay-telegram-bot/1.0", **headers}
        payload: bytes | None = None

        if multipart_files:
            payload, content_type = self._encode_multipart(
                multipart_fields,
                multipart_files,
            )
            request_headers["Content-Type"] = content_type
        elif json_body is not None:
            payload = json.dumps(json_body, ensure_ascii=True).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")

        req = request.Request(
            request_url,
            data=payload,
            headers=request_headers,
            method=method.upper(),
        )

        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                return self._build_response(
                    status_code=response.status,
                    headers=response.headers,
                    payload=response.read(),
                )
        except error.HTTPError as exc:
            return self._build_response(
                status_code=exc.code,
                headers=exc.headers,
                payload=exc.read(),
            )

    def _get_bytes_sync(
        self,
        url: str,
        timeout_seconds: float,
    ) -> tuple[int, bytes, dict[str, str]]:
        req = request.Request(url, headers={"User-Agent": "qvapay-telegram-bot/1.0"})
        try:
            with request.urlopen(req, timeout=timeout_seconds) as response:
                headers = self._normalize_headers(response.headers)
                return response.status, response.read(), headers
        except error.HTTPError as exc:
            return exc.code, exc.read(), self._normalize_headers(exc.headers)

    def _build_response(
        self,
        *,
        status_code: int,
        headers: Message,
        payload: bytes,
    ) -> HttpResponse:
        normalized_headers = self._normalize_headers(headers)
        content_type = normalized_headers.get("Content-Type", "")
        decoded_text = payload.decode("utf-8", errors="replace")

        if "application/json" in content_type:
            try:
                parsed_body: JsonValue | str | None = json.loads(decoded_text)
            except json.JSONDecodeError:
                parsed_body = decoded_text
        else:
            parsed_body = decoded_text

        return HttpResponse(
            status_code=status_code,
            headers=normalized_headers,
            body=parsed_body,
        )

    @staticmethod
    def _normalize_headers(headers: Message) -> dict[str, str]:
        return {key: value for key, value in headers.items()}

    @staticmethod
    def _build_url(url: str, query: dict[str, JsonValue]) -> str:
        if not query:
            return url

        items: list[tuple[str, str]] = []
        for key, value in query.items():
            if value is None:
                continue
            if isinstance(value, list):
                items.extend((key, str(item)) for item in value)
            else:
                items.append((key, str(value)))

        encoded_query = parse.urlencode(items, doseq=True)
        return f"{url}?{encoded_query}" if encoded_query else url

    @staticmethod
    def _encode_multipart(
        fields: dict[str, JsonValue],
        files: dict[str, FileUpload],
    ) -> tuple[bytes, str]:
        boundary = f"----qvapay-{uuid.uuid4().hex}"
        body = bytearray()

        for field_name, value in fields.items():
            if value is None:
                continue
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(
                (
                    f'Content-Disposition: form-data; name="{field_name}"\r\n\r\n'
                    f"{value}\r\n"
                ).encode("utf-8")
            )

        for field_name, file_upload in files.items():
            content_type = (
                file_upload.content_type
                or mimetypes.guess_type(file_upload.filename)[0]
                or "application/octet-stream"
            )
            body.extend(f"--{boundary}\r\n".encode("utf-8"))
            body.extend(
                (
                    f'Content-Disposition: form-data; name="{field_name}"; '
                    f'filename="{file_upload.filename}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8")
            )
            body.extend(file_upload.content)
            body.extend(b"\r\n")

        body.extend(f"--{boundary}--\r\n".encode("utf-8"))
        return bytes(body), f"multipart/form-data; boundary={boundary}"
