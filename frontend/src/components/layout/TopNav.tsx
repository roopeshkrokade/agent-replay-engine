import React from "react";
import { Link } from "react-router-dom";

export default function TopNav() {
  return (
    <header className="topnav bg-surface w-full h-toolbar-height sticky top-0 z-50 border-b border-outline-variant flex justify-between items-center px-gutter">
      <div className="flex items-center gap-8">
        <Link
          to="/"
          className="font-headline-md text-headline-md text-primary tracking-tight font-bold cursor-pointer"
        >
          Agent Replay
        </Link>
        <nav className="hidden md:flex items-center gap-6">
          <Link
            to="/"
            className="text-on-surface-variant font-medium hover:text-primary transition-colors duration-200 font-body-md text-body-md cursor-pointer"
          >
            Home
          </Link>
          <Link
            to="/agents"
            className="text-primary font-bold border-b-2 border-primary font-body-md text-body-md cursor-pointer"
          >
            My Agents
          </Link>
        </nav>
      </div>
      <div className="flex items-center gap-4">
        <div className="relative hidden lg:block">
          <input
            className="bg-surface-container-low border border-outline-variant rounded-full py-1.5 px-4 text-body-sm font-body-sm focus:outline-none focus:border-primary w-64 transition-all"
            placeholder="Search agents..."
            type="text"
          />
          <span className="material-symbols-outlined absolute right-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-[18px]">
            search
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="material-symbols-outlined text-on-surface-variant hover:text-primary cursor-pointer p-1.5 transition-colors">
            notifications
          </span>
          <span className="material-symbols-outlined text-on-surface-variant hover:text-primary cursor-pointer p-1.5 transition-colors">
            settings
          </span>
          <div className="w-8 h-8 rounded-full overflow-hidden border border-outline-variant ml-2 cursor-pointer active:opacity-80">
            <img
              className="w-full h-full object-cover"
              alt="User avatar"
              src="https://lh3.googleusercontent.com/aida-public/AB6AXuAFoWGBVKSqp5ueVIukvLx0FAo7VciGy5FlaJAoWPIz_Ig8_31CO9voZtvmKvBWl3PWyWv9l9_7BADmEiWBVRbhybfz15716lQfwqSd4_Mctt_KLExkjsoylur8TFfPI-vJCPOz0aYECYBOTTbGCNMdziUPtMHLIoz7-e8f5cduPF4Z-VrGT39ecUYpAdq1NxKkgzsA2fuS_bs_glft0-ldfVEXcxtSEHaW5U1bN0XJiKBVufpSig4"
            />
          </div>
        </div>
      </div>
    </header>
  );
}
