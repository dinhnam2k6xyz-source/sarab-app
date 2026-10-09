"use client";

import React from "react";
import Link from "next/link";
import { BookOpen, Sparkles, History, Globe } from "lucide-react";

export default function Navbar() {
  return (
    <header className="sticky top-0 z-40 w-full border-b border-slate-800/80 bg-slate-950/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-center gap-3 transition-opacity hover:opacity-90">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-cyan-400 shadow-lg shadow-indigo-500/20">
            <BookOpen className="h-5 w-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-lg font-black tracking-tight text-white">NOVEL</span>
              <span className="text-lg font-black tracking-tight bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">AI</span>
              <span className="text-xs font-semibold uppercase tracking-widest text-indigo-400/80">Translator</span>
            </div>
            <p className="text-[10px] text-slate-400 leading-none">URL → Vietnamese Web Novel</p>
          </div>
        </Link>

        <div className="flex items-center gap-3">
          <Link
            href="/"
            className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-slate-700 hover:text-white"
          >
            <History className="h-3.5 w-3.5 text-slate-400" />
            <span>Lịch sử truyện</span>
          </Link>

          <div className="flex items-center gap-1.5 rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1.5 text-xs font-medium text-slate-300">
            <Globe className="h-3.5 w-3.5 text-cyan-400" />
            <span className="text-slate-200">Tiếng Việt</span>
          </div>

          <div className="hidden sm:flex items-center gap-1 rounded-full bg-emerald-500/10 px-2.5 py-1 text-[11px] font-medium text-emerald-400 border border-emerald-500/20">
            <Sparkles className="h-3 w-3" />
            <span>AI Ready</span>
          </div>
        </div>
      </div>
    </header>
  );
}
