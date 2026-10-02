import React, { useState, useEffect, useRef } from "react";
import { useParams } from "react-router-dom";
import {
  Play,
  Square,
  RotateCw,
  AlignJustify,
  Search,
  ChevronDown,
  CreditCard,
  Gauge,
  Cpu,
  Menu,
  X,
} from "lucide-react";
import {
  fetchAgentVersions,
  replayRecord,
  type MatchMode,
  type ReplayResult,
} from "../services/api.services";
import ReplayReport from "../components/workspace/ReplayReport";

import { AnsiUp } from "ansi_up";
import DOMPurify from "dompurify";

// Small route/waypoint glyph used next to each version — a custom SVG
// since it needs to closely match a specific mark rather than a stock icon.
const VersionIcon = ({ className = "" }: { className?: string }) => (
  <svg
    viewBox="0 0 16 16"
    fill="none"
    className={className}
    xmlns="http://www.w3.org/2000/svg"
  >
    <circle cx="4" cy="4" r="1.6" stroke="currentColor" strokeWidth="1.3" />
    <path
      d="M4 5.6C4 9 5 10 8 11.5"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
    />
    <circle
      cx="10.5"
      cy="12.3"
      r="1.6"
      stroke="currentColor"
      strokeWidth="1.3"
    />
  </svg>
);

interface LogEntry {
  timestamp: string;
  level: "SYSTEM" | "KERNEL" | "MODEL" | "EVENT" | "DATABASE" | "ERROR";
  message: string;
  html?: string;
  highlight?: boolean;
  italic?: boolean;
  id?: string;
  mounted?: boolean;
}

const mockLogs: LogEntry[] = [];

const versionList = [
  { name: "v5.2.4-stable", status: "healthy", selected: true },
];

const getLevelColor = (level: string) => {
  switch (level) {
    case "SYSTEM":
      return "text-slate-400 border-slate-600";
    case "KERNEL":
      return "text-orange-400 border-orange-400/40";
    case "MODEL":
      return "text-slate-400 border-slate-600";
    case "EVENT":
      return "text-amber-500 border-amber-500/40";
    case "DATABASE":
      return "text-blue-400 border-blue-400/40";
    case "ERROR":
      return "text-red-400 border-red-400/40";
    default:
      return "text-slate-400 border-slate-600";
  }
};

const getStatusColor = (status: string) => {
  switch (status) {
    case "healthy":
      return "bg-green-500";
    case "warning":
      return "bg-yellow-500";
    case "error":
      return "bg-red-500";
    case "inactive":
      return "bg-slate-600";
    default:
      return "bg-slate-600";
  }
};

// Renders a log message, highlighting quoted text and file paths in amber
const renderMessage = (log: LogEntry) => {
  if (log.html) {
    return (
      <span
        className={log.italic ? "italic text-slate-400" : "text-slate-200"}
        dangerouslySetInnerHTML={{ __html: log.html }}
      />
    );
  }
  const parts = log.message.split(/("(?:[^"]*)"|\/[a-zA-Z0-9\-_/.]+)/g);
  return (
    <span className={log.italic ? "italic text-slate-400" : "text-slate-200"}>
      {parts.map((part, i) => {
        const isQuoted = /^".*"$/.test(part);
        const isPath = /^\//.test(part);
        if (isQuoted || isPath) {
          return (
            <span key={i} className="text-amber-500">
              {part}
            </span>
          );
        }
        return <span key={i}>{part}</span>;
      })}
    </span>
  );
};

