import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { History, HistoryEntry, MonitorState } from "../lib/types";

const TABS: { key: keyof History; label: string }[] = [
  { key: "applied", label: "Aplicadas" },
  { key: "lost_race", label: "Perdidas" },
  { key: "filtered", label: "Elegibles" },
  { key: "discarded", label: "Descartadas" },
];

function fmt(n: number, d = 2): string {
  return n.toFixed(d);
}

function Table({ entries }: { entries: HistoryEntry[] }) {
  if (entries.length === 0) return <div className="muted small">Sin registros.</div>;
  return (
    <table className="table">
      <thead>
        <tr>
          <th>Moneda</th>
          <th>Monto</th>
          <th>Recibe</th>
          <th>Ratio</th>
          <th>Usuario</th>
          <th>Resultado</th>
          <th>Motivo</th>
          <th>Evaluado</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        {entries.map((e) => (
          <tr key={e.uuid + e.evaluated_at}>
            <td>{e.coin}</td>
            <td>{fmt(e.amount)}</td>
            <td>{fmt(e.receive)}</td>
            <td>{fmt(e.ratio, 4)}</td>
            <td>{e.username ?? "—"}</td>
            <td>{e.result ?? "—"}</td>
            <td className="muted small">{e.reason ?? "—"}</td>
            <td className="muted small">{e.evaluated_at.slice(0, 19)}</td>
            <td>
              <a href={e.link} target="_blank" rel="noreferrer">
                ver
              </a>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function HistoryPage() {
  const [monitors, setMonitors] = useState<MonitorState[]>([]);
  const [monitorId, setMonitorId] = useState<string>("");
  const [history, setHistory] = useState<History | null>(null);
  const [tab, setTab] = useState<keyof History>("applied");

  useEffect(() => {
    api.listMonitors().then((resp) => {
      setMonitors(resp.monitors);
      if (resp.monitors.length > 0) setMonitorId(resp.monitors[0].id);
    });
  }, []);

  useEffect(() => {
    if (!monitorId) {
      setHistory(null);
      return;
    }
    api.getHistory(monitorId).then(setHistory);
  }, [monitorId]);

  if (monitors.length === 0) {
    return (
      <div className="card muted">
        No hay monitores. Crea uno en <strong>Reglas</strong>.
      </div>
    );
  }

  return (
    <div className="card">
      <div className="history-head">
        <label className="inline-label">
          Monitor
          <select value={monitorId} onChange={(e) => setMonitorId(e.target.value)}>
            {monitors.map((m) => (
              <option key={m.id} value={m.id}>
                {m.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="tabs">
        {TABS.map((t) => (
          <button
            key={t.key}
            className={`tab ${tab === t.key ? "active" : ""}`}
            onClick={() => setTab(t.key)}
          >
            {t.label} ({history ? history[t.key].length : 0})
          </button>
        ))}
      </div>
      <div className="table-wrap">
        {history ? <Table entries={history[tab]} /> : <div className="muted">Cargando…</div>}
      </div>
    </div>
  );
}
