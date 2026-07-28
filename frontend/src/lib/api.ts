import type {
  CoinsMap,
  CycleReport,
  History,
  MonitorState,
  MonitorsResponse,
  OfferEvaluation,
  OfferType,
  Profile,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers ?? {}) },
    ...options,
  });
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = body.detail ?? detail;
    } catch {
      // sin cuerpo JSON
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

export interface LoginPayload {
  email: string;
  password: string;
  two_factor_code?: string;
}

export interface RulesPayload {
  name?: string;
  target_type: OfferType;
  poll_interval_seconds: number;
  coin: string | null;
  min_ratio: number | null;
  max_ratio: number | null;
  min_amount: number | null;
  max_amount: number | null;
  only_kyc: boolean;
  only_vip: boolean;
}

export const api = {
  login: (payload: LoginPayload) =>
    request<Profile>("/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  logout: () => request<{ ok: boolean }>("/auth/logout", { method: "POST" }),
  me: () => request<Profile>("/auth/me"),

  listMonitors: () => request<MonitorsResponse>("/monitors"),
  createMonitor: (name: string) =>
    request<MonitorState>("/monitors", {
      method: "POST",
      body: JSON.stringify({ name }),
    }),
  updateRules: (monitorId: string, payload: RulesPayload) =>
    request<MonitorState>(`/monitors/${monitorId}/rules`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  deleteMonitor: (monitorId: string) =>
    request<{ ok: boolean }>(`/monitors/${monitorId}`, { method: "DELETE" }),
  startMonitor: (monitorId: string) =>
    request<MonitorState>(`/monitors/${monitorId}/start`, { method: "POST" }),
  stopMonitor: (monitorId: string) =>
    request<MonitorState>(`/monitors/${monitorId}/stop`, { method: "POST" }),
  testCycle: (monitorId: string) =>
    request<CycleReport>(`/monitors/${monitorId}/test`, { method: "POST" }),

  getHistory: (monitorId: string) =>
    request<History>(`/monitors/${monitorId}/history`),
  getOffers: (monitorId: string) =>
    request<{ offers: OfferEvaluation[]; error?: string }>(
      `/monitors/${monitorId}/offers`,
    ),
  getCoins: () => request<{ coins: CoinsMap }>("/coins"),
  getBalance: () => request<{ balance: number | null }>("/balance"),
};
