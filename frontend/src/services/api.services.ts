// Centralized API endpoints and helpers
const API_BASE = (import.meta.env && import.meta.env.VITE_API_BASE) || "";

export const endpoints = {
  agents: `${API_BASE}/api/agents`,
  runs: `${API_BASE}/api/runs`,
};

export async function fetchAgents(signal?: AbortSignal) {
  const res = await fetch(endpoints.agents, {
    method: "GET",
    headers: { accept: "application/json" },
    signal,
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${txt}`);
  }
  return res.json();
}

export async function fetchAgentVersions(
  agentId: string,
  signal?: AbortSignal,
) {
  const url = `${endpoints.agents}/${encodeURIComponent(agentId)}`;
  const res = await fetch(url, {
    method: "GET",
    headers: { accept: "application/json" },
    signal,
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${txt}`);
  }
  return res.json();
}

export async function replayRecord(recordId: string, signal?: AbortSignal) {
  const url = `${endpoints.runs}/${encodeURIComponent(recordId)}/replay`;
  const res = await fetch(url, {
    method: "POST",
    headers: { accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({}),
    signal,
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${txt}`);
  }
  return res.json();
}

export async function replayRecordWithInput(
  recordId: string,
  input: any,
  signal?: AbortSignal,
) {
  const url = `${endpoints.runs}/${encodeURIComponent(recordId)}/replay`;
  const res = await fetch(url, {
    method: "POST",
    headers: { accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ input }),
    signal,
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${txt}`);
  }
  return res.json();
}

export default {
  endpoints,
  fetchAgents,
  fetchAgentVersions,
  replayRecord,
  replayRecordWithInput,
};
