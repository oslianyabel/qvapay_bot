import { useState, type FormEvent } from "react";
import { api, ApiError, type RulesPayload } from "../lib/api";
import type {
  ApplyMode,
  CoinsMap,
  MonitorState,
  OfferType,
  SelectionStrategy,
} from "../lib/types";

function numOrNull(v: string): number | null {
  if (v.trim() === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

interface Props {
  monitor: MonitorState;
  coins: CoinsMap;
  onSaved: (updated: MonitorState) => void;
  onDeleted: (id: string) => void;
}

export default function MonitorRuleCard({ monitor, coins, onSaved, onDeleted }: Props) {
  const [name, setName] = useState(monitor.name);
  const [form, setForm] = useState<RulesPayload>({
    target_type: monitor.target_type,
    selection_strategy: monitor.selection_strategy,
    apply_mode: monitor.apply_mode,
    poll_interval_seconds: monitor.poll_interval_seconds,
    coin: monitor.rules.coin,
    min_ratio: monitor.rules.min_ratio,
    max_ratio: monitor.rules.max_ratio,
    min_amount: monitor.rules.min_amount,
    max_amount: monitor.rules.max_amount,
    only_kyc: monitor.rules.only_kyc,
    only_vip: monitor.rules.only_vip,
  });
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const coinKeys = Object.keys(coins).sort();
  const selected = form.coin ? coins[form.coin] : undefined;

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setStatus(null);
    setBusy(true);
    try {
      const updated = await api.updateRules(monitor.id, { ...form, name });
      onSaved(updated);
      setStatus("Guardado.");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al guardar");
    } finally {
      setBusy(false);
    }
  };

  const onDelete = async () => {
    if (!confirm(`¿Eliminar el monitor "${monitor.name}"?`)) return;
    setBusy(true);
    try {
      await api.deleteMonitor(monitor.id);
      onDeleted(monitor.id);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Error al eliminar");
      setBusy(false);
    }
  };

  return (
    <form className="card rule-card" onSubmit={onSubmit}>
      <div className="rule-card-head">
        <input
          className="name-input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Nombre del monitor"
          aria-label="Nombre del monitor"
        />
        <span className={`badge ${monitor.enabled ? "on" : "off"}`}>
          {monitor.enabled ? "ACTIVO" : "DETENIDO"}
        </span>
      </div>

      <div className="form-grid">
        <label>
          Tipo de oferta
          <select
            value={form.target_type}
            onChange={(e) =>
              setForm({ ...form, target_type: e.target.value as OfferType })
            }
          >
            <option value="any">Cualquiera</option>
            <option value="buy">Compra (buy)</option>
            <option value="sell">Venta (sell)</option>
          </select>
        </label>

        <label>
          Intervalo (segundos)
          <input
            type="number"
            min={5}
            value={form.poll_interval_seconds}
            onChange={(e) =>
              setForm({
                ...form,
                poll_interval_seconds: Number(e.target.value) || 5,
              })
            }
          />
        </label>

        <label>
          Moneda
          <select
            value={form.coin ?? ""}
            onChange={(e) => setForm({ ...form, coin: e.target.value || null })}
          >
            <option value="">Cualquiera</option>
            {coinKeys.map((key) => (
              <option key={key} value={key}>
                {key}
                {coins[key]?.name && coins[key].name !== key
                  ? ` — ${coins[key].name}`
                  : ""}
              </option>
            ))}
          </select>
        </label>

        <div className="ratio-panel">
          <div className="ratio-panel-head">
            Ratio promedio actual
            {form.coin ? <> · <span className="coin">{form.coin}</span></> : ""}
          </div>
          {selected ? (
            <div className="ratio-stats">
              <div className="ratio-stat primary">
                <span className="rp-label">Promedio</span>
                <span className="rp-value">{selected.average?.toFixed(4) ?? "—"}</span>
              </div>
              <div className="ratio-stat">
                <span className="rp-label">Compra</span>
                <span className="rp-value">
                  {selected.average_buy?.toFixed(4) ?? "—"}
                </span>
              </div>
              <div className="ratio-stat">
                <span className="rp-label">Venta</span>
                <span className="rp-value">
                  {selected.average_sell?.toFixed(4) ?? "—"}
                </span>
              </div>
            </div>
          ) : (
            <div className="ratio-empty">
              Selecciona una moneda para ver su ratio de cambio promedio.
            </div>
          )}
        </div>
      </div>

      <div className="pair-grid">
        <label>
          Ratio mínimo
          <input
            type="number"
            step="any"
            value={form.min_ratio ?? ""}
            onChange={(e) =>
              setForm({ ...form, min_ratio: numOrNull(e.target.value) })
            }
          />
        </label>
        <label>
          Ratio máximo
          <input
            type="number"
            step="any"
            value={form.max_ratio ?? ""}
            onChange={(e) =>
              setForm({ ...form, max_ratio: numOrNull(e.target.value) })
            }
          />
        </label>
      </div>

      <div className="pair-grid">
        <label>
          Monto mínimo
          <input
            type="number"
            step="any"
            value={form.min_amount ?? ""}
            onChange={(e) =>
              setForm({ ...form, min_amount: numOrNull(e.target.value) })
            }
          />
        </label>
        <label>
          Monto máximo
          <input
            type="number"
            step="any"
            value={form.max_amount ?? ""}
            onChange={(e) =>
              setForm({ ...form, max_amount: numOrNull(e.target.value) })
            }
          />
        </label>
      </div>

      <div className="checks">
        <label className="check">
          <input
            type="checkbox"
            checked={form.only_kyc}
            onChange={(e) => setForm({ ...form, only_kyc: e.target.checked })}
          />
          Solo KYC
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={form.only_vip}
            onChange={(e) => setForm({ ...form, only_vip: e.target.checked })}
          />
          Solo VIP
        </label>
      </div>

      <div className="policy">
        <div className="policy-head">Política de aplicación</div>
        <div className="pair-grid">
          <label>
            Prioridad de selección
            <select
              value={form.selection_strategy}
              onChange={(e) =>
                setForm({
                  ...form,
                  selection_strategy: e.target.value as SelectionStrategy,
                })
              }
            >
              <option value="best_ratio">Mejor ratio</option>
              <option value="amount_high">Mayor monto</option>
              <option value="amount_low">Menor monto</option>
              <option value="oldest">Más antigua</option>
              <option value="newest">Más reciente</option>
            </select>
          </label>
          <label>
            Aplicaciones por ciclo
            <select
              value={form.apply_mode}
              onChange={(e) =>
                setForm({ ...form, apply_mode: e.target.value as ApplyMode })
              }
            >
              <option value="single">Una (la mejor)</option>
              <option value="multiple">Varias (hasta agotar saldo)</option>
            </select>
          </label>
        </div>
        <p className="muted small" style={{ margin: "0.4rem 0 0" }}>
          {form.apply_mode === "multiple"
            ? "Aplica varias ofertas por ciclo en orden de prioridad, hasta agotar el saldo (compra) o el límite de ritmo."
            : "Aplica solo la mejor oferta según la prioridad elegida en cada ciclo."}
        </p>
      </div>

      {error && <div className="alert alert-error">{error}</div>}
      {status && <div className="alert alert-ok">{status}</div>}

      <div className="rule-card-actions">
        <button className="btn btn-primary" type="submit" disabled={busy}>
          {busy ? "Guardando…" : "Guardar"}
        </button>
        <button
          className="btn btn-danger"
          type="button"
          onClick={onDelete}
          disabled={busy}
        >
          Eliminar
        </button>
      </div>
    </form>
  );
}
