"use client";

import React, { useState, useEffect, useMemo } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  BookOpen,
  Sparkles,
  ArrowUpDown,
  Search,
  CheckCircle2,
  Clock,
  Loader2,
  AlertCircle,
  BookMarked,
  Layers,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  RotateCcw,
} from "lucide-react";
import Navbar from "@/components/Navbar";
import TranslationProgressModal from "@/components/TranslationProgressModal";
import GlossaryModal from "@/components/GlossaryModal";
import { api } from "@/lib/api";
import { Novel, Chapter, ChapterStatus } from "@/types";

export default function NovelDetailPage() {
  const params = useParams();
  const router = useRouter();
  const novelId = Number(params?.id);

  const [novel, setNovel] = useState<Novel | null>(null);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Search, Sort, Filter
  const [search, setSearch] = useState("");
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc");
  const [filterStatus, setFilterStatus] = useState<string>("all");
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;

  // Selection
  const [selectedChapterIds, setSelectedChapterIds] = useState<number[]>([]);

  // Modals & Realtime Job Tracking
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [activeJobChapterTitle, setActiveJobChapterTitle] = useState("");
  const [activeJobChapterId, setActiveJobChapterId] = useState<number | null>(null);
  const [isProgressModalOpen, setIsProgressModalOpen] = useState(false);
  const [isGlossaryModalOpen, setIsGlossaryModalOpen] = useState(false);

  // Bulk translation loading
  const [bulkLoading, setBulkLoading] = useState(false);

  const fetchNovelData = async () => {
    if (!novelId) return;
    try {
      setLoading(true);
      setError("");
      const [novelData, chaptersData] = await Promise.all([
        api.getNovel(novelId),
        api.getNovelChapters(novelId, 500, 0, "asc"),
      ]);
      setNovel(novelData);
      setChapters(chaptersData);
    } catch (err: any) {
      setError(err.message || "Không thể tải thông tin bộ truyện.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchNovelData();
  }, [novelId]);

  // Filtering and Sorting
  const filteredChapters = useMemo(() => {
    let result = [...chapters];

    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (c) =>
          c.title.toLowerCase().includes(q) ||
          c.chapter_number.toString().includes(q)
      );
    }

    if (filterStatus !== "all") {
      result = result.filter((c) => c.status === filterStatus);
    }

    if (sortOrder === "desc") {
      result.reverse();
    }

    return result;
  }, [chapters, search, filterStatus, sortOrder]);

  // Pagination
  const totalPages = Math.ceil(filteredChapters.length / pageSize) || 1;
  const paginatedChapters = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredChapters.slice(start, start + pageSize);
  }, [filteredChapters, currentPage, pageSize]);

  // Selection handlers
  const handleSelectAllCurrentPage = () => {
    const pageIds = paginatedChapters.map((c) => c.id);
    const allSelected = pageIds.every((id) => selectedChapterIds.includes(id));
    if (allSelected) {
      setSelectedChapterIds((prev) => prev.filter((id) => !pageIds.includes(id)));
    } else {
      setSelectedChapterIds((prev) => Array.from(new Set([...prev, ...pageIds])));
    }
  };

  const handleToggleChapter = (id: number) => {
    setSelectedChapterIds((prev) =>
      prev.includes(id) ? prev.filter((item) => item !== id) : [...prev, id]
    );
  };

  // Start single chapter translation
  const handleTranslateSingle = async (chapter: Chapter, force = false) => {
    try {
      setError("");
      const job = await api.translateChapter(chapter.id, force);
      setActiveJobId(job.job_id);
      setActiveJobChapterTitle(chapter.title);
      setActiveJobChapterId(chapter.id);
      setIsProgressModalOpen(true);

      // Optimistically update chapter status to translating
      setChapters((prev) =>
        prev.map((c) => (c.id === chapter.id ? { ...c, status: "translating" } : c))
      );
    } catch (err: any) {
      setError(err.message || "Không thể khởi động tiến trình dịch.");
    }
  };

  // Bulk translate selected chapters
  const handleTranslateSelected = async () => {
    if (selectedChapterIds.length === 0) return;
    try {
      setBulkLoading(true);
      setError("");
      const res = await api.translateBulk(selectedChapterIds);
      if (res.jobs.length > 0) {
        // Track first job in progress modal
        const firstJob = res.jobs[0];
        const targetChap = chapters.find((c) => c.id === firstJob.chapter_id);
        setActiveJobId(firstJob.job_id);
        setActiveJobChapterTitle(targetChap?.title || "Dịch hàng loạt");
        setActiveJobChapterId(firstJob.chapter_id);
        setIsProgressModalOpen(true);

        // Update chapters status
        setChapters((prev) =>
          prev.map((c) =>
            selectedChapterIds.includes(c.id) ? { ...c, status: "queued" } : c
          )
        );
      }
    } catch (err: any) {
      setError(err.message || "Lỗi khi gửi yêu cầu dịch hàng loạt.");
    } finally {
      setBulkLoading(false);
    }
  };

  // Bulk translate all pending chapters
  const handleTranslateAll = async () => {
    const pendingIds = chapters.filter((c) => c.status !== "completed").map((c) => c.id).slice(0, 30);
    if (pendingIds.length === 0) {
      alert("Tất cả các chương đã hoàn thành dịch!");
      return;
    }
    setSelectedChapterIds(pendingIds);
    try {
      setBulkLoading(true);
      const res = await api.translateBulk(pendingIds);
      if (res.jobs.length > 0) {
        setActiveJobId(res.jobs[0].job_id);
        setActiveJobChapterTitle("Dịch toàn bộ chương");
        setActiveJobChapterId(res.jobs[0].chapter_id);
        setIsProgressModalOpen(true);
      }
    } catch (err: any) {
      setError(err.message || "Lỗi khi dịch toàn bộ.");
    } finally {
      setBulkLoading(false);
    }
  };

  const handleJobCompleted = (finishedChapterId: number) => {
    setChapters((prev) =>
      prev.map((c) => (c.id === finishedChapterId ? { ...c, status: "completed" } : c))
    );
  };

  const renderStatusBadge = (chapter: Chapter) => {
    switch (chapter.status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" />
            <span>Đã dịch</span>
          </span>
        );
      case "translating":
      case "processing":
      case "queued":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-indigo-500/15 px-2.5 py-0.5 text-xs font-semibold text-indigo-400 border border-indigo-500/20">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            <span>Đang dịch</span>
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-red-500/15 px-2.5 py-0.5 text-xs font-semibold text-red-400 border border-red-500/20">
            <AlertCircle className="h-3.5 w-3.5" />
            <span>Lỗi</span>
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-medium text-slate-400">
            <Clock className="h-3 w-3" />
            <span>Chưa dịch</span>
          </span>
        );
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#080B11] text-slate-100 flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin text-indigo-400 mx-auto mb-3" />
            <p className="text-sm text-slate-400">Đang tải thông tin truyện...</p>
          </div>
        </div>
      </div>
    );
  }

  if (!novel) {
    return (
      <div className="min-h-screen bg-[#080B11] text-slate-100 flex flex-col">
        <Navbar />
        <div className="flex-1 flex items-center justify-center p-4">
          <div className="text-center max-w-md rounded-2xl border border-slate-800 bg-slate-900/60 p-8">
            <AlertCircle className="h-10 w-10 text-red-400 mx-auto mb-3" />
            <h2 className="text-lg font-bold text-white mb-2">Không tìm thấy truyện</h2>
            <p className="text-xs text-slate-400 mb-6">{error || "Bộ truyện không tồn tại hoặc đã bị xóa."}</p>
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-xl bg-indigo-600 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-500"
            >
              Về trang chủ
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const translatedCount = chapters.filter((c) => c.status === "completed").length;

  return (
    <div className="min-h-screen bg-[#080B11] text-slate-100 flex flex-col">
      <Navbar />

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Navigation Breadcrumb */}
        <div className="mb-6 flex items-center gap-2 text-xs text-slate-400">
          <Link href="/" className="hover:text-white transition-colors">
            Trang chủ
          </Link>
          <span>/</span>
          <span className="text-slate-200 truncate">{novel.title}</span>
        </div>

        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
            <AlertCircle className="h-4 w-4 shrink-0 text-red-400" />
            <span>{error}</span>
          </div>
        )}

        {/* Novel Header Card */}
        <div className="relative overflow-hidden rounded-3xl border border-slate-800/80 bg-slate-900/50 p-6 sm:p-8 backdrop-blur-xl mb-8">
          <div className="flex flex-col md:flex-row gap-6 lg:gap-8 items-start">
            {/* Book Cover */}
            <div className="h-56 w-40 sm:h-64 sm:w-44 shrink-0 overflow-hidden rounded-2xl border border-slate-700/80 bg-slate-800 shadow-xl mx-auto md:mx-0 flex items-center justify-center">
              {novel.cover_url ? (
                <img
                  src={novel.cover_url}
                  alt={novel.title}
                  className="h-full w-full object-cover"
                  onError={(e) => {
                    (e.target as HTMLElement).style.display = "none";
                  }}
                />
              ) : (
                <BookOpen className="h-16 w-16 text-slate-600" />
              )}
            </div>

            {/* Novel Info & Actions */}
            <div className="flex-1 min-w-0 flex flex-col justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="rounded-md bg-indigo-500/15 px-2 py-0.5 text-[11px] font-semibold text-indigo-400 border border-indigo-500/20">
                    {novel.source_domain || "Web Novel"}
                  </span>
                  <a
                    href={novel.url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 rounded-md border border-slate-800 bg-slate-800/60 px-2 py-0.5 text-[11px] font-medium text-slate-400 hover:text-white transition-colors"
                  >
                    <span>Website gốc</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </div>

                <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight mb-2">
                  {novel.title}
                </h1>
                <p className="text-xs sm:text-sm text-slate-400 font-medium mb-4">
                  Tác giả: <span className="text-slate-200">{novel.author}</span>
                </p>

                {novel.description && (
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3.5 text-xs text-slate-300 leading-relaxed mb-6 max-h-36 overflow-y-auto whitespace-pre-line">
                    {novel.description}
                  </div>
                )}
              </div>

              {/* Stats & Action Buttons */}
              <div>
                <div className="flex flex-wrap items-center gap-4 text-xs text-slate-400 mb-5">
                  <div>
                    Tổng số: <strong className="text-white font-mono">{novel.total_chapters}</strong> chương
                  </div>
                  <div>•</div>
                  <div>
                    Đã dịch:{" "}
                    <strong className="text-emerald-400 font-mono">
                      {translatedCount} / {novel.total_chapters}
                    </strong>{" "}
                    ({Math.round((translatedCount / Math.max(novel.total_chapters, 1)) * 100)}%)
                  </div>
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <button
                    onClick={handleTranslateSelected}
                    disabled={selectedChapterIds.length === 0 || bulkLoading}
                    className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-indigo-600/20 hover:opacity-95 disabled:opacity-40 transition-all"
                  >
                    <Sparkles className="h-4 w-4" />
                    <span>Dịch chương đã chọn ({selectedChapterIds.length})</span>
                  </button>

                  <button
                    onClick={handleTranslateAll}
                    disabled={bulkLoading}
                    className="flex items-center gap-2 rounded-xl border border-indigo-500/30 bg-indigo-500/10 px-4 py-2.5 text-xs font-bold text-indigo-300 hover:bg-indigo-500/20 transition-all"
                  >
                    <Layers className="h-4 w-4 text-cyan-400" />
                    <span>Dịch toàn bộ</span>
                  </button>

                  <button
                    onClick={() => setIsGlossaryModalOpen(true)}
                    className="flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-2.5 text-xs font-semibold text-slate-200 hover:border-amber-500/40 hover:text-amber-300 transition-colors"
                  >
                    <BookMarked className="h-4 w-4 text-amber-400" />
                    <span>Thuật ngữ / Glossary</span>
                  </button>

                  {translatedCount > 0 && (
                    <Link
                      href={`/reader/${chapters.find((c) => c.status === "completed")?.id}`}
                      className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-xs font-bold text-white shadow-lg shadow-emerald-600/20 hover:bg-emerald-500 transition-colors"
                    >
                      <BookOpen className="h-4 w-4" />
                      <span>Đọc truyện</span>
                    </Link>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Chapters Section */}
        <section className="rounded-3xl border border-slate-800/80 bg-slate-900/40 p-6 backdrop-blur-xl">
          {/* Controls Bar: Search, Filter, Sort, Selection */}
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 border-b border-slate-800/80 pb-5 mb-5">
            <div className="flex flex-wrap items-center gap-3">
              <h2 className="text-base font-bold text-white">Danh sách chương</h2>
              <span className="text-xs text-slate-400">({filteredChapters.length} chương)</span>

              <button
                onClick={handleSelectAllCurrentPage}
                className="rounded-lg border border-slate-800 bg-slate-800/60 px-2.5 py-1 text-xs font-medium text-slate-300 hover:border-slate-700 transition-colors"
              >
                {paginatedChapters.every((c) => selectedChapterIds.includes(c.id))
                  ? "Bỏ chọn trang này"
                  : "Chọn trang này"}
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2.5">
              {/* Search Chapter */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Tìm tên hoặc số chương..."
                  value={search}
                  onChange={(e) => {
                    setSearch(e.target.value);
                    setCurrentPage(1);
                  }}
                  className="rounded-xl border border-slate-800 bg-slate-950/60 pl-8 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none w-48 sm:w-56"
                />
              </div>

              {/* Status Filter */}
              <select
                value={filterStatus}
                onChange={(e) => {
                  setFilterStatus(e.target.value);
                  setCurrentPage(1);
                }}
                className="rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-1.5 text-xs text-slate-300 focus:border-indigo-500 focus:outline-none"
              >
                <option value="all">Tất cả trạng thái</option>
                <option value="completed">Đã dịch</option>
                <option value="pending">Chưa dịch</option>
                <option value="translating">Đang dịch</option>
                <option value="failed">Lỗi</option>
              </select>

              {/* Sort Order Toggle */}
              <button
                onClick={() => setSortOrder((prev) => (prev === "asc" ? "desc" : "asc"))}
                className="flex items-center gap-1 rounded-xl border border-slate-800 bg-slate-950/60 px-3 py-1.5 text-xs font-medium text-slate-300 hover:border-slate-700"
              >
                <ArrowUpDown className="h-3 w-3" />
                <span>{sortOrder === "asc" ? "Cũ nhất" : "Mới nhất"}</span>
              </button>
            </div>
          </div>

          {/* Chapters Table */}
          <div className="divide-y divide-slate-800/60">
            {paginatedChapters.length === 0 ? (
              <div className="py-12 text-center text-xs text-slate-500">
                Không tìm thấy chương nào phù hợp với bộ lọc.
              </div>
            ) : (
              paginatedChapters.map((chapter) => (
                <div
                  key={chapter.id}
                  className="flex items-center justify-between py-3 px-2 rounded-xl hover:bg-slate-800/40 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <input
                      type="checkbox"
                      checked={selectedChapterIds.includes(chapter.id)}
                      onChange={() => handleToggleChapter(chapter.id)}
                      className="h-4 w-4 rounded border-slate-700 bg-slate-800 text-indigo-600 focus:ring-0 focus:ring-offset-0"
                    />

                    <span className="font-mono text-xs font-semibold text-slate-400 w-12 shrink-0">
                      #{chapter.chapter_number}
                    </span>

                    <span className="text-xs font-medium text-white truncate max-w-sm sm:max-w-md lg:max-w-xl">
                      {chapter.title}
                    </span>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 ml-4">
                    {renderStatusBadge(chapter)}

                    {chapter.status === "completed" ? (
                      <Link
                        href={`/reader/${chapter.id}`}
                        className="rounded-lg bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/20 border border-emerald-500/20 transition-colors"
                      >
                        Đọc ngay
                      </Link>
                    ) : chapter.status === "translating" ? (
                      <button
                        onClick={() => {
                          setActiveJobChapterTitle(chapter.title);
                          setActiveJobChapterId(chapter.id);
                          setIsProgressModalOpen(true);
                        }}
                        className="rounded-lg bg-indigo-500/10 px-3 py-1 text-xs font-semibold text-indigo-300 hover:bg-indigo-500/20 border border-indigo-500/20 transition-colors"
                      >
                        Xem tiến trình
                      </button>
                    ) : (
                      <button
                        onClick={() => handleTranslateSingle(chapter)}
                        className="rounded-lg bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-300 hover:bg-indigo-600 hover:text-white transition-colors"
                      >
                        Dịch
                      </button>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-800/80 pt-5 mt-5 text-xs text-slate-400">
              <span>
                Trang {currentPage} / {totalPages}
              </span>

              <div className="flex items-center gap-2">
                <button
                  disabled={currentPage <= 1}
                  onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                  className="flex items-center gap-1 rounded-lg border border-slate-800 px-3 py-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-40 transition-colors"
                >
                  <ChevronLeft className="h-3.5 w-3.5" />
                  <span>Trang trước</span>
                </button>

                <button
                  disabled={currentPage >= totalPages}
                  onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                  className="flex items-center gap-1 rounded-lg border border-slate-800 px-3 py-1.5 text-slate-300 hover:bg-slate-800 disabled:opacity-40 transition-colors"
                >
                  <span>Trang sau</span>
                  <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )}
        </section>
      </main>

      {/* Realtime Translation Progress Modal */}
      <TranslationProgressModal
        isOpen={isProgressModalOpen}
        jobId={activeJobId}
        chapterTitle={activeJobChapterTitle}
        chapterId={activeJobChapterId}
        onClose={() => setIsProgressModalOpen(false)}
        onComplete={handleJobCompleted}
      />

      {/* Glossary Management Modal */}
      <GlossaryModal
        isOpen={isGlossaryModalOpen}
        novelId={novel.id}
        novelTitle={novel.title}
        onClose={() => setIsGlossaryModalOpen(false)}
      />
    </div>
  );
}
