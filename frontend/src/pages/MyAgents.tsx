import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { fetchAgents } from "../services/api.services";

interface Agent {
  id: string;
  name: string;
  status: "healthy" | "error" | "inactive";
  timeCreated: string;
  lastExecution: string;
  executionStatus?: "success" | "failed" | "timeout" | "never";
  version: string;
}

// Agents are loaded from the backend API at `/api/agents`.
// The backend returns objects with `agent_id`, `agent_name`, `latest_version`,
// `created_at`, and `last_execution_timestamp`.

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
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const healthyCount = agents.filter((a) => a.status === "healthy").length;
  const errorCount = agents.filter((a) => a.status === "error").length;
  const inactiveCount = agents.filter((a) => a.status === "inactive").length;

  useEffect(() => {
    const ac = new AbortController();
    async function loadAgents() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchAgents(ac.signal);
        // Map backend shape to UI shape
        const mapped: Agent[] = (data || []).map((a: any) => ({
          id: a.agent_id,
          name: a.agent_name,
          status: a.last_execution_timestamp ? "healthy" : "inactive",
          timeCreated: a.created_at
            ? new Date(a.created_at).toLocaleString()
            : "Unknown",
          lastExecution: a.last_execution_timestamp
            ? new Date(a.last_execution_timestamp).toLocaleString()
            : "Never executed",
          executionStatus: a.last_execution_timestamp ? "success" : "never",
          version: a.latest_version || "unknown",
        }));
        setAgents(mapped);
      } catch (err: any) {
        if (err.name !== "AbortError") setError(err.message || String(err));
      } finally {
        setLoading(false);
      }
    }

    loadAgents();
    return () => ac.abort();
  }, []);

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
          {loading ? (
            <div className="p-6 text-center text-slate-400">
              Loading agents...
            </div>
          ) : error ? (
            <div className="p-6 text-center">
              <div className="text-red-400 mb-2">
                Error loading agents: {error}
              </div>
              <button
                onClick={() => window.location.reload()}
                className="px-4 py-2 bg-amber-600 text-slate-900 rounded text-xs font-bold"
              >
                Retry
              </button>
            </div>
          ) : agents.length === 0 ? (
            <div className="p-6 text-center text-slate-400">
              No agents found.
            </div>
          ) : (
            agents.map((agent) => (
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
            ))
          )}
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
