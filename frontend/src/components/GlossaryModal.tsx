"use client";

import React, { useEffect, useState } from "react";
import { BookMarked, Plus, Trash2, X, Loader2 } from "lucide-react";
import { api } from "@/lib/api";
import { GlossaryItem } from "@/types";

interface Props {
  isOpen: boolean;
  novelId: number;
  novelTitle?: string;
  onClose: () => void;
}

export default function GlossaryModal({ isOpen, novelId, novelTitle, onClose }: Props) {
  const [terms, setTerms] = useState<GlossaryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [sourceTerm, setSourceTerm] = useState("");
  const [translatedTerm, setTranslatedTerm] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  const loadGlossary = async () => {
    try {
      setLoading(true);
      const data = await api.getGlossary(novelId);
      setTerms(data);
    } catch (err: any) {
      setError(err.message || "Không thể tải danh sách thuật ngữ.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isOpen && novelId) {
      loadGlossary();
    }
  }, [isOpen, novelId]);

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sourceTerm.trim() || !translatedTerm.trim()) return;

    try {
      setSubmitting(true);
      setError("");
      const newTerm = await api.addGlossaryTerm(novelId, sourceTerm.trim(), translatedTerm.trim(), note.trim());
      setTerms((prev) => {
        const filtered = prev.filter((t) => t.source_term !== newTerm.source_term);
        return [...filtered, newTerm];
      });
      setSourceTerm("");
      setTranslatedTerm("");
      setNote("");
    } catch (err: any) {
      setError(err.message || "Không thể lưu thuật ngữ.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (termId: number) => {
    try {
      await api.deleteGlossaryTerm(novelId, termId);
      setTerms((prev) => prev.filter((t) => t.id !== termId));
    } catch (err: any) {
      setError(err.message || "Không thể xóa thuật ngữ.");
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="relative w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between border-b border-slate-800/80 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-amber-500/20 text-amber-400">
              <BookMarked className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Thuật ngữ & Bộ nhớ dịch (Glossary)</h3>
              <p className="text-xs text-slate-400 truncate max-w-sm">Bộ truyện: {novelTitle || "Tiểu thuyết"}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-800 hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Info Box */}
        <div className="my-4 rounded-xl border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-300">
          💡 <strong>Translation Memory:</strong> Tên nhân vật, địa danh và thuật ngữ thêm vào đây sẽ được đưa vào lời nhắc AI, ép buộc dịch đồng nhất trong mọi chương truyện.
        </div>

        {error && (
          <div className="mb-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
            {error}
          </div>
        )}

        {/* Add Form */}
        <form onSubmit={handleAdd} className="mb-6 grid grid-cols-1 gap-3 sm:grid-cols-3">
          <div>
            <label className="block text-[11px] font-semibold text-slate-400 mb-1">Từ gốc (Tiếng Anh/Trung/Nhật)</label>
            <input
              type="text"
              placeholder="VD: 张三 hoặc Zhang San"
              value={sourceTerm}
              onChange={(e) => setSourceTerm(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-amber-500 focus:outline-none"
              required
            />
          </div>
          <div>
            <label className="block text-[11px] font-semibold text-slate-400 mb-1">Dịch sang tiếng Việt</label>
            <input
              type="text"
              placeholder="VD: Trương Tam"
              value={translatedTerm}
              onChange={(e) => setTranslatedTerm(e.target.value)}
              className="w-full rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-amber-500 focus:outline-none"
              required
            />
          </div>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <label className="block text-[11px] font-semibold text-slate-400 mb-1">Ghi chú (Tùy chọn)</label>
              <input
                type="text"
                placeholder="VD: Nhân vật chính"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-800/80 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-amber-500 focus:outline-none"
              />
            </div>
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center gap-1.5 rounded-xl bg-amber-600 px-3.5 py-2 text-xs font-bold text-white hover:bg-amber-500 disabled:opacity-50 transition-colors"
            >
              {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              <span>Thêm</span>
            </button>
          </div>
        </form>

        {/* Terms List */}
        <div className="max-h-60 overflow-y-auto space-y-2 rounded-xl border border-slate-800 bg-slate-950/60 p-3">
          {loading ? (
            <div className="flex items-center justify-center py-6 text-slate-500">
              <Loader2 className="h-5 w-5 animate-spin" />
            </div>
          ) : terms.length === 0 ? (
            <div className="py-6 text-center text-xs text-slate-500">
              Chưa có thuật ngữ nào. Bạn có thể thêm tên nhân vật để AI dịch chuẩn xác hơn.
            </div>
          ) : (
            terms.map((t) => (
              <div
                key={t.id}
                className="flex items-center justify-between rounded-lg border border-slate-800/80 bg-slate-900/60 px-3 py-2 text-xs transition-colors hover:border-slate-700"
              >
                <div className="flex items-center gap-3">
                  <span className="font-semibold text-slate-300 font-mono">{t.source_term}</span>
                  <span className="text-slate-500">→</span>
                  <span className="font-bold text-amber-400">{t.translated_term}</span>
                  {t.note && <span className="text-[11px] text-slate-500 italic">({t.note})</span>}
                </div>
                <button
                  onClick={() => handleDelete(t.id)}
                  className="rounded p-1 text-slate-500 hover:bg-red-500/10 hover:text-red-400 transition-colors"
                  title="Xóa thuật ngữ"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="mt-5 flex justify-end border-t border-slate-800/80 pt-4">
          <button
            onClick={onClose}
            className="rounded-xl border border-slate-700 bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white transition-colors"
          >
            Đóng
          </button>
        </div>
      </div>
    </div>
  );
}
