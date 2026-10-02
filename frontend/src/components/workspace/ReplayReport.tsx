import React from "react";
import type { Divergence, ReplayResult } from "../../services/api.services";

const DIVERGENCE_LABELS: Record<string, string> = {
  request_mismatch: "Request changed",
  over_execution: "Extra call",
  under_execution: "Call never made",
  tool_changed: "Different tool",
  tool_input_changed: "Tool arguments changed",
  tool_output_changed: "Tool result changed",
  tool_missing: "Tool call missing",
  tool_extra: "Extra tool call",
};

const pretty = (value: unknown) => (typeof value === "string" ? value : JSON.stringify(value, null, 2));

function DivergenceItem({ d }: { d: Divergence }) {
  const isError = d.severity === "error";
  const where = d.tool ? `tool ${d.tool} #${d.tool_step}` : d.step ? `call #${d.step}${d.api ? ` · ${d.api}` : ""}` : "";
  return (
    <li className={`rounded-lg border px-3 py-2 ${isError ? "border-red-800 bg-red-950/30" : "border-amber-800/60 bg-amber-950/20"}`}>
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span className={`rounded px-1.5 py-0.5 font-bold uppercase ${isError ? "bg-red-600 text-white" : "bg-amber-500 text-slate-950"}`}>
          {d.severity}
        </span>
        <span className="font-semibold text-slate-100">{DIVERGENCE_LABELS[d.type] ?? d.type}</span>
        {where ? <span className="font-mono text-slate-400">{where}</span> : null}
      </div>
      <div className="mt-1 text-xs text-slate-300">{d.reason}</div>
      {d.expected !== undefined || d.got !== undefined ? (
        <details className="mt-2 text-xs">
          <summary className="cursor-pointer text-slate-400 hover:text-slate-200">Expected vs got</summary>
          <div className="mt-2 grid gap-2 md:grid-cols-2">
            {(["expected", "got"] as const).map((key) => (
              <div key={key}>
                <div className="mb-1 font-semibold uppercase tracking-wider text-slate-500">{key}</div>
                <pre className="max-h-48 overflow-auto whitespace-pre-wrap rounded bg-slate-900 p-2 font-mono text-slate-200">
                  {d[key] === null || d[key] === undefined ? "—" : pretty(d[key])}
                </pre>
              </div>
            ))}
          </div>
        </details>
      ) : null}
    </li>
  );
}

export default function ReplayReport({ result, onClose }: { result: ReplayResult; onClose: () => void }) {
  const { report } = result;
  const ok = result.status === "success";
  const faults = report.events.filter((e) => e.type === "fault_injected");
  const replayedErrors = report.events.filter((e) => e.type === "replayed_error");
  const errors = report.divergences.filter((d) => d.severity === "error").length;

  return (
    <section aria-label="Replay report" className="border-b border-slate-800 bg-slate-900/60 px-3 py-3 sm:px-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 flex-shrink-0 rounded-full ${ok ? "bg-green-500" : "bg-red-500"}`} />
            <h2 className={`truncate text-sm font-bold ${ok ? "text-green-400" : "text-red-400"}`}>{result.message}</h2>
          </div>
          <div className="mt-2 flex flex-wrap gap-2 text-xs font-mono text-slate-300">
            <span className="rounded border border-slate-700 bg-slate-950 px-2 py-1">
              served {report.served_steps}/{report.total_steps} recorded calls
            </span>
            <span className="rounded border border-slate-700 bg-slate-950 px-2 py-1">{report.match} match</span>
            <span className="rounded border border-slate-700 bg-slate-950 px-2 py-1">
              {report.divergences.length} divergence{report.divergences.length === 1 ? "" : "s"}
              {errors ? ` (${errors} error${errors === 1 ? "" : "s"})` : ""}
            </span>
            {faults.map((e, i) => (
              <span key={`f${i}`} className="rounded border border-amber-800 bg-amber-950/40 px-2 py-1 text-amber-300">
                fault injected · call #{e.step} · HTTP {e.status}
              </span>
            ))}
            {replayedErrors.map((e, i) => (
              <span key={`e${i}`} className="rounded border border-sky-800 bg-sky-950/40 px-2 py-1 text-sky-300">
                recorded error replayed · call #{e.step} · HTTP {e.status}
              </span>
            ))}
          </div>
          {report.tool_check !== "compared" ? (
            <div className="mt-2 text-xs text-slate-500">Tool check {report.tool_check}</div>
          ) : null}
        </div>
        <button onClick={onClose} className="flex-shrink-0 text-xs text-slate-500 hover:text-slate-200" aria-label="Close replay report">
          ✕
        </button>
      </div>

      {report.divergences.length ? (
        <ul className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
          {report.divergences.map((d, i) => (
            <DivergenceItem key={i} d={d} />
          ))}
        </ul>
      ) : (
        <div className="mt-3 text-xs text-slate-400">No divergences: the agent behaved exactly as recorded.</div>
      )}
    </section>
  );
}
