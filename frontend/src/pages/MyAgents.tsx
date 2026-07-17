import React, { useState } from "react";
import { Link } from "react-router-dom";

interface Agent {
  id: string;
  name: string;
  status: "healthy" | "error" | "inactive";
  timeCreated: string;
  lastExecution: string;
  executionStatus?: "success" | "failed" | "timeout" | "never";
  version: string;
}

const agents: Agent[] = [
  {
    id: "1",
    name: "Data_Scraper_Alpha",
    status: "healthy",
    timeCreated: "Oct 12, 2023 · 14:22",
    lastExecution: "2 mins ago",
    executionStatus: "success",
    version: "v2.4.1-stable",
  },
  {
    id: "2",
    name: "Lead_Gen_Bot_01",
    status: "error",
    timeCreated: "Oct 10, 2023 · 09:15",
    lastExecution: "Failed 1h ago",
    executionStatus: "failed",
    version: "v1.0.9-hotfix",
  },
  {
    id: "3",
    name: "Researcher_V3",
    status: "inactive",
    timeCreated: "Sep 28, 2023 · 21:05",
    lastExecution: "Never executed",
    executionStatus: "never",
    version: "v3.0.0-beta",
  },
  {
    id: "4",
    name: "Social_Monitor_Global",
    status: "healthy",
    timeCreated: "Sep 22, 2023 · 11:30",
    lastExecution: "15 mins ago",
    executionStatus: "success",
    version: "v1.2.0-stable",
  },
  {
    id: "5",
    name: "Log_Analyzer_System",
    status: "healthy",
    timeCreated: "Sep 15, 2023 · 04:12",
    lastExecution: "Just now",
    executionStatus: "success",
    version: "v4.4.2-prod",
  },
  {
    id: "6",
    name: "Email_Responder_Auto",
    status: "error",
    timeCreated: "Sep 10, 2023 · 18:45",
    lastExecution: "Timeout 12h ago",
    executionStatus: "timeout",
    version: "v0.9.8-dev",
  },
  {
    id: "7",
    name: "Audit_Trail_Scanner",
    status: "healthy",
    timeCreated: "Aug 30, 2023 · 13:00",
    lastExecution: "3 hours ago",
    executionStatus: "success",
    version: "v1.1.0-stable",
  },
  {
    id: "8",
    name: "Legacy_Connector_X",
    status: "inactive",
    timeCreated: "Aug 12, 2023 · 10:20",
    lastExecution: "3 months ago",
    executionStatus: "never",
    version: "v8.6.1-legacy",
  },
];

const getStatusColor = (status: string) => {
  switch (status) {
    case "healthy":
      return "bg-green-500 shadow-lg shadow-green-500/60";
    case "error":
      return "bg-red-400 shadow-lg shadow-red-400/60";
    case "inactive":
      return "bg-slate-600";
    default:
      return "bg-slate-600";
  }
};

const getStatusTextColor = (status: string) => {
  switch (status) {
    case "healthy":
      return "text-slate-100";
    case "error":
      return "text-red-300";
    case "inactive":
      return "text-slate-400 opacity-50";
    default:
      return "text-slate-400";
  }
};

const getVersionBgColor = (status: string) => {
  switch (status) {
    case "healthy":
      return "bg-amber-600/10";
    default:
      return "bg-slate-700";
  }
};

const getVersionTextColor = (status: string) => {
  switch (status) {
    case "healthy":
      return "text-amber-600";
    default:
      return "text-slate-400";
  }
};

