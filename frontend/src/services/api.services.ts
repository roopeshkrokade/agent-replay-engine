// Centralized API endpoints and helpers
const API_BASE = (import.meta.env && import.meta.env.VITE_API_BASE) || "";
const TOKEN_KEY = "agentReplayToken";

export const endpoints = {
  agents: `${API_BASE}/api/agents`,
  runs: `${API_BASE}/api/runs`,
};

export type MatchMode = "RELAXED" | "STRICT";

export interface Fault {
  step: number;
  status?: number;
  persistent?: boolean;
}

export interface ReplayOptions {
  match?: MatchMode;
  faults?: Fault[];
}

export interface Divergence {
  type: string;
  severity: "error" | "warning";
  reason: string;
  step?: number;
  tool_step?: number;
  tool?: string;
  api?: string;
  expected?: unknown;
  got?: unknown;
}

export interface ReplayEvent {
  type: "served" | "fault_injected" | "replayed_error";
  step: number;
  status?: number;
  api?: string;
  node_id?: string;
}

export interface ReplayReport {
  match: MatchMode;
  served_steps: number;
  total_steps: number;
  complete: boolean;
  tool_check: string;
  events: ReplayEvent[];
  divergences: Divergence[];
}

export interface ReplayResult {
  status: "success" | "error";
  message: string;
  logs: string;
  divergences: Divergence[];
  report: ReplayReport;
}

function authHeaders(): Record<string, string> {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

// A server started with AGENT_REPLAY_TOKEN answers 401; ask once for the token and retry.
async function request<T>(url: string, init: RequestInit = {}, retried = false): Promise<T> {
  const res = await fetch(url, {
    ...init,
    headers: { accept: "application/json", ...(init.headers || {}), ...authHeaders() },
  });
  if (res.status === 401 && !retried) {
    const token = window.prompt("This Agent Replay server requires its access token (AGENT_REPLAY_TOKEN):");
    if (token) {
      try {
        localStorage.setItem(TOKEN_KEY, token.trim());
      } catch {
        // storage unavailable: the token is only used for this retry
        return request<T>(url, { ...init, headers: { ...(init.headers || {}), Authorization: `Bearer ${token.trim()}` } }, true);
      }
      return request<T>(url, init, true);
    }
  }
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${txt}`);
  }
  return res.json();
}

export async function fetchAgents(signal?: AbortSignal) {
  return request<any[]>(endpoints.agents, { method: "GET", signal });
}

export async function fetchAgentVersions(agentId: string, signal?: AbortSignal) {
  return request<any[]>(`${endpoints.agents}/${encodeURIComponent(agentId)}`, { method: "GET", signal });
}

export async function replayRecord(recordId: string, options: ReplayOptions = {}, signal?: AbortSignal) {
  return request<ReplayResult>(`${endpoints.runs}/${encodeURIComponent(recordId)}/replay`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ match: options.match ?? "RELAXED", faults: options.faults ?? [] }),
    signal,
  });
}

export default {
  endpoints,
  fetchAgents,
  fetchAgentVersions,
  replayRecord,
};
