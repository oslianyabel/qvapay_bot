from __future__ import annotations

import html as _html
from datetime import datetime

from qvapay_bot.p2p_models import (
    OfferHistoryEntry,
    OfferProcessResult,
    P2PMonitorChatState,
    P2PMonitorCycleReport,
    P2POfferSnapshot,
    P2POfferType,
)

KeyboardRows = list[list[dict[str, str]]]

QVAPAY_P2P_URL = "https://www.qvapay.com/p2p-pub/"
APPLIED_LIST_PAGE_SIZE = 10
_APPLIED_LIST_PAGE_CALLBACK_PREFIX = "adlp:"


def format_monitor_status(
    state: P2PMonitorChatState, balance: float | None = None
) -> str:
    rules = state.rules
    offer_type_label = _format_offer_type_label(state.target_type, rules.coin)
    active_emoji = "✅" if state.enabled else "❌"
    lines = [
        "Estado del monitor P2P",
        f"activo: {active_emoji}",
        f"moneda: {rules.coin or 'cualquiera'}",
        f"tipo_oferta: {offer_type_label}",
    ]
    if state.enabled:
        applied_count = sum(
            1 for e in state.filtered_history if e.result == OfferProcessResult.APPLIED
        )
        lines.append(f"ofertas_aplicadas: {applied_count}")
    lines += [
        f"ratio_min: {_format_optional_number(rules.min_ratio)}",
        f"ratio_max: {_format_optional_number(rules.max_ratio)}",
        f"monto_min: {_format_optional_number(rules.min_amount)}",
        f"monto_max: {_format_optional_number(rules.max_amount)}",
        f"solo_kyc: {'sí' if rules.only_kyc else 'no'}",
        f"solo_vip: {'sí' if rules.only_vip else 'no'}",
        f"intervalo_segundos: {state.poll_interval_seconds}",
    ]
    balance_str = f"${balance:.2f}" if isinstance(balance, float) else "$-"
    lines.append(f"saldo_disponible: {balance_str}")
    if state.last_error:
        lines.append(f"ultimo_error: {state.last_error}")
    return "\n".join(lines)


def format_rules(state: P2PMonitorChatState) -> str:
    rules = state.rules
    offer_type_label = _format_offer_type_label(state.target_type, rules.coin)
    lines = [
        "Reglas P2P",
        f"moneda: {rules.coin or 'cualquiera'}",
        f"tipo_oferta: {offer_type_label}",
        f"ratio_min: {_format_optional_number(rules.min_ratio)}",
        f"ratio_max: {_format_optional_number(rules.max_ratio)}",
        f"monto_min: {_format_optional_number(rules.min_amount)}",
        f"monto_max: {_format_optional_number(rules.max_amount)}",
        f"solo_kyc: {'sí' if rules.only_kyc else 'no'}",
        f"solo_vip: {'sí' if rules.only_vip else 'no'}",
    ]
    return "\n".join(lines)


def format_monitor_on_confirmation(
    state: P2PMonitorChatState, poll_interval_seconds: int
) -> str:
    """Devuelve texto HTML para la pantalla de confirmación al activar el monitor."""
    rules = state.rules
    offer_type_label = _format_offer_type_label(state.target_type, rules.coin)
    lines = [
        "<b>Confirmar activación del monitor P2P</b>",
        "",
        f"intervalo: {poll_interval_seconds}s",
        f"tipo_oferta: {offer_type_label}",
        "",
        "<b>Reglas activas:</b>",
        f"moneda: {rules.coin or 'cualquiera'}",
        f"ratio_min: {_format_optional_number(rules.min_ratio)}",
        f"ratio_max: {_format_optional_number(rules.max_ratio)}",
        f"monto_min: {_format_optional_number(rules.min_amount)}",
        f"monto_max: {_format_optional_number(rules.max_amount)}",
        f"solo_kyc: {'sí' if rules.only_kyc else 'no'}",
        f"solo_vip: {'sí' if rules.only_vip else 'no'}",
    ]
    return "\n".join(lines)


