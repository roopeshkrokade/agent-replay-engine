import React from "react";
import { HashRouter, Routes, Route } from "react-router-dom";
import MyAgents from "./pages/MyAgents";
import AgentWorkspace from "./pages/AgentWorkspace";
import Landing from "./pages/Landing";
import AppShell from "./components/layout/AppShell";

export default function App() {
  return (
    <HashRouter>
      <AppShell>
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/agents" element={<MyAgents />} />
          <Route path="/agents/:agentId" element={<AgentWorkspace />} />
        </Routes>
      </AppShell>
    </HashRouter>
  );
}
