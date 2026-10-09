"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Link2,
  Sparkles,
  BookOpen,
  ArrowRight,
  ShieldCheck,
  Zap,
  BookmarkCheck,
  Loader2,
  AlertCircle,
  ExternalLink,
  BookMarked,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import { api } from "@/lib/api";
import { Novel } from "@/types";

const SAMPLE_URLS = [
  {
    name: "Syosetu (Nhật)",
    url: "https://ncode.syosetu.com/n1444ie/",
    desc: "Tiểu thuyết Shousetsuka ni Narou",
  },
  {
    name: "Royal Road (Âu Mỹ)",
    url: "https://www.royalroad.com/fiction/21220/mother-of-learning",
    desc: "English Web Novel",
  },
  {
    name: "ReadNovelFull",
    url: "https://readnovelfull.com/lord-of-the-mysteries.html",
    desc: "Tiểu thuyết kỳ ảo",
  },
];

export default function HomePage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [recentNovels, setRecentNovels] = useState<Novel[]>([]);
  const [loadingNovels, setLoadingNovels] = useState(true);

  // Load recently analyzed novels
  useEffect(() => {
    async function fetchRecent() {
      try {
        setLoadingNovels(true);
        const novels = await api.getNovels(20);
        setRecentNovels(novels);
      } catch (err) {
        // Silently fail or keep empty list if offline initially
      } finally {
        setLoadingNovels(false);
      }
    }
    fetchRecent();
  }, []);

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url.trim()) {
      setError("Vui lòng nhập đường dẫn URL của truyện.");
      return;
    }

    try {
      setLoading(true);
      setError("");
      const result = await api.analyzeUrl(url.trim());
      if (result.success && result.novel?.id) {
        router.push(`/novel/${result.novel.id}`);
      } else {
        setError(result.error?.message || "Không thể phân tích website này.");
      }
    } catch (err: any) {
      setError(err.message || "❌ Không thể lấy nội dung từ URL này. Vui lòng kiểm tra lại liên kết.");
    } finally {
      setLoading(false);
    }
  };

  const handleSelectSample = (sampleUrl: string) => {
    setUrl(sampleUrl);
    setError("");
  };

  return (
    <div className="min-h-screen bg-[#080B11] text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Hero Section */}
        <div className="relative overflow-hidden rounded-3xl border border-slate-800/80 bg-gradient-to-b from-slate-900/80 via-slate-900/40 to-slate-950/80 p-8 sm:p-12 shadow-2xl backdrop-blur-xl mb-12">
          {/* Subtle Ambient Glow */}
          <div className="absolute -top-24 left-1/2 -translate-x-1/2 h-64 w-96 rounded-full bg-indigo-500/15 blur-3xl pointer-events-none" />

          <div className="relative z-10 mx-auto max-w-3xl text-center">
            <div className="inline-flex items-center gap-2 rounded-full border border-indigo-500/30 bg-indigo-500/10 px-3.5 py-1 text-xs font-semibold text-indigo-300 mb-6">
              <Sparkles className="h-3.5 w-3.5 text-cyan-400" />
              <span>Dịch truyện từ URL bằng AI</span>
            </div>

            <h1 className="text-3xl sm:text-5xl font-black tracking-tight text-white mb-4">
              NOVEL AI TRANSLATOR
            </h1>
            <p className="text-sm sm:text-base text-slate-300 leading-relaxed max-w-2xl mx-auto mb-8">
              Nhập link tiểu thuyết từ bất kỳ website nào. Hệ thống tự động phân tích mục lục, làm sạch văn bản, chia đoạn thông minh và dịch sang tiếng Việt mượt mà.
            </p>

            {/* URL Input Form */}
            <form onSubmit={handleAnalyze} className="relative mx-auto max-w-2xl">
              <div className="flex flex-col sm:flex-row items-stretch gap-2 rounded-2xl border border-slate-700/80 bg-slate-900/90 p-2 shadow-xl shadow-black/50 focus-within:border-indigo-500 transition-colors">
                <div className="relative flex-1 flex items-center">
                  <Link2 className="absolute left-3.5 h-5 w-5 text-slate-400" />
                  <input
                    type="url"
                    placeholder="🔗 Dán URL truyện vào đây (vd: https://ncode.syosetu.com/...)"
                    value={url}
                    onChange={(e) => {
                      setUrl(e.target.value);
                      if (error) setError("");
                    }}
                    disabled={loading}
                    className="w-full rounded-xl bg-transparent pl-11 pr-4 py-3 text-sm text-white placeholder-slate-400 focus:outline-none"
                    required
                  />
                  {url && (
                    <button
                      type="button"
                      onClick={() => setUrl("")}
                      className="mr-2 text-xs text-slate-400 hover:text-slate-200"
                    >
                      Xóa
                    </button>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={loading}
                  className="flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 px-6 py-3 text-sm font-bold text-white shadow-lg shadow-indigo-600/30 hover:opacity-95 disabled:opacity-50 transition-all"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      <span>Đang phân tích...</span>
                    </>
                  ) : (
                    <>
                      <Sparkles className="h-4 w-4" />
                      <span>PHÂN TÍCH TRUYỆN</span>
                    </>
                  )}
                </button>
              </div>

              {/* Error Banner */}
              {error && (
                <div className="mt-4 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-left text-xs text-red-300">
                  <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
                  <span>{error}</span>
                </div>
              )}
            </form>

            {/* Quick Demo URLs */}
            <div className="mt-6 flex flex-wrap items-center justify-center gap-2 text-xs">
              <span className="text-slate-400 font-medium">Thử nhanh URL mẫu:</span>
              {SAMPLE_URLS.map((sample) => (
                <button
                  key={sample.name}
                  onClick={() => handleSelectSample(sample.url)}
                  className="rounded-lg border border-slate-800 bg-slate-900/60 px-2.5 py-1 text-slate-300 hover:border-indigo-500/50 hover:text-indigo-300 transition-colors"
                >
                  {sample.name}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Feature Highlights */}
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-14">
          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-5 backdrop-blur-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/15 text-indigo-400 mb-3">
              <Zap className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-bold text-white mb-1">URL Analyzer</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Tự động phát hiện tên truyện, tác giả, ảnh bìa, mô tả và toàn bộ danh sách chương.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-5 backdrop-blur-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-cyan-500/15 text-cyan-400 mb-3">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-bold text-white mb-1">Content Cleaner & SSRF</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Lọc sạch quảng cáo, tracking, boilerplate và bảo vệ hệ thống tuyệt đối chống SSRF.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-5 backdrop-blur-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-500/15 text-amber-400 mb-3">
              <BookMarked className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-bold text-white mb-1">Translation Memory</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Bảng thuật ngữ Glossary giữ nhất quán tên nhân vật và xưng hô trong suốt bộ truyện.
            </p>
          </div>

          <div className="rounded-2xl border border-slate-800/80 bg-slate-900/40 p-5 backdrop-blur-sm">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/15 text-emerald-400 mb-3">
              <BookmarkCheck className="h-5 w-5" />
            </div>
            <h3 className="text-sm font-bold text-white mb-1">Modern Reader & Cache</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Giao diện đọc truyện tiện nghi, lưu trữ hash SHA256 để không bao giờ phải dịch lại.
            </p>
          </div>
        </div>

        {/* Recently Analyzed Novels */}
        <section className="mb-14">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <BookOpen className="h-5 w-5 text-indigo-400" />
              <h2 className="text-lg font-bold text-white">Truyện đã phân tích gần đây</h2>
            </div>
            <span className="text-xs text-slate-400">
              {recentNovels.length} bộ truyện trong thư viện
            </span>
          </div>

          {loadingNovels ? (
            <div className="flex items-center justify-center py-12 text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
            </div>
          ) : recentNovels.length === 0 ? (
            <div className="rounded-2xl border border-slate-800/80 bg-slate-900/20 p-8 text-center">
              <p className="text-sm text-slate-400">Chưa có truyện nào trong lịch sử.</p>
              <p className="text-xs text-slate-500 mt-1">Dán link truyện vào ô tìm kiếm bên trên để bắt đầu phân tích!</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {recentNovels.map((novel) => (
                <Link
                  key={novel.id}
                  href={`/novel/${novel.id}`}
                  className="group relative flex flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/60 p-4 transition-all hover:border-indigo-500/40 hover:bg-slate-900 hover:shadow-xl hover:shadow-indigo-950/20"
                >
                  <div className="flex gap-4">
                    {/* Cover or Placeholder */}
                    <div className="h-28 w-20 shrink-0 overflow-hidden rounded-xl border border-slate-800 bg-slate-800/80 flex items-center justify-center">
                      {novel.cover_url ? (
                        <img
                          src={novel.cover_url}
                          alt={novel.title}
                          className="h-full w-full object-cover group-hover:scale-105 transition-transform duration-300"
                          onError={(e) => {
                            // If image fails to load, fallback
                            (e.target as HTMLElement).style.display = "none";
                          }}
                        />
                      ) : (
                        <BookOpen className="h-8 w-8 text-slate-600" />
                      )}
                    </div>

                    <div className="flex-1 min-w-0 flex flex-col justify-between">
                      <div>
                        <div className="flex items-center gap-1.5 mb-1">
                          <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] font-medium text-slate-400">
                            {novel.source_domain || "Web"}
                          </span>
                        </div>
                        <h3 className="text-sm font-bold text-white truncate group-hover:text-indigo-300 transition-colors">
                          {novel.title}
                        </h3>
                        <p className="text-xs text-slate-400 truncate mt-0.5">
                          Tác giả: {novel.author}
                        </p>
                      </div>

                      <div className="mt-3 flex items-center justify-between text-[11px] text-slate-400">
                        <span>{novel.total_chapters} chương</span>
                        {novel.translated_count !== undefined && novel.translated_count > 0 ? (
                          <span className="rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-400 font-medium border border-emerald-500/20">
                            Đã dịch {novel.translated_count}
                          </span>
                        ) : (
                          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-slate-400">
                            Chưa dịch
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </section>
      </main>

      <footer className="border-t border-slate-900 bg-slate-950/60 py-6 text-center text-xs text-slate-500">
        <p>NOVEL AI TRANSLATOR — Full-Stack Realtime Novel Translation Platform</p>
      </footer>
    </div>
  );
}
