"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { Loader2, CheckCircle2, AlertCircle, Sparkles, BookOpen, X } from "lucide-react";
import { api } from "@/lib/api";
import { TranslationJob } from "@/types";

interface Props {
  isOpen: boolean;
  jobId: string | null;
  chapterTitle?: string;
  chapterId?: number | null;
  onClose: () => void;
  onComplete?: (chapterId: number) => void;
}

export default function TranslationProgressModal({
  isOpen,
  jobId,
  chapterTitle,
  chapterId,
  onClose,
  onComplete,
}: Props) {
  const [job, setJob] = useState<TranslationJob | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    if (!isOpen || !jobId) {
      setJob(null);
      setError("");
      return;
    }

    setError("");
    const unsubscribe = api.subscribeJobProgress(
      jobId,
      (updatedJob) => {
        setJob(updatedJob);
        if (updatedJob.status === "completed" && chapterId && onComplete) {
          onComplete(chapterId);
        }
        if (updatedJob.status === "failed") {
          setError(updatedJob.error_message || updatedJob.error || "Quá trình dịch gặp sự cố.");
        }
      },
      (err) => {
        setError(err.message || "Không thể kết nối cập nhật tiến trình.");
      }
    );

    return () => {
      unsubscribe();
    };
  }, [isOpen, jobId, chapterId, onComplete]);

  if (!isOpen) return null;

  const percent = job?.progress_percent || 0;
  const isCompleted = job?.status === "completed";
  const isFailed = job?.status === "failed" || !!error;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl shadow-indigo-950/40">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-800/80 pb-4">
          <div className="flex items-center gap-2.5">
            <div className={`flex h-9 w-9 items-center justify-center rounded-xl ${
              isCompleted ? "bg-emerald-500/20 text-emerald-400" : isFailed ? "bg-red-500/20 text-red-400" : "bg-indigo-500/20 text-indigo-400"
            }`}>
              {isCompleted ? (
                <CheckCircle2 className="h-5 w-5" />
              ) : isFailed ? (
                <AlertCircle className="h-5 w-5" />
              ) : (
                <Loader2 className="h-5 w-5 animate-spin" />
              )}
            </div>
            <div>
              <h3 className="text-base font-bold text-white">
                {isCompleted ? "Dịch thành công!" : isFailed ? "Dịch gặp sự cố" : "Tiến trình dịch AI Realtime"}
              </h3>
              <p className="text-xs text-slate-400 truncate max-w-xs">{chapterTitle || "Chương truyện"}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Body Content */}
        <div className="my-6 space-y-4">
          {/* Status Message & Percentage */}
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-slate-300 flex items-center gap-2">
              {!isCompleted && !isFailed && <Sparkles className="h-3.5 w-3.5 text-indigo-400 animate-pulse" />}
              {job?.message || "Đang chuẩn bị hàng đợi..."}
            </span>
            <span className="font-mono text-base font-bold text-indigo-400">{percent}%</span>
          </div>

          {/* Progress Bar */}
          <div className="h-3 w-full overflow-hidden rounded-full bg-slate-800">
            <div
              className={`h-full transition-all duration-300 ease-out ${
                isCompleted
                  ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                  : isFailed
                  ? "bg-red-500"
                  : "bg-gradient-to-r from-indigo-500 via-indigo-400 to-cyan-400"
              }`}
              style={{ width: `${percent}%` }}
            />
          </div>

          {/* Chunk Counter */}
          {job && job.total_chunks > 0 && (
            <div className="flex items-center justify-between text-xs text-slate-400">
              <span>Phân đoạn:</span>
              <span className="font-mono font-semibold text-slate-200">
                {job.current_chunk} / {job.total_chunks} đoạn
              </span>
            </div>
          )}

          {/* Error Banner */}
          {isFailed && (
            <div className="rounded-xl border border-red-500/20 bg-red-500/10 p-3.5 text-xs text-red-300">
              <p className="font-semibold mb-1">❌ Không thể hoàn thành bản dịch:</p>
              <p className="text-red-400/90">{error || job?.error_message || "Đã xảy ra lỗi không xác định."}</p>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 border-t border-slate-800/80 pt-4">
          <button
            onClick={onClose}
            className="rounded-xl border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
          >
            Đóng
          </button>

          {isCompleted && chapterId && (
            <Link
              href={`/reader/${chapterId}`}
              className="flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-cyan-600 px-4 py-2 text-xs font-bold text-white shadow-lg shadow-indigo-600/30 hover:opacity-95 transition-opacity"
            >
              <BookOpen className="h-3.5 w-3.5" />
              <span>Đọc chương ngay</span>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