export default function MyAgents() {
  const [searchQuery, setSearchQuery] = useState("");
  const healthyCount = agents.filter((a) => a.status === "healthy").length;
  const errorCount = agents.filter((a) => a.status === "error").length;
  const inactiveCount = agents.filter((a) => a.status === "inactive").length;

  return (
    <div className="flex flex-col h-full">
      {/* Page Header */}
      <div className="flex flex-col gap-1 pb-8 border-b border-slate-700 mb-6">
        <h1 className="text-4xl font-semibold text-slate-100">My Agents</h1>
        <p className="text-sm text-slate-400">
          Manage and monitor your active autonomous agents.
        </p>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          {/* Search is in TopNav */}
        </div>
        <div className="flex items-center gap-3">
          <button className="flex items-center gap-2 px-4 py-2 bg-slate-800 border border-slate-600 rounded text-slate-100 text-xs font-semibold hover:bg-slate-700 transition-colors">
            ⚙️ FILTER
          </button>
          <Link
            to="/agents/new"
            className="flex items-center gap-2 px-6 py-2 bg-amber-600 hover:bg-amber-700 text-slate-900 text-xs font-bold rounded transition-colors"
          >
            + DEPLOY NEW
          </Link>
        </div>
      </div>

      {/* Table */}
      <div className="flex-1 border border-slate-700 rounded-lg overflow-hidden bg-slate-900 flex flex-col">
        {/* Table Header */}
        <div className="grid grid-cols-12 gap-4 bg-slate-800 border-b border-slate-700 px-6 py-4 text-xs font-semibold text-slate-400 uppercase tracking-wider">
          <div className="col-span-4">Name</div>
          <div className="col-span-3">Time Created</div>
          <div className="col-span-3">Last Execution</div>
          <div className="col-span-2 text-right">Version</div>
        </div>

        {/* Table Body */}
        <div className="flex-1 overflow-y-auto">
          {agents.map((agent) => (
            <div
              key={agent.id}
              className="grid grid-cols-12 gap-4 px-6 py-4 border-b border-slate-700 hover:bg-slate-800/50 transition-colors items-center"
            >
              {/* Name with Status */}
              <div className="col-span-4 flex items-center gap-3">
                <div
                  className={`w-2 h-2 rounded-full ${getStatusColor(agent.status)}`}
                ></div>
                <Link
                  to={`/agents/${agent.id}`}
                  className={`text-sm font-medium ${getStatusTextColor(agent.status)} hover:underline`}
                >
                  {agent.name}
                </Link>
              </div>

              {/* Time Created */}
              <div className="col-span-3 text-sm text-slate-400">
                {agent.timeCreated}
              </div>

              {/* Last Execution */}
              <div className="col-span-3">
                <span
                  className={`text-sm ${
                    agent.executionStatus === "failed"
                      ? "text-red-400"
                      : agent.executionStatus === "timeout"
                        ? "text-yellow-400"
                        : agent.status === "inactive"
                          ? "text-slate-400 opacity-50"
                          : "text-slate-400"
                  }`}
                >
                  {agent.lastExecution}
                </span>
              </div>

              {/* Version */}
              <div className="col-span-2 text-right">
                <span
                  className={`inline-block px-2 py-1 rounded text-xs font-mono ${getVersionBgColor(
                    agent.status,
                  )} ${getVersionTextColor(agent.status)}`}
                >
                  {agent.version}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Stats Footer */}
      <div className="mt-6 pt-6 border-t border-slate-700">
        <div className="flex items-center justify-between mb-6">
          <div className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
            {agents.length} Agents Total
          </div>
          <div className="flex items-center gap-6 text-xs font-medium">
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-green-500"></div>
              <span className="text-slate-400">{healthyCount} Healthy</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-red-400"></div>
              <span className="text-slate-400">{errorCount} Errors</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-2 h-2 rounded-full bg-slate-600"></div>
              <span className="text-slate-400">{inactiveCount} Inactive</span>
            </div>
          </div>
        </div>

        {/* Metrics Cards */}
        <div className="grid grid-cols-3 gap-4">
          <div className="p-4 border border-slate-700 rounded bg-slate-900">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              System Load
            </div>
            <div className="text-xl font-bold text-amber-600">
              34% Total CPU
            </div>
          </div>
          <div className="p-4 border border-slate-700 rounded bg-slate-900">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Active Sessions
            </div>
            <div className="text-xl font-bold text-slate-100">
              12{" "}
              <span className="text-green-500 text-sm ml-2">
                +2 from 1 hour
              </span>
            </div>
          </div>
          <div className="p-4 border border-slate-700 rounded bg-slate-900">
            <div className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Memory Usage
            </div>
            <div className="text-xl font-bold text-slate-100">
              4.2<span className="text-sm text-slate-500">GB</span> / 16GB
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