def format_offer_found_message(offer: P2POfferSnapshot) -> str:
    """Mensaje amigable al detectar una oferta P2P coincidente."""
    offer_type_label = "compra" if offer.offer_type == P2POfferType.BUY else "venta"
    url = f"{QVAPAY_P2P_URL}{offer.uuid}"
    return (
        "🔔 <b>¡Oferta P2P encontrada!</b>\n\n"
        f"💱 <b>Tipo:</b> {offer_type_label}\n"
        f"🪙 <b>Moneda:</b> {_html.escape(offer.coin)}\n"
        f"💰 <b>Monto:</b> {offer.amount:.2f} QUSD\n"
        f"📈 <b>Ratio:</b> {offer.ratio:.4f}\n"
        f'🔗 <a href="{url}">Ver oferta</a>'
    )


def format_offer_notification(
    offer: P2POfferSnapshot,
    *,
    evaluated_at: str,
    result_text: str,
    result: OfferProcessResult | None = None,
) -> tuple[str, KeyboardRows]:
    if result == OfferProcessResult.APPLIED:
        result_icon = "🟢"
    elif result in {OfferProcessResult.REJECTED, OfferProcessResult.ERROR}:
        result_icon = "🔴"
    elif result == OfferProcessResult.RATE_LIMITED:
        result_icon = "⏳"
    else:
        result_icon = "ℹ️"

    lines = [
        "<b>Oportunidad P2P</b>",
        f"uuid: <code>{_html.escape(offer.uuid)}</code>",
        f"tipo: {offer.offer_type.value}",
        f"moneda: {offer.coin}",
        f"monto: {offer.amount:.2f}",
        f"recibe: {offer.receive:.2f}",
        f"ratio: {offer.ratio:.4f}",
        f"usuario: {_html.escape(offer.advertiser.username or '-')}",
        f"usuario_kyc: {'sí' if offer.advertiser.kyc else 'no'}",
        f"usuario_vip: {'sí' if offer.advertiser.vip else 'no'}",
        f"resultado: {result_icon} {_html.escape(result_text)}",
        f'ver oferta: <a href="{QVAPAY_P2P_URL}{offer.uuid}">{QVAPAY_P2P_URL}{offer.uuid}</a>',
    ]
    text = "\n".join(lines)

    keyboard: KeyboardRows = []
    if result is not None:
        keyboard = [
            [
                {
                    "text": "🔍 Ver detalle",
                    "callback_data": f"adh:{offer.uuid}:{evaluated_at}",
                }
            ]
        ]

    return text, keyboard


def format_cycle_report(report: P2PMonitorCycleReport) -> str:
    lines = [
        "Prueba del monitor P2P",
        f"ofertas_leídas: {report.read_count}",
        f"ofertas_filtradas: {report.filtered_count}",
        f"ofertas_descartadas: {report.discarded_count}",
    ]
    if report.top_discarded_reasons:
        lines.extend(
            [
                "",
                "razones_descarte:",
                *report.top_discarded_reasons,
            ]
        )
    if report.final_entry is not None:
        lines.extend(
            [
                "",
                f"seleccionado_uuid: {report.final_entry.uuid}",
                f"seleccionado_resultado: {report.final_entry.result.value if report.final_entry.result else 'n/a'}",
                f"seleccionado_razon: {report.final_entry.reason or '-'}",
            ]
        )
    elif report.matched_entry is not None:
        lines.extend(
            [
                "",
                f"seleccionado_uuid: {report.matched_entry.uuid}",
                "seleccionado_resultado: solo_coincidencia",
            ]
        )
    if report.rate_limited:
        lines.append("limite_de_tasa: sí")
    if report.error_message:
        lines.append(f"error: {report.error_message}")
    return "\n".join(lines)


