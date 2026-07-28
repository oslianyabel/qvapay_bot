import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError } from "../lib/api";
import type { CoinsMap, MonitorState } from "../lib/types";
import MonitorRuleCard from "../components/MonitorRuleCard";
import Modal from "../components/Modal";

export default function RulesPage() {
  const [monitors, setMonitors] = useState<MonitorState[] | null>(null);
  const [coins, setCoins] = useState<CoinsMap>({});
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

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

  const openCreate = () => {
    setError(null);
    setNewName(`Monitor ${(monitors?.length ?? 0) + 1}`);
    setShowCreate(true);
  };

  const submitCreate = async (e?: FormEvent) => {
    e?.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setError(null);
    setCreating(true);
    try {
      const created = await api.createMonitor(name);
      setMonitors((prev) => [...(prev ?? []), created]);
      setShowCreate(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al crear el monitor");
    } finally {
      setCreating(false);
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
        <button className="btn btn-primary" onClick={openCreate}>
          + Nuevo monitor
        </button>
      </div>

      {monitors.length === 0 ? (
        <div className="card">
          <p className="muted" style={{ margin: 0 }}>
            Aún no tienes monitores. Crea el primero con <strong>“+ Nuevo monitor”</strong>{" "}
            y define sus reglas: moneda, tipo de oferta, ratios y montos.
          </p>
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

      {showCreate && (
        <Modal title="Nuevo monitor" onClose={() => setShowCreate(false)}>
          <form onSubmit={submitCreate} className="modal-body" style={{ padding: 0, gap: "1rem" }}>
            <label>
              Nombre del monitor
              <input
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Ej: CUP venta rápida"
                maxLength={60}
              />
            </label>
            <p className="muted small" style={{ margin: 0 }}>
              Podrás configurar sus reglas (moneda, ratios, montos) después de crearlo.
            </p>
            {error && <div className="alert alert-error">{error}</div>}
            <div className="modal-actions">
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowCreate(false)}
              >
                Cancelar
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={creating || !newName.trim()}
              >
                {creating ? "Creando…" : "Crear monitor"}
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
