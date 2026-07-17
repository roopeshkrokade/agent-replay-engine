import React, { useState } from "react";
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
  highlight?: boolean;
  italic?: boolean;
}

const mockLogs: LogEntry[] = [
  {
    timestamp: "10:42:01.034",
    level: "SYSTEM",
    message: "Initializing Agent Replay Engine v5.2.4...",
  },
  {
    timestamp: "10:42:01.442",
    level: "KERNEL",
    message: "Mounting virtual workspace: /agents/cs-bot-v5",
  },
  {
    timestamp: "10:42:01.890",
    level: "MODEL",
    message: "Handshake with LLM provider successful. Latency: 42ms",
    italic: true,
  },
  {
    timestamp: "10:42:02.102",
    level: "EVENT",
    message: 'User Input Received: "Where is my order #5521?"',
    highlight: true,
  },
  {
    timestamp: "10:42:02.315",
    level: "MODEL",
    message:
      "Thought Process: Checking database for order ID 5521. Cross-referencing with customer ID 883.",
  },
  {
    timestamp: "10:42:03.112",
    level: "DATABASE",
    message: "Query OK: Row fetched in 12ms. Status: SHIPPED.",
  },
  {
    timestamp: "10:42:03.400",
    level: "EVENT",
    message:
      'Agent Response Generated: "Your order #5521 was shipped on Tuesday..."',
  },
];

const versionList = [
  { name: "v5.2.4-stable", status: "healthy", selected: true },
  { name: "v5.1.0-rc", status: "warning", selected: false },
  { name: "v4.8.9", status: "inactive", selected: false },
  { name: "v4.8.8", status: "inactive", selected: false },
  { name: "v4.7.2", status: "error", selected: false },
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

  const agentName = agentId
    ? decodeURIComponent(agentId)
    : "Customer Support Bot";
  const playheadPct = (currentTime / maxTime) * 100;

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
              {versionList.map((version) => (
                <div
                  key={version.name}
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
                  <div
                    className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${getStatusColor(
                      version.status,
                    )}`}
                  ></div>
                </div>
              ))}
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
              <button className="flex items-center gap-1.5 px-3 py-2 bg-amber-500 hover:bg-amber-600 text-slate-950 font-bold rounded-lg text-xs sm:text-sm transition-colors whitespace-nowrap">
                <Play className="w-3.5 h-3.5 fill-current" /> Replay
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
              <div className="flex bg-slate-950 border border-slate-700 rounded-lg gap-1 p-1">
                <button className="px-2.5 sm:px-3 py-1 bg-amber-500 text-slate-950 font-bold text-xs rounded-md transition-colors">
                  Live
                </button>
                <button className="px-2.5 sm:px-3 py-1 text-slate-400 text-xs hover:text-slate-200 transition-colors">
                  Cache
                </button>
              </div>
              <div className="flex items-center gap-2 px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-xs font-mono">
                <CreditCard className="w-3.5 h-3.5 text-slate-500" />
                <span className="text-slate-300">$0.00</span>
              </div>
            </div>
          </div>

          {/* Log Viewer */}
          <div className="flex-1 overflow-y-auto p-3 sm:p-4 font-mono text-xs sm:text-sm">
            <div className="space-y-1">
              {mockLogs.map((log, idx) => (
                <div
                  key={idx}
                  className={`flex flex-col sm:flex-row gap-1 sm:gap-4 ${
                    log.highlight
                      ? "bg-red-950/20 px-2 py-1.5 rounded"
                      : "px-1 py-1 sm:px-0 sm:py-0"
                  }`}
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
