import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useEventStream } from "../lib/useEventStream";
import type { MonitorEvent, MonitorState } from "../lib/types";

function fmt(n: number | null | undefined, digits = 2): string {
  return typeof n === "number" ? n.toFixed(digits) : "—";
}

function describeEvent(event: MonitorEvent): string {
  const d = event.data as Record<string, any>;
  switch (event.type) {
    case "cycle_completed":
      return `leídas ${d.read_count ?? "?"} · elegibles ${d.filtered_count ?? "?"} · descartadas ${d.discarded_count ?? "?"}`;
    case "offer_selected":
      return d.offer
        ? `${d.offer.coin} ${fmt(d.offer.amount)} @ ratio ${fmt(d.offer.ratio, 4)}`
        : "oferta seleccionada";
    case "apply_result":
      return d.entry ? `${d.entry.result}: ${d.entry.reason ?? ""}` : "resultado";
    case "error":
      return String(d.message ?? "error");
    case "balance_low":
      return `saldo ${fmt(d.balance)}`;
    case "monitor_stopped":
      return `detenido (${d.reason ?? ""})`;
    default:
      return "";
  }
}

function MonitorCard({
  monitor,
  lastCycle,
  onToggle,
  onTest,
  busy,
}: {
  monitor: MonitorState;
  lastCycle: Record<string, any> | undefined;
  onToggle: (m: MonitorState) => void;
  onTest: (m: MonitorState) => void;
  busy: boolean;
}) {
  return (
    <div className="card monitor-card">
      <div className="monitor-card-head">
        <div>
          <div className="monitor-name">{monitor.name}</div>
          <div className="muted small">
            {monitor.target_type} · {monitor.rules.coin ?? "cualquier moneda"} ·{" "}
            {monitor.poll_interval_seconds}s
          </div>
        </div>
        <span className={`badge ${monitor.enabled ? "on" : "off"}`}>
          {monitor.enabled ? "ACTIVO" : "DETENIDO"}
        </span>
      </div>

      <div className="monitor-stats">
        <span>aplicadas: {monitor.applied_count}</span>
        {lastCycle && (
          <span className="muted">
            último: {lastCycle.read_count ?? "?"} leídas / {lastCycle.filtered_count ?? "?"} elegibles
          </span>
        )}
      </div>

      {monitor.last_error && (
        <div className="alert alert-error small">{monitor.last_error}</div>
      )}

      <div className="monitor-card-actions">
        <button
          className={`btn ${monitor.enabled ? "btn-danger" : "btn-primary"}`}
          onClick={() => onToggle(monitor)}
          disabled={busy}
        >
          {monitor.enabled ? "Pausar" : "Iniciar"}
        </button>
        <button
          className="btn btn-ghost"
          onClick={() => onTest(monitor)}
          disabled={busy}
        >
          Probar ciclo
        </button>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const [monitors, setMonitors] = useState<MonitorState[] | null>(null);
  const [balance, setBalance] = useState<number | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const { events, connected } = useEventStream(true);

  const load = useCallback(async () => {
    const resp = await api.listMonitors();
    setMonitors(resp.monitors);
    setBalance(resp.balance);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Refrescar la lista cuando llega un evento relevante.
  useEffect(() => {
    if (events.length === 0) return;
    const type = events[0].type;
    if (["cycle_completed", "apply_result", "monitor_stopped"].includes(type)) {
      load();
    }
  }, [events, load]);

  // Último ciclo por monitor (a partir del feed SSE).
  const lastCycleByMonitor = useMemo(() => {
    const map: Record<string, Record<string, any>> = {};
    for (const e of events) {
      if (e.type !== "cycle_completed") continue;
      const id = (e.data as any).monitor_id as string;
      if (id && !map[id]) map[id] = e.data as Record<string, any>;
    }
    return map;
  }, [events]);

  const toggle = async (m: MonitorState) => {
    setBusyId(m.id);
    try {
      const next = m.enabled
        ? await api.stopMonitor(m.id)
        : await api.startMonitor(m.id);
      setMonitors((prev) => (prev ?? []).map((x) => (x.id === next.id ? next : x)));
    } finally {
      setBusyId(null);
    }
  };

  const test = async (m: MonitorState) => {
    setBusyId(m.id);
    try {
      await api.testCycle(m.id);
      await load();
    } finally {
      setBusyId(null);
    }
  };

  if (!monitors) return <div className="muted">Cargando…</div>;

  const runningCount = monitors.filter((m) => m.enabled).length;

  return (
    <div className="dashboard">
      <div className="cards">
        <div className="card stat">
          <div className="stat-label">Saldo</div>
          <div className="stat-value">{fmt(balance)} QUSD</div>
        </div>
        <div className="card stat">
          <div className="stat-label">Monitores</div>
          <div className="stat-value">{monitors.length}</div>
        </div>
        <div className="card stat">
          <div className="stat-label">Activos</div>
          <div className="stat-value">{runningCount}</div>
        </div>
        <div className="card stat">
          <div className="stat-label">SSE</div>
          <div className="muted small">
            {connected ? "● en vivo" : "○ desconectado"}
          </div>
        </div>
      </div>

      {monitors.length === 0 ? (
        <div className="card muted">
          No hay monitores. Ve a <strong>Reglas</strong> para crear uno.
        </div>
      ) : (
        <div className="monitor-grid">
          {monitors.map((m) => (
            <MonitorCard
              key={m.id}
              monitor={m}
              lastCycle={lastCycleByMonitor[m.id]}
              onToggle={toggle}
              onTest={test}
              busy={busyId === m.id}
            />
          ))}
        </div>
      )}

      <section className="card">
        <h2>Eventos en vivo</h2>
        <div className="event-feed">
          {events.length === 0 && (
            <div className="muted small">Sin eventos todavía…</div>
          )}
          {events.map((e, i) => (
            <div className={`event event-${e.type}`} key={`${e.at}-${i}`}>
              <span className="event-time">{e.at.slice(11, 19)}</span>
              <span className="event-monitor">
                {String((e.data as any).monitor_name ?? "")}
              </span>
              <span className="event-type">{e.type}</span>
              <span className="event-summary">{describeEvent(e)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
