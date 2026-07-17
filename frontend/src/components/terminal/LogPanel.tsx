import React, { useEffect, useRef } from "react";

export default function LogPanel({ lines }: { lines: string[] }) {
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [lines]);

  return (
    <div className="p-4 border border-slate-700 rounded bg-black/60">
      <div className="h-72 overflow-y-auto font-mono text-sm" ref={ref}>
        {lines.map((l, i) => (
          <div key={i} className="px-2 py-1 text-slate-200">
            {l}
          </div>
        ))}
      </div>
    </div>
  );
}