def format_applied_history(
    applied_history: list[OfferHistoryEntry],
    lost_race_history: list[OfferHistoryEntry],
) -> str:
    if not applied_history and not lost_race_history:
        return "Aún no se han procesado ofertas P2P del monitor."

    lines = ["Ofertas P2P procesadas"]
    if applied_history:
        lines.append("")
        lines.append("aplicadas:")
        lines.extend(_format_history_lines(applied_history))
    if lost_race_history:
        lines.append("")
        lines.append("perdidas_por_carrera:")
        lines.extend(_format_history_lines(lost_race_history))
    return "\n".join(lines)


def format_applied_list_keyboard(
    applied_history: list[OfferHistoryEntry],
    lost_race_history: list[OfferHistoryEntry],
    page: int = 0,
    coin_averages: dict[str, float] | None = None,
) -> tuple[str, list[list[dict[str, str]]]]:
    """Devuelve (texto_cabecera, filas_keyboard) para la lista de ofertas procesadas."""
    if not applied_history and not lost_race_history:
        return "Aún no se han procesado ofertas P2P del monitor.", []

    all_entries = list(applied_history) + list(lost_race_history)
    total = len(all_entries)
    total_pages = max(1, (total + APPLIED_LIST_PAGE_SIZE - 1) // APPLIED_LIST_PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * APPLIED_LIST_PAGE_SIZE
    page_entries = all_entries[start : start + APPLIED_LIST_PAGE_SIZE]

    lost_race_uuids = {e.uuid for e in lost_race_history}

    header_lines = ["<b>Ofertas P2P procesadas</b>"]
    if applied_history:
        header_lines.append(f"📋 aplicadas: {len(applied_history)}")
    if lost_race_history:
        header_lines.append(f"🏁 perdidas: {len(lost_race_history)}")
    if total_pages > 1:
        header_lines.append(f"📄 página {page + 1}/{total_pages}")
    header_lines.append("\nPresiona un botón para ver los detalles:")

    keyboard_rows: list[list[dict[str, str]]] = []
    for entry in page_entries:
        is_lost = entry.uuid in lost_race_uuids
        icon = _result_icon(entry.result, is_lost_race=is_lost)
        status_icon = _status_emoji(entry.status)
        date_str = _format_short_date(entry.applied_at or entry.evaluated_at)
        below_avg = ""
        if coin_averages and entry.coin in coin_averages:
            if entry.ratio < coin_averages[entry.coin]:
                below_avg = "⚠️"
        button_text = f"{icon}{status_icon}{below_avg} {entry.coin} | {entry.amount:.2f} | {entry.ratio:.4f} | {date_str}"
        callback_data = f"adh:{entry.uuid}:{entry.evaluated_at}"
        keyboard_rows.append([{"text": button_text, "callback_data": callback_data}])

    nav_row: list[dict[str, str]] = []
    if page > 0:
        nav_row.append(
            {
                "text": "◀ Anterior",
                "callback_data": f"{_APPLIED_LIST_PAGE_CALLBACK_PREFIX}{page - 1}",
            }
        )
    if page < total_pages - 1:
        nav_row.append(
            {
                "text": "Siguiente ▶",
                "callback_data": f"{_APPLIED_LIST_PAGE_CALLBACK_PREFIX}{page + 1}",
            }
        )
    if nav_row:
        keyboard_rows.append(nav_row)

    return "\n".join(header_lines), keyboard_rows


def _result_icon(result: OfferProcessResult | None, *, is_lost_race: bool) -> str:
    if is_lost_race:
        return "🏁"
    if result is None:
        return "❓"
    if result == OfferProcessResult.APPLIED:
        return "✅"
    if result == OfferProcessResult.REJECTED:
        return "❌"
    if result == OfferProcessResult.RATE_LIMITED:
        return "⏳"
    if result == OfferProcessResult.ERROR:
        return "🚫"
    return "❓"


def format_applied_detail(entry: OfferHistoryEntry) -> str:
    """Devuelve texto HTML con los detalles de una oferta procesada. El UUID se muestra en bloque de código para fácil copia."""
    offer_url = f"{QVAPAY_P2P_URL}{entry.uuid}"
    status_icon = _status_emoji(entry.status)
    is_lost = entry.result == OfferProcessResult.LOST_RACE
    result_icon = _result_icon(entry.result, is_lost_race=is_lost)
    result_label = entry.result.value if entry.result else "-"
    lines = [
        "<b>Detalle de oferta P2P procesada</b>",
        f"uuid: <code>{_html.escape(entry.uuid)}</code>",
        f"estado: {status_icon} {_html.escape(entry.status)}",
        f"moneda: {_html.escape(entry.coin)}",
        f"monto: {entry.amount:.2f}",
        f"recibe: {entry.receive:.2f}",
        f"ratio: {entry.ratio:.4f}",
        f"usuario: {_html.escape(entry.username or '-')}",
        f"primera_detección: {_html.escape(_format_date_only(entry.first_detected_at))}",
        f"evaluado_en: {_html.escape(_format_date_only(entry.evaluated_at))}",
        f"notificado_en: {_html.escape(_format_date_only(entry.notified_at))}",
        f"aplicado_en: {_html.escape(_format_date_only(entry.applied_at))}",
        f"resultado: {result_icon} {_html.escape(result_label)}",
        f"razón: {_html.escape(entry.reason or '-')}",
        f'ver oferta: <a href="{offer_url}">{offer_url}</a>',
    ]
    return "\n".join(lines)


def _format_history_lines(entries: list[OfferHistoryEntry]) -> list[str]:
    return [
        (
            f"- {entry.uuid} | {entry.coin} | ratio={entry.ratio:.4f} | "
            f"user={entry.username or '-'} | result={entry.result.value if entry.result else '-'}"
        )
        for entry in entries
    ]


def format_cancel_p2p_keyboard(
    applied_history: list[OfferHistoryEntry],
) -> tuple[str, list[list[dict[str, str]]]]:
    """Devuelve (texto_cabecera, filas_keyboard) para cancelar ofertas aplicadas activas."""
    _TERMINAL_STATUSES = {"cancelled", "completed", "rejected"}
    cancellable = [
        entry
        for entry in applied_history
        if entry.result == OfferProcessResult.APPLIED
        and entry.status.lower() not in _TERMINAL_STATUSES
    ]
    if not cancellable:
        return "No hay ofertas aplicadas pendientes de cancelar.", []

    header = "<b>Selecciona la oferta a cancelar:</b>"
    keyboard_rows: list[list[dict[str, str]]] = []
    for entry in cancellable:
        date_str = _format_short_date(entry.applied_at or entry.evaluated_at)
        button_text = (
            f"{entry.coin} | {entry.ratio:.4f} | {entry.amount:.2f} | {date_str}"
        )
        callback_data = f"cp2p:{entry.uuid}:{entry.evaluated_at}"
        keyboard_rows.append([{"text": button_text, "callback_data": callback_data}])
    return header, keyboard_rows


def _format_short_date(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%d/%m %H:%M")
    except ValueError:
        return iso[:16]


def _format_date_only(iso: str | None) -> str:
    if not iso:
        return "-"
    return iso[:10]


def _status_emoji(status: str) -> str:
    mapping: dict[str, str] = {
        "open": "⏳",
        "paid": "💰",
        "completed": "✅",
        "cancelled": "❌",
        "rejected": "❌",
    }
    return mapping.get(status.lower(), "❓")


def _format_offer_type_label(offer_type: P2POfferType, coin: str | None) -> str:
    coin_label = coin or "la moneda"
    if offer_type == P2POfferType.BUY:
        return f"� Vender — Vendes QUSD, compras {coin_label}"
    if offer_type == P2POfferType.SELL:
        return f"🛒 Comprar — Compras QUSD, vendes {coin_label}"
    return "🔄 Cualquiera"


def _format_optional_number(value: float | None) -> str:
    if value is None:
        return "any"
    return f"{value:.4f}" if not value.is_integer() else str(int(value))
