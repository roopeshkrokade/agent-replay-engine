import React, { PropsWithChildren } from "react";
import TopNav from "./TopNav";

export default function AppShell({ children }: PropsWithChildren) {
  return (
    <div className="app-shell">
      <TopNav />
      <main className="main-content">{children}</main>
    </div>
  );
}
