export type OfferType = "buy" | "sell" | "any";

export type SelectionStrategy =
  | "best_ratio"
  | "amount_high"
  | "amount_low"
  | "oldest"
  | "newest";

export type ApplyMode = "single" | "multiple";

export interface Profile {
  uuid: string;
  username: string | null;
  kyc: boolean;
  p2p_enabled: boolean;
  balance: number | null;
  monitor_running?: boolean;
}

export interface Rules {
  coin: string | null;
  min_ratio: number | null;
  max_ratio: number | null;
  min_amount: number | null;
  max_amount: number | null;
  only_kyc: boolean;
  only_vip: boolean;
}

export interface MonitorState {
  id: string;
  name: string;
  enabled: boolean;
  running: boolean;
  poll_interval_seconds: number;
  target_type: OfferType;
  selection_strategy: SelectionStrategy;
  apply_mode: ApplyMode;
  rules: Rules;
  last_error: string | null;
  last_error_at: string | null;
  last_success_at: string | null;
  applied_count: number;
  balance: number | null;
}

export interface MonitorsResponse {
  balance: number | null;
  monitors: MonitorState[];
}

export interface CoinAverage {
  name: string;
  average: number;
  average_buy: number;
  average_sell: number;
  count?: number;
  updated_at?: string;
}

export type CoinsMap = Record<string, CoinAverage>;

export interface Advertiser {
  uuid: string | null;
  username: string | null;
  kyc: boolean;
  vip: boolean;
}

export interface OfferSnapshot {
  uuid: string;
  offer_type: OfferType;
  coin: string;
  amount: number;
  receive: number;
  ratio: number;
  status: string;
  only_kyc: boolean;
  only_vip: boolean;
  created_at: string | null;
  link: string;
  advertiser: Advertiser;
}

export interface HistoryEntry {
  uuid: string;
  status: string;
  coin: string;
  amount: number;
  receive: number;
  ratio: number;
  user_uuid: string | null;
  username: string | null;
  evaluated_at: string;
  first_detected_at: string;
  notified_at: string | null;
  applied_at: string | null;
  result: string | null;
  reason: string | null;
  link: string;
}

export interface History {
  applied: HistoryEntry[];
  lost_race: HistoryEntry[];
  notified: HistoryEntry[];
  filtered: HistoryEntry[];
  discarded: HistoryEntry[];
}

export interface CycleReport {
  read_count: number;
  filtered_count: number;
  discarded_count: number;
  top_discarded_reasons: string[];
  error_message: string | null;
  rate_limited: boolean;
  next_sleep_seconds: number | null;
  applied_rules: Rules | null;
  selected_offer: OfferSnapshot | null;
  matched_entry: HistoryEntry | null;
  final_entry: HistoryEntry | null;
}

export interface MonitorEvent {
  type: string;
  user_id: string;
  at: string;
  data: Record<string, unknown>;
}

export interface OfferEvaluation {
  offer: OfferSnapshot;
  is_eligible: boolean;
  reasons: string[];
}
