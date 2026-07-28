import { useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { CoinsMap, MonitorState } from "../lib/types";
import MonitorRuleCard from "../components/MonitorRuleCard";

export default function RulesPage() {
  const [monitors, setMonitors] = useState<MonitorState[] | null>(null);
  const [coins, setCoins] = useState<CoinsMap>({});
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    (async () => {
      const [list, coinsResp] = await Promise.all([
        api.listMonitors(),
        api.getCoins().catch(() => ({ coins: {} })),
      ]);
      setMonitors(list.monitors);
      setCoins(coinsResp.coins ?? {});
    })();
  }, []);

  const createMonitor = async () => {
    const name = newName.trim() || `Monitor ${(monitors?.length ?? 0) + 1}`;
    setError(null);
    setBusy(true);
    try {
      const created = await api.createMonitor(name);
      setMonitors((prev) => [...(prev ?? []), created]);
      setNewName("");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al crear");
    } finally {
      setBusy(false);
    }
  };

  const onSaved = (updated: MonitorState) =>
    setMonitors((prev) =>
      (prev ?? []).map((m) => (m.id === updated.id ? updated : m)),
    );
  const onDeleted = (id: string) =>
    setMonitors((prev) => (prev ?? []).filter((m) => m.id !== id));

  if (!monitors) return <div className="muted">Cargando…</div>;

  return (
    <div className="rules-page">
      <div className="page-head">
        <h1>Monitores</h1>
        <div className="create-monitor">
          <input
            type="text"
            placeholder="Nombre del monitor (opcional)"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && createMonitor()}
          />
          <button className="btn btn-primary" onClick={createMonitor} disabled={busy}>
            + Crear monitor
          </button>
        </div>
      </div>

      {error && <div className="alert alert-error">{error}</div>}

      {monitors.length === 0 ? (
        <div className="card muted">
          No hay monitores todavía. Crea el primero arriba.
        </div>
      ) : (
        <div className="rule-cards">
          {monitors.map((m) => (
            <MonitorRuleCard
              key={m.id}
              monitor={m}
              coins={coins}
              onSaved={onSaved}
              onDeleted={onDeleted}
            />
          ))}
        </div>
      )}
    </div>
  );
}
