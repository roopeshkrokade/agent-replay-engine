import React from "react";
import { Link } from "react-router-dom";

const PipelineStep = ({
  icon,
  title,
  description,
}: {
  icon: string;
  title: string;
  description: string;
}) => (
  <div className="backdrop-blur rounded-lg border border-slate-700 p-6 w-72 flex flex-col items-center text-center">
    <div className="w-16 h-16 rounded-full bg-slate-700 border border-amber-600 flex items-center justify-center mb-4">
      <span className="text-2xl">{icon}</span>
    </div>
    <h3 className="font-bold text-white mb-2">{title}</h3>
    <p className="text-sm text-slate-300">{description}</p>
  </div>
);

export default function Landing() {
  return (
    <>
      <div className="w-full">
        {/* Hero Section */}
        <div className="min-h-screen flex flex-col items-center justify-center px-6 py-20">
          {/* Badge */}
          <div className="inline-flex items-center gap-2 mb-8 px-4 py-2 rounded-full border border-amber-700/30 bg-amber-900/10">
            <div className="w-2 h-2 rounded-full bg-amber-600"></div>
            <span className="text-xs font-semibold text-amber-600 tracking-wider uppercase">
              v2.4 Engine Now Deterministic
            </span>
          </div>

          {/* Heading */}
          <h1 className="text-6xl font-bold text-center max-w-3xl mb-6 leading-tight">
            <span className="text-slate-100">
              Deterministic Reliability for
            </span>
            <br />
            <span className="text-amber-600">Autonomous AI Systems</span>
          </h1>

          {/* Subheading */}
          <p className="text-xl text-slate-300 text-center max-w-2xl mb-12 leading-relaxed">
            Capture, replay, and debug complex LLM agent interactions with
            millisecond precision. Eliminate the "black box" of stochastic agent
            behavior once and for all.
          </p>

          {/* CTA Buttons */}
          <div className="flex gap-4 mb-20">
            <Link
              to="/agents"
              className="inline-flex items-center gap-2 px-8 py-3 bg-amber-600 hover:bg-amber-700 text-slate-900 font-bold rounded transition-colors"
            >
              Get Started
              <span>→</span>
            </Link>
            <button className="inline-flex items-center px-8 py-3 border border-slate-600 text-slate-100 font-bold rounded hover:bg-slate-900/50 transition-colors">
              View Demo
            </button>
          </div>

          {/* Decorative element */}
          <div className="w-full max-w-2xl h-64 rounded-lg bg-gradient-to-b from-slate-800 to-transparent opacity-20 blur-2xl -mt-20"></div>
        </div>

        {/* Pipeline Section */}
        <div className="border-t border-b border-slate-700 bg-slate-950 py-24 px-6">
          <div className="max-w-6xl mx-auto">
            {/* Section Header */}
            <div className="text-center mb-16">
              <h2 className="text-4xl font-bold text-slate-100 mb-4">
                The Execution Pipeline
              </h2>
              <p className="text-lg text-slate-400">
                Universal capture for any LLM-powered application
              </p>
            </div>

            {/* Pipeline Steps */}
            <div className="flex justify-center items-center gap-8 flex-wrap">
              {/* Pipeline line connector */}
              <div
                className="absolute h-1 bg-gradient-to-r from-slate-700 via-amber-600 to-slate-700 opacity-30"
                style={{ width: "calc(100% - 48px)", maxWidth: "1200px" }}
              ></div>

              <PipelineStep
                icon="📝"
                title="Capture"
                description="Deep-hooks into SDKs capture all inputs, tool calls, and hidden reasoning chains."
              />
              <PipelineStep
                icon="⚙️"
                title="Replay Engine"
                description="Virtualizes environmental state to guarantee bit-for-bit identical reproduction."
              />
              <PipelineStep
                icon="🔍"
                title="Analysis"
                description="Inspect state transitions, identify divergence points, and validate determinism."
              />
            </div>
          </div>
        </div>

        {/* CTA Section */}
        <div className="py-24 px-6 text-center">
          <h2 className="text-4xl font-bold text-slate-100 mb-6">
            Ready to Debug Your Agents?
          </h2>
          <p className="text-lg text-slate-400 mb-8 max-w-2xl mx-auto">
            Start replaying traces in minutes. No complex setup required.
          </p>
          <Link
            to="/agents"
            className="inline-flex items-center gap-2 px-8 py-3 bg-amber-600 hover:bg-amber-700 text-slate-900 font-bold rounded transition-colors"
          >
            Launch Dashboard
            <span>→</span>
          </Link>
        </div>
      </div>
    </>
  );
}
