import type { LogEntry } from "./types";

export function subscribeToReplayLogs(
  _agentId: string,
  _versionId: string,
  onMessage: (m: LogEntry) => void,
) {
  // placeholder: server should expose an SSE endpoint
  const interval = setInterval(() => {
    onMessage({
      ts: Date.now(),
      text: "mock log at " + new Date().toISOString(),
    });
  }, 2000);
  return () => clearInterval(interval);
}
