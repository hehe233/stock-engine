// 与后端 Pydantic 响应一一对应；新增字段时同步修改并运行类型与协议测试。
export type AssetType = 'stock' | 'etf' | 'index';
export type AnalysisMode = 'rules' | 'api' | 'ollama';
export interface Quote {
  symbol: string;
  name: string;
  sector: string;
  asset_type: AssetType;
  price: number | null;
  change_pct: number | null;
  turnover_pct: number | null;
  volume_ratio: number | null;
  amount_yuan: number | null;
  quote_time: string | null;
}

export interface MarketResponse {
  snapshot_id: string;
  source: string;
  is_demo: boolean;
  asset_type: AssetType;
  as_of: string | null;
  fetched_at: string;
  stale: boolean;
  refresh_interval_seconds: number;
  quotes: Quote[];
  total: number;
  universe_count: number;
  source_time_known_count: number;
  missing_from_previous: string[];
  rejected_count: number;
  coverage_verified: boolean;
  warnings: string[];
}

export interface AnalysisReport {
  research_context: Record<string, unknown>;
  id: string;
  snapshot_id: string;
  symbol: string;
  name: string;
  created_at: string;
  as_of: string | null;
  source: string;
  is_demo: boolean;
  asset_type: AssetType;
  analysis_mode: AnalysisMode;
  score_version: string;
  heat_score: number | null;
  model_name: string | null;
  insight: {
    summary: string;
    observations: { text: string; evidence_ids: string[] }[];
    limitations: string[];
  } | null;
  evidence: Record<string, unknown>;
  summary: string;
  factors: {
    name: string;
    value: number | null;
    points: number | null;
    max_points: number;
    explanation: string;
  }[];
  risks: string[];
  trace: { node: string; title: string; detail: string }[];
}

export interface AnalysisList {
  items: AnalysisReport[];
  total: number;
}

export interface AppConfig {
  market_provider: 'demo' | 'public';
  refresh_interval_seconds: number;
  api_configured: boolean;
  api_models: string[];
  default_model: string;
  ollama_model: string;
}

export interface ModelSettings {
  revision: string | null;
  source: 'saved' | 'environment';
  base_url: string;
  has_api_key: boolean;
  default_model: string;
  models: string[];
  ollama_base_url: string;
  ollama_model: string;
}

export interface ModelSettingsInput {
  revision: string | null;
  base_url: string;
  api_key?: string;
  key_action: 'keep' | 'replace' | 'clear';
  default_model: string;
  models: string[];
  ollama_base_url: string;
  ollama_model: string;
}

export interface ModelProfile extends ModelSettings {
  id: string;
  name: string;
  active: boolean;
}

export interface ModelProfileInput extends ModelSettingsInput {
  name: string;
}

export interface ModelProfileList {
  items: ModelProfile[];
  active_id: string | null;
}

export interface MarketStatus {
  worker_online: boolean;
  session: { code: string; label: string; calendar_verified: boolean };
  collection: Record<
    AssetType,
    {
      status: string;
      updated_at?: string;
      message?: string;
      count?: number;
      source?: string;
      snapshot_id?: string;
    }
  >;
}

export interface ResearchJob {
  id: string;
  snapshot_id: string;
  symbol: string;
  mode: AnalysisMode;
  model_name: string | null;
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  created_at: string;
  updated_at: string;
  attempts: number;
  cancel_requested: boolean;
  error: string | null;
  report_id: string | null;
}

export interface JobEvent {
  id: number;
  kind: string;
  created_at: string;
  payload: {
    message?: string;
    detail?: string;
    node?: string;
    report_id?: string;
    attempt?: number;
    block_id?: string;
    call_id?: string;
    name?: string;
    text?: string;
    arguments?: unknown;
    result?: unknown;
    insight?: PartialInsight;
    patch?: ReportPreview;
  };
}

export interface PartialInsight {
  summary?: string;
  observations?: { text?: string; evidence_ids?: string[] }[];
  limitations?: string[];
}

export interface ReportPreview {
  heat_score?: number | null;
  factors?: AnalysisReport['factors'];
  risks?: string[];
  summary?: string;
  insight?: PartialInsight | null;
}