export default function AgentWorkspace() {
  const { agentId } = useParams<{ agentId: string }>();
  const [versions, setVersions] = useState(() => versionList as any[]);
  const [versionsLoading, setVersionsLoading] = useState(false);
  const [versionsError, setVersionsError] = useState<string | null>(null);
  const [replayingRecordId, setReplayingRecordId] = useState<string | null>(
    null,
  );
  const [replayResult, setReplayResult] = useState<ReplayResult | null>(null);
  const [replayError, setReplayError] = useState<string | null>(null);
  const [matchMode, setMatchMode] = useState<MatchMode>("RELAXED");
  const [faultStep, setFaultStep] = useState<string>("");
  const [faultPersistent, setFaultPersistent] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>(mockLogs);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const logsContainerRef = useRef<HTMLDivElement | null>(null);
  const [currentTime, setCurrentTime] = useState(4.2);
  const [isPlaying, setIsPlaying] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const maxTime = 4.2;

  const formatTimecode = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.round((seconds % 1) * 1000);
    return `${String(mins).padStart(2, "0")}:${String(secs).padStart(
      2,
      "0",
    )}:${String(ms).padStart(2, "0").slice(0, 2)}`;
  };

  // Parse an API error message like "API error 400: { ... }" and extract a concise summary and expected/got fields
  const parseApiError = (msg: string) => {
    const out: { summary: string; expected?: string; got?: string } = {
      summary: msg,
    };
    try {
      // status code if present
      const statusMatch = String(msg).match(/^API error\s*(\d+):/);
      const status = statusMatch ? statusMatch[1] : null;

      // find JSON part
      const firstBrace = msg.indexOf("{");
      const jsonPart = firstBrace >= 0 ? msg.slice(firstBrace) : null;
      let body: any = null;
      if (jsonPart) {
        try {
          body = JSON.parse(jsonPart);
        } catch (e) {
          // ignore
        }
      }

      const detailText =
        body?.detail && typeof body.detail === "string"
          ? body.detail
          : body || msg;

      // extract Expected / got if present
      const expMatch = String(detailText).match(
        /Expected\s+([\s\S]*?)\s*,\s*got/,
      );
      if (expMatch && expMatch[1]) {
        // try to clean up single quotes
        const cleaned = expMatch[1]
          .replace(/None/g, "null")
          .replace(/True/g, "true")
          .replace(/False/g, "false")
          .replace(/'/g, '"');
        try {
          const parsed = JSON.parse(cleaned);
          out.expected = JSON.stringify(parsed, null, 2);
        } catch (e) {
          out.expected = expMatch[1].trim();
        }
      }

      const gotMatch = String(detailText).match(/got\s+([\s\S]*?)$/);
      if (gotMatch && gotMatch[1]) {
        const cleaned = gotMatch[1]
          .trim()
          .replace(/None/g, "null")
          .replace(/True/g, "true")
          .replace(/False/g, "false")
          .replace(/'/g, '"');
        try {
          const parsed = JSON.parse(cleaned);
          out.got = JSON.stringify(parsed, null, 2);
        } catch (e) {
          out.got = gotMatch[1].trim();
        }
      }

      // compose summary
      if (status && typeof detailText === "string") {
        const oneLine = String(detailText).split("\n")[0];
        out.summary = `API error ${status}: ${oneLine}`;
      } else if (body && body.detail) {
        out.summary = String(body.detail).split("\n")[0];
      }
    } catch (e) {
      out.summary = msg;
    }
    return out;
  };

  // Helper to append a properly-typed LogEntry
  const ansiUp = new AnsiUp();
  const addLog = (level: LogEntry["level"], message: string, html?: string) => {
    const now = new Date();
    const ts =
      now.toTimeString().split(" ")[0] +
      "." +
      String(now.getMilliseconds()).padStart(3, "0");
    const id = `${Date.now()}-${Math.floor(Math.random() * 100000)}`;
    const entry: LogEntry = {
      id,
      mounted: false,
      timestamp: ts,
      level,
      message,
      html,
    };
    setLogs((s) => [...s, entry]);
    // trigger mount animation on next tick
    setTimeout(() => {
      setLogs((s) => s.map((l) => (l.id === id ? { ...l, mounted: true } : l)));
    }, 20);
  };

  const stripAnsi = (s: string) => {
    return s.replace(/\x1B\[[0-9;]*[A-Za-z]/g, "");
  };

  // Streaming log reveal: schedule lines to appear one-by-one with animation
  const streamIdRef = React.useRef(0);
  const sleep = (ms: number) => new Promise((res) => setTimeout(res, ms));

  const streamLogs = async (
    level: LogEntry["level"],
    raw: string | undefined,
  ) => {
    if (!raw) return;
    const rawStr = String(raw);
    const lines = rawStr.split(/\r?\n/).filter((l) => stripAnsi(l).trim());
    if (!lines.length) return;
    const myStream = ++streamIdRef.current;

    for (let i = 0; i < lines.length; i++) {
      // stop if a new stream started
      if (myStream !== streamIdRef.current) return;
      const line = lines[i];
      const plain = stripAnsi(line).trim();
      try {
        const html = ansiUp.ansi_to_html(line);
        const safe = DOMPurify.sanitize(html);
        addLog(level, plain, safe);
      } catch (e) {
        addLog(level, plain);
      }
      // after adding a log, if auto-scroll is enabled, scroll to bottom smoothly
      if (autoScrollEnabled && logsContainerRef.current) {
        try {
          logsContainerRef.current.scrollTo({
            top: logsContainerRef.current.scrollHeight,
            behavior: "smooth",
          });
        } catch (e) {
          logsContainerRef.current.scrollTop =
            logsContainerRef.current.scrollHeight;
        }
      }
      // delay between entries (slightly variable for natural feel)
      const delay = 25 + Math.min(200, 8 * String(plain).length);
      await sleep(delay);
    }
  };

  const runReplay = async (recordId: string) => {
    setReplayResult(null);
    setReplayError(null);
    setLogs([]); // clear previous logs for a fresh replay stream
    setReplayingRecordId(recordId);
    const step = parseInt(faultStep, 10);
    const faults =
      Number.isFinite(step) && step > 0
        ? [{ step, status: faultPersistent ? 500 : 503, persistent: faultPersistent }]
        : [];
    let res: ReplayResult;
    try {
      res = await replayRecord(recordId, { match: matchMode, faults });
    } catch (err: any) {
      const msg = err?.message || String(err);
      setReplayError(msg);
      addLog("ERROR", parseApiError(msg).summary);
      return;
    } finally {
      // The replay is over once the response arrives; the log animation below is presentation only.
      setReplayingRecordId(null);
    }
    setReplayResult(res);
    await streamLogs(res.status === "success" ? "SYSTEM" : "ERROR", res.logs || res.message);
  };

  const selectedRecordId = versions.find((v) => v.selected)?.recordId ?? versions.find((v) => v.recordId)?.recordId;

  const agentName = agentId
    ? decodeURIComponent(agentId)
    : "Customer Support Bot";
  const playheadPct = (currentTime / maxTime) * 100;

  // Load versions for the selected agent
  React.useEffect(() => {
    if (!agentId) return;
    const id = agentId; // capture non-null agentId for the async loader
    const ac = new AbortController();
    async function load() {
      setVersionsLoading(true);
      setVersionsError(null);
      try {
        const data = await fetchAgentVersions(id, ac.signal);
        // map to UI shape
        const mapped = (data || []).map((v: any, i: number) => ({
          name: v.version ? `v${v.version}` : v.record_id || `v${i}`,
          status: v.last_execution_timestamp ? "healthy" : "inactive",
          selected: i === 0,
          recordId: v.record_id,
          createdAt: v.created_at,
        }));
        setVersions(mapped);
      } catch (err: any) {
        if (err.name !== "AbortError")
          setVersionsError(err.message || String(err));
      } finally {
        setVersionsLoading(false);
      }
    }
    load();
    return () => ac.abort();
  }, [agentId]);

  // Auto-scroll when logs change if enabled
  useEffect(() => {
    if (!autoScrollEnabled) return;
    const c = logsContainerRef.current;
    if (!c) return;
    try {
      c.scrollTo({ top: c.scrollHeight, behavior: "smooth" });
    } catch (e) {
      c.scrollTop = c.scrollHeight;
    }
  }, [logs, autoScrollEnabled]);

  return (
    <div className="flex flex-col h-full">
      <div className="relative flex flex-1 min-h-0 bg-slate-950 overflow-hidden">
        {/* Mobile top bar */}
        <div className="lg:hidden absolute top-0 left-0 right-0 z-30 flex items-center gap-3 bg-slate-900 border-b border-slate-800 px-3 py-2.5">
          <button
            onClick={() => setSidebarOpen(true)}
            aria-label="Open versions menu"
            className="p-1.5 -ml-1 text-slate-300 hover:text-slate-100"
          >
            <Menu className="w-5 h-5" />
          </button>
          <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider truncate">
            {agentName}
          </h3>
        </div>

        {sidebarOpen && (
          <div
            className="lg:hidden fixed inset-0 bg-black/60 z-40"
            onClick={() => setSidebarOpen(false)}
          />
        )}

        {/* Left Sidebar */}
        <div
          className={`
            fixed lg:static inset-y-0 left-0 z-50
            w-72 sm:w-64 max-w-[85vw]
            bg-slate-900 border-r border-slate-800 flex flex-col
            transform transition-transform duration-200 ease-out
            ${sidebarOpen ? "translate-x-0" : "-translate-x-full"} lg:translate-x-0
          `}
        >
          <div className="border-b border-slate-800 p-4 flex items-start justify-between gap-2">
            <div className="min-w-0">
              <button className="flex items-center gap-1 text-sm font-bold text-slate-100 uppercase tracking-wider hover:text-amber-500 transition-colors max-w-full">
                <span className="truncate">{agentName}</span>
                <ChevronDown className="w-4 h-4 text-slate-500 flex-shrink-0" />
              </button>
              <div className="flex items-center gap-2 text-xs font-semibold text-slate-500 mt-2.5">
                <div className="w-2 h-2 rounded-full bg-green-500 flex-shrink-0"></div>
                <span className="truncate">ACTIVE DEPLOYMENT</span>
              </div>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              aria-label="Close versions menu"
              className="lg:hidden p-1 text-slate-400 hover:text-slate-200 flex-shrink-0"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-2">
            <div className="text-xs font-bold text-slate-600 uppercase tracking-wider px-3 py-2 mb-1">
              Versions
            </div>
            <div className="space-y-0.5">
              {versionsLoading ? (
                <div className="px-3 py-2 text-sm text-slate-400">
                  Loading versions...
                </div>
              ) : versionsError ? (
                <div className="px-3 py-2 text-sm text-red-400">
                  Error: {versionsError}
                </div>
              ) : (
                versions.map((version) => (
                  <div
                    key={version.name}
                    onClick={() =>
                      setVersions((vs) => vs.map((v) => ({ ...v, selected: v.name === version.name })))
                    }
                    className={`flex items-center gap-2 px-3 py-2.5 rounded-lg text-sm font-mono border-l-2 ${
                      version.selected
                        ? "bg-slate-800 border-amber-500"
                        : "border-transparent hover:bg-slate-800/50 cursor-pointer"
                    }`}
                  >
                    <VersionIcon className="w-3.5 h-3.5 text-slate-600 flex-shrink-0" />
                    <span className="text-slate-300 flex-1 truncate">
                      {version.name}
                    </span>
                    <div className="flex items-center gap-2">
                      {version.recordId ? (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            runReplay(version.recordId);
                          }}
                          disabled={replayingRecordId !== null}
                          className="px-2 py-1 text-xs bg-amber-600 text-slate-900 rounded disabled:opacity-50"
                        >
                          {replayingRecordId === version.recordId
                            ? "Replaying..."
                            : "Replay"}
                        </button>
                      ) : null}
                      <div
                        className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${getStatusColor(version.status)}`}
                      ></div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="border-t border-slate-800 p-4">
            <button className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 text-sm font-medium hover:bg-slate-700 transition-colors">
              + New Version
            </button>
          </div>
        </div>

        {/* Main Content Area */}
        <div className="flex-1 min-w-0 bg-slate-950 flex flex-col pt-12 lg:pt-0">
          {/* Workspace Toolbar */}
          <div className="border-b border-slate-800 px-3 sm:px-4 py-3 flex flex-wrap items-center gap-y-2 gap-x-3 justify-between">
            <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
              <button
                onClick={() => selectedRecordId && runReplay(selectedRecordId)}
                disabled={!selectedRecordId || replayingRecordId !== null}
                title={selectedRecordId ? `Replay ${selectedRecordId}` : "Select a version to replay"}
                className="flex items-center gap-1.5 px-3 py-2 bg-amber-500 hover:bg-amber-600 disabled:opacity-50 disabled:hover:bg-amber-500 text-slate-950 font-bold rounded-lg text-xs sm:text-sm transition-colors whitespace-nowrap"
              >
                <Play className="w-3.5 h-3.5 fill-current" /> {replayingRecordId ? "Replaying..." : "Replay"}
              </button>
              <button className="p-2 text-slate-500 hover:text-slate-200 transition-colors">
                <Square className="w-4 h-4" />
              </button>
              <button className="p-2 text-slate-500 hover:text-slate-200 transition-colors">
                <RotateCw className="w-4 h-4" />
              </button>
              <div className="hidden sm:block w-px h-6 bg-slate-800"></div>
              <button className="p-2 text-slate-500 hover:text-slate-200 transition-colors">
                <AlignJustify className="w-4 h-4" />
              </button>
              <button className="p-2 text-slate-500 hover:text-slate-200 transition-colors">
                <Search className="w-4 h-4" />
              </button>
            </div>
            <div className="flex items-center gap-2 sm:gap-4 flex-wrap">
              <div
                className="flex bg-slate-950 border border-slate-700 rounded-lg gap-1 p-1"
                role="group"
                aria-label="Request matching"
              >
                {(["RELAXED", "STRICT"] as MatchMode[]).map((mode) => (
                  <button
                    key={mode}
                    onClick={() => setMatchMode(mode)}
                    aria-pressed={matchMode === mode}
                    title={
                      mode === "RELAXED"
                        ? "Serve the matching (else next) recorded call; report differences"
                        : "Fail if a request differs from the recording"
                    }
                    className={`px-2.5 sm:px-3 py-1 text-xs rounded-md transition-colors ${
                      matchMode === mode
                        ? "bg-amber-500 text-slate-950 font-bold"
                        : "text-slate-400 hover:text-slate-200"
                    }`}
                  >
                    {mode === "RELAXED" ? "Relaxed" : "Strict"}
                  </button>
                ))}
              </div>
              <label
                className="flex items-center gap-2 px-2 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-400"
                title="Inject a provider failure on this model call (1-based)"
              >
                Fault @
                <input
                  type="number"
                  min={1}
                  value={faultStep}
                  onChange={(e) => setFaultStep(e.target.value)}
                  placeholder="—"
                  aria-label="Fault on call number"
                  className="w-12 bg-slate-950 border border-slate-700 rounded px-1.5 py-0.5 font-mono text-slate-200"
                />
                <select
                  value={faultPersistent ? "always" : "once"}
                  onChange={(e) => setFaultPersistent(e.target.value === "always")}
                  aria-label="Fault mode"
                  className="bg-slate-950 border border-slate-700 rounded px-1 py-0.5 text-slate-200"
                >
                  <option value="once">once (503)</option>
                  <option value="always">always (500)</option>
                </select>
              </label>
              <div className="flex items-center gap-2 px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs font-mono">
                <CreditCard className="w-3.5 h-3.5 text-slate-500" />
                <span className="text-slate-300">$0.00</span>
              </div>
            </div>
          </div>

          {replayResult ? (
            <ReplayReport result={replayResult} onClose={() => setReplayResult(null)} />
          ) : replayError ? (
            <div className="border-b border-red-900 bg-red-950/30 px-3 sm:px-4 py-3 text-sm text-red-300">
              {parseApiError(replayError).summary}
            </div>
          ) : null}

          {/* Log Viewer */}
          <div
            ref={logsContainerRef}
            onScroll={(e) => {
              const el = e.currentTarget as HTMLDivElement;
              const distanceFromBottom =
                el.scrollHeight - el.scrollTop - el.clientHeight;
              // if user scrolled away more than 60px, pause auto-scroll
              if (distanceFromBottom > 60) {
                setAutoScrollEnabled(false);
              } else {
                setAutoScrollEnabled(true);
              }
            }}
            className="flex-1 overflow-y-auto p-3 sm:p-4 font-mono text-xs sm:text-sm relative"
          >
            {!autoScrollEnabled ? (
              <div className="absolute top-2 right-4 z-20">
                <button
                  onClick={() => {
                    const c = logsContainerRef.current;
                    if (!c) return;
                    try {
                      c.scrollTo({ top: c.scrollHeight, behavior: "smooth" });
                    } catch (e) {
                      c.scrollTop = c.scrollHeight;
                    }
                    setAutoScrollEnabled(true);
                  }}
                  className="px-2 py-1 bg-slate-800/80 text-slate-200 rounded text-xs border border-slate-700"
                >
                  Jump to latest
                </button>
              </div>
            ) : null}
            <div className="space-y-1">
              {logs.map((log, idx) => (
                <div
                  key={log.id ?? idx}
                  className={`flex flex-col sm:flex-row gap-1 sm:gap-4 ${
                    log.highlight
                      ? "bg-red-950/20 px-2 py-1.5 rounded"
                      : "px-1 py-1 sm:px-0 sm:py-0"
                  } ${log.mounted ? "opacity-100 translate-y-0" : "opacity-0 -translate-y-1"} transition-all duration-300 ease-out`}
                >
                  <div className="flex items-center gap-2 sm:contents">
                    <span className="text-slate-600 flex-shrink-0 sm:min-w-fit">
                      {log.timestamp}
                    </span>
                    <div
                      className={`px-2 py-0.5 rounded border text-[10px] sm:text-xs font-semibold flex-shrink-0 ${getLevelColor(
                        log.level,
                      )}`}
                    >
                      {log.level}
                    </div>
                  </div>
                  <span className="flex-1 break-words">
                    {renderMessage(log)}
                  </span>
                </div>
              ))}
              {/* live cursor row */}
              <div className="flex items-end gap-2 sm:gap-4 px-1 sm:px-0 pt-1">
                <span className="text-slate-600 flex-shrink-0">
                  10:42:04.001
                </span>
                <span className="w-2.5 h-0.5 bg-amber-500 mb-0.5 animate-pulse"></span>
              </div>
            </div>
          </div>

          {/* Timeline / Status Bar */}
          <div className="border-t border-slate-800 bg-slate-900/30 p-3 sm:p-4 space-y-3">
            <div className="flex justify-end">
              <div className="flex items-center gap-2 bg-slate-800/80 border border-slate-700 rounded-full px-3 py-1.5 text-xs font-semibold text-amber-500">
                <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse"></span>
                STREAMING LOGS
              </div>
            </div>

            <div className="flex items-center gap-3">
              <span className="text-xs font-mono text-slate-500 flex-shrink-0">
                00:00:00
              </span>
              <div className="flex-1 relative h-6 flex items-center">
                <div className="w-full h-px bg-slate-700 relative">
                  <div
                    className="absolute top-0 left-0 h-px bg-amber-500"
                    style={{ width: `${playheadPct}%` }}
                  ></div>
                  <div
                    className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-amber-500 ring-2 ring-slate-950"
                    style={{ left: "38%" }}
                  ></div>
                  <div
                    className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-2 h-2 rounded-full bg-slate-500 ring-2 ring-slate-950"
                    style={{ left: "78%" }}
                  ></div>
                </div>
                <div
                  className="absolute top-1/2 -translate-x-1/2 flex flex-col items-center"
                  style={{ left: `${playheadPct}%` }}
                >
                  <div className="w-2.5 h-2.5 bg-white rotate-45 -translate-y-3"></div>
                  <div className="w-px h-6 bg-white/50 -translate-y-3"></div>
                </div>
              </div>
              <span className="text-xs font-mono text-slate-500 flex-shrink-0">
                {formatTimecode(maxTime)}
              </span>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-[10px] sm:text-[11px] font-mono text-slate-500">
              <div className="flex items-center gap-4">
                <span className="flex items-center gap-1.5">
                  <Gauge className="w-3 h-3" /> 1.0x PLAYBACK
                </span>
                <span className="flex items-center gap-1.5">
                  <Cpu className="w-3 h-3" /> GPU-0: 42%
                </span>
              </div>
              <div className="flex items-center gap-4">
                <span>AUTO-SCROLL ENABLED</span>
                <span>FRAMES: 1,204</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
