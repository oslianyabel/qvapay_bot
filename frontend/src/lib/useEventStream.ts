import { useEffect, useRef, useState } from "react";
import type { MonitorEvent } from "./types";

const MAX_EVENTS = 100;

/**
 * Se conecta al stream SSE `/api/events` (same-origin, la cookie de sesión viaja
 * sola) y mantiene la lista de los últimos eventos del monitor.
 */
export function useEventStream(enabled: boolean) {
  const [events, setEvents] = useState<MonitorEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const sourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!enabled) return;

    const source = new EventSource("/api/events", { withCredentials: true });
    sourceRef.current = source;

    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false);

    const handler = (event: MessageEvent) => {
      try {
        const parsed = JSON.parse(event.data) as MonitorEvent;
        setEvents((prev) => [parsed, ...prev].slice(0, MAX_EVENTS));
      } catch {
        // ignora mensajes no-JSON (heartbeats)
      }
    };

    const eventTypes = [
      "cycle_started",
      "offer_selected",
      "apply_result",
      "cycle_completed",
      "error",
      "balance_low",
      "monitor_stopped",
    ];
    for (const type of eventTypes) source.addEventListener(type, handler);

    return () => {
      for (const type of eventTypes) source.removeEventListener(type, handler);
      source.close();
      setConnected(false);
    };
  }, [enabled]);

  const clear = () => setEvents([]);
  return { events, connected, clear };
}
