"use client";

import React, { useState, useEffect, useRef } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Settings2,
  BookOpen,
  ArrowLeft,
  Sun,
  Moon,
  Coffee,
  Type,
  Maximize2,
  Minimize2,
  Loader2,
  AlertCircle,
  Columns2,
  Sparkles,
  Home,
  List,
  Heart,
  AlertTriangle,
  ArrowUp,
  MessageSquare,
  Send,
  Info,
  CheckCircle2,
  RotateCcw,
} from "lucide-react";
import { api } from "@/lib/api";
import { ReaderData, Chapter } from "@/types";

type ThemeMode = "dark" | "sepia" | "light";

interface CommentItem {
  id: string;
  author: string;
  level: string;
  content: string;
  time: string;
  likes: number;
}

const DEFAULT_COMMENTS: CommentItem[] = [
  {
    id: "c1",
    author: "Bạch Tiêu Phàm",
    level: "Cấp 4 - Nguyên Anh",
    content: "Bản dịch AI này đỉnh thật sự, khung thoại xóa sạch bong không còn tí chữ tiếng Anh nào luôn!",
    time: "15 phút trước",
    likes: 12,
  },
  {
    id: "c2",
    author: "Mèo Thích Đọc Truyện",
    level: "Cấp 3 - Kim Đan",
    content: "Font chữ tiếng Việt bo tròn nhìn cưng ghê, vừa mắt hơn hẳn font mặc định.",
    time: "42 phút trước",
    likes: 8,
  },
  {
    id: "c3",
    author: "Tu Tiên Giả",
    level: "Cấp 2 - Trúc Cơ",
    content: "Hóng chap tiếp theo quá ad ơi, bộ này art đẹp mà dịch mượt đọc cuốn vãi!",
    time: "2 giờ trước",
    likes: 5,
  },
];

export default function ReaderPage() {
  const params = useParams();
  const router = useRouter();
  const chapterId = Number(params?.chapterId);

  const [data, setData] = useState<ReaderData | null>(null);
  const [allChapters, setAllChapters] = useState<Chapter[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // Reader Settings
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [fontSize, setFontSize] = useState<number>(18);
  const [lineHeight, setLineHeight] = useState<number>(1.8);
  const [maxWidth, setMaxWidth] = useState<"narrow" | "normal" | "wide" | "full">("normal");
  const [fontFamily, setFontFamily] = useState<"sans" | "serif">("sans");
  const [showOriginal, setShowOriginal] = useState<boolean>(false);
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [translateBubbles, setTranslateBubbles] = useState<boolean>(true);

  // NetTruyen Features
  const [followed, setFollowed] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportReason, setReportReason] = useState("Ảnh bị lỗi không hiển thị");
  const [reportSuccess, setReportSuccess] = useState(false);
  const [showScrollTop, setShowScrollTop] = useState(false);

  // Comments
  const [comments, setComments] = useState<CommentItem[]>(DEFAULT_COMMENTS);
  const [commentAuthor, setCommentAuthor] = useState("");
  const [commentText, setCommentText] = useState("");

  // Reading progress
  const [scrollPercent, setScrollPercent] = useState<number>(0);
  const contentRef = useRef<HTMLDivElement>(null);

  // Load Reader Preferences from localStorage
  useEffect(() => {
    try {
      const savedTheme = localStorage.getItem("reader_theme") as ThemeMode;
      if (savedTheme) setTheme(savedTheme);
      const savedSize = localStorage.getItem("reader_fontSize");
      if (savedSize) setFontSize(Number(savedSize));
      const savedLH = localStorage.getItem("reader_lineHeight");
      if (savedLH) setLineHeight(Number(savedLH));
      const savedWidth = localStorage.getItem("reader_maxWidth") as any;
      if (savedWidth) setMaxWidth(savedWidth);
      const savedFont = localStorage.getItem("reader_fontFamily") as any;
      if (savedFont) setFontFamily(savedFont);

      const savedAuthor = localStorage.getItem("comment_author");
      if (savedAuthor) setCommentAuthor(savedAuthor);
    } catch {}
  }, []);

  // Save settings on changes
  const updateSetting = (key: string, value: any, setter: (val: any) => void) => {
    setter(value);
    try {
      localStorage.setItem(`reader_${key}`, value.toString());
    } catch {}
  };

  // Fetch chapter reader content
  useEffect(() => {
    async function fetchChapter() {
      if (!chapterId) return;
      try {
        setLoading(true);
        setError("");
        const readerData = await api.getReaderContent(chapterId);
        setData(readerData);

        // Load stored comments for this chapter if any
        try {
          const savedComments = localStorage.getItem(`comments_chap_${chapterId}`);
          if (savedComments) {
            setComments(JSON.parse(savedComments));
          } else {
            setComments(DEFAULT_COMMENTS);
          }
        } catch {}

        // Restore scroll position after render
        setTimeout(() => {
          try {
            const savedPos = localStorage.getItem(`reader_pos_${chapterId}`);
            if (savedPos) {
              window.scrollTo({ top: Number(savedPos), behavior: "smooth" });
            }
          } catch {}
        }, 150);
      } catch (err: any) {
        setError(err.message || "Không thể tải nội dung chương truyện.");
      } finally {
        setLoading(false);
      }
    }
    fetchChapter();
  }, [chapterId]);

  // Fetch all chapters of this novel for the NetTruyen dropdown selector
  useEffect(() => {
    if (!data?.novel_id) return;
    api
      .getNovelChapters(data.novel_id, 500, 0, "asc")
      .then((chaps) => setAllChapters(chaps))
      .catch(() => {});

    try {
      const savedFollow = localStorage.getItem(`follow_novel_${data.novel_id}`);
      if (savedFollow === "true") setFollowed(true);
    } catch {}
  }, [data?.novel_id]);

  // NetTruyen Keyboard Navigation: ArrowLeft (←) for Prev, ArrowRight (→) for Next
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger when user is typing in form inputs
      const tagName = (e.target as HTMLElement)?.tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(tagName)) return;

      if (e.key === "ArrowLeft" && data?.prev_chapter_id) {
        router.push(`/reader/${data.prev_chapter_id}`);
      } else if (e.key === "ArrowRight" && data?.next_chapter_id) {
        router.push(`/reader/${data.next_chapter_id}`);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [data?.prev_chapter_id, data?.next_chapter_id, router]);

  // Automatic scroll position restoration


  // Track and save scroll position & toggle Floating Top Button
  useEffect(() => {
    const handleScroll = () => {
      const total = document.documentElement.scrollHeight - window.innerHeight;
      const current = window.scrollY;
      if (total > 0) {
        setScrollPercent(Math.min(100, Math.round((current / total) * 100)));
      }
      setShowScrollTop(current > 350);

      if (chapterId) {
        try {
          localStorage.setItem(`reader_pos_${chapterId}`, current.toString());
        } catch {}
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, [chapterId]);

  // Handle posting comment
  const handlePostComment = (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;

    const authorName = commentAuthor.trim() || "Độc giả ẩn danh";
    const newComment: CommentItem = {
      id: "c_" + Date.now(),
      author: authorName,
      level: "Cấp 1 - Luyện Khí",
      content: commentText.trim(),
      time: "Vừa xong",
      likes: 1,
    };

    const updated = [newComment, ...comments];
    setComments(updated);
    setCommentText("");

    try {
      localStorage.setItem("comment_author", authorName);
      localStorage.setItem(`comments_chap_${chapterId}`, JSON.stringify(updated));
    } catch {}
  };

  // Theme styling helpers (NetTruyen authentic dark tone)
  const getThemeClasses = () => {
    switch (theme) {
      case "light":
        return {
          bg: "bg-[#F5F6F8] text-[#1E293B]",
          navBg: "bg-white/95 border-slate-200",
          cardBg: "bg-white border-slate-200",
          subtext: "text-slate-500",
          dialogue: "text-indigo-900 font-medium",
          toolbarBg: "bg-white border-slate-200 text-slate-800",
        };
      case "sepia":
        return {
          bg: "bg-[#F4ECD8] text-[#382E25]",
          navBg: "bg-[#EAE0CA]/95 border-[#D8CBB0]",
          cardBg: "bg-[#EFE5CE] border-[#D8CBB0]",
          subtext: "text-[#706253]",
          dialogue: "text-[#854D0E] font-medium",
          toolbarBg: "bg-[#EFE5CE] border-[#D8CBB0] text-[#382E25]",
        };
      default: // Dark mode NetTruyen
        return {
          bg: "bg-[#14151a] text-[#E2E8F0]",
          navBg: "bg-[#191a21]/95 border-slate-800",
          cardBg: "bg-[#1d1f28] border-slate-800",
          subtext: "text-slate-400",
          dialogue: "text-cyan-300 font-medium",
          toolbarBg: "bg-[#1a1c24] border-slate-800 text-slate-200",
        };
    }
  };

  const getMaxWidthClass = () => {
    switch (maxWidth) {
      case "narrow":
        return "max-w-2xl";
      case "wide":
        return "max-w-5xl";
      case "full":
        return "max-w-none w-full px-0 sm:px-4";
      default: // normal
        return "max-w-3xl";
    }
  };

  const themeClasses = getThemeClasses();

  if (loading) {
    return (
      <div className={`min-h-screen ${themeClasses.bg} flex items-center justify-center`}>
        <div className="text-center">
          <Loader2 className="h-9 w-9 animate-spin text-rose-500 mx-auto mb-3" />
          <p className="text-sm font-medium text-slate-400">Đang tải nội dung chương truyện...</p>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className={`min-h-screen ${themeClasses.bg} flex items-center justify-center p-4`}>
        <div className="text-center max-w-md rounded-2xl border border-rose-500/30 bg-rose-500/10 p-8">
          <AlertCircle className="h-10 w-10 text-rose-400 mx-auto mb-3" />
          <h2 className="text-base font-bold mb-2">Không thể tải chương truyện</h2>
          <p className="text-xs text-rose-300 mb-6">{error || "Chương truyện không tồn tại."}</p>
          <button
            onClick={() => router.back()}
            className="rounded-xl bg-slate-800 px-5 py-2 text-xs font-semibold text-white hover:bg-slate-700"
          >
            Quay lại
          </button>
        </div>
      </div>
    );
  }

  const translatedParagraphs = (data.translated_text || data.original_text || "")
    .split("\n\n")
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  const originalParagraphs = (data.original_text || "")
    .split("\n\n")
    .map((p) => p.trim())
    .filter((p) => p.length > 0);

  // Reusable NetTruyen Chapter Toolbar component
  const renderNetTruyenToolbar = (isBottom = false) => (
    <div
      className={`flex flex-wrap items-center justify-center gap-2 sm:gap-3 py-3 px-3 sm:px-5 rounded-2xl border shadow-lg backdrop-blur-md ${themeClasses.toolbarBg} transition-all`}
    >
      {/* Home Button */}
      <Link
        href="/"
        className="p-2 sm:px-3 sm:py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all flex items-center gap-1.5 text-xs font-medium"
        title="Trang chủ"
      >
        <Home className="h-4 w-4 text-slate-400" />
        <span className="hidden sm:inline">Trang chủ</span>
      </Link>

      {/* Index / Table of Contents Button */}
      <Link
        href={`/novel/${data.novel_id}`}
        className="p-2 sm:px-3 sm:py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-all flex items-center gap-1.5 text-xs font-medium"
        title="Mục lục truyện"
      >
        <List className="h-4 w-4 text-slate-400" />
        <span className="hidden sm:inline">Mục lục</span>
      </Link>

      {/* Prev Chapter Button */}
      <button
        disabled={!data.prev_chapter_id}
        onClick={() => router.push(`/reader/${data.prev_chapter_id}`)}
        className="px-3 sm:px-4 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-30 disabled:hover:bg-rose-600 text-white font-bold text-xs flex items-center gap-1 transition-all shadow-md shadow-rose-600/20 active:scale-95"
        title="Chương trước (Phím ←)"
      >
        <ChevronLeft className="h-4 w-4" />
        <span>Chap trước</span>
      </button>

      {/* Chapter Dropdown Select (NetTruyen classic dropdown) */}
      <div className="relative min-w-[130px] sm:min-w-[170px]">
        <select
          value={chapterId}
          onChange={(e) => router.push(`/reader/${e.target.value}`)}
          className="w-full appearance-none rounded-xl bg-slate-800 border border-slate-700 hover:border-slate-600 px-3 py-1.5 pr-8 text-xs font-semibold text-white focus:outline-none focus:ring-2 focus:ring-rose-500 cursor-pointer transition-all truncate"
        >
          {allChapters.length > 0 ? (
            allChapters.map((c) => (
              <option key={c.id} value={c.id}>
                Chương {c.chapter_number} {c.id === chapterId ? "★ (Đang đọc)" : ""}
              </option>
            ))
          ) : (
            <option value={chapterId}>Chương {data.chapter_number} (Đang đọc)</option>
          )}
        </select>
        <ChevronDown className="h-3.5 w-3.5 text-slate-400 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
      </div>

      {/* Next Chapter Button */}
      <button
        disabled={!data.next_chapter_id}
        onClick={() => router.push(`/reader/${data.next_chapter_id}`)}
        className="px-3 sm:px-4 py-1.5 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-30 disabled:hover:bg-rose-600 text-white font-bold text-xs flex items-center gap-1 transition-all shadow-md shadow-rose-600/20 active:scale-95"
        title="Chương sau (Phím →)"
      >
        <span>Chap sau</span>
        <ChevronRight className="h-4 w-4" />
      </button>

      {/* Follow Button (Theo dõi) */}
      <button
        onClick={() => {
          const nextFollow = !followed;
          setFollowed(nextFollow);
          try {
            localStorage.setItem(`follow_novel_${data.novel_id}`, nextFollow ? "true" : "false");
          } catch {}
        }}
        className={`px-3 py-1.5 rounded-xl border text-xs font-semibold flex items-center gap-1.5 transition-all ${
          followed
            ? "bg-rose-600/25 border-rose-500 text-rose-400 shadow-sm"
            : "bg-slate-800 hover:bg-slate-700 border-slate-700 text-slate-300"
        }`}
        title="Theo dõi bộ truyện này"
      >
        <Heart className={`h-3.5 w-3.5 ${followed ? "fill-rose-500 text-rose-500" : ""}`} />
        <span className="hidden sm:inline">{followed ? "Đã theo dõi" : "Theo dõi"}</span>
      </button>

      {/* Report Button (Báo lỗi) */}
      <button
        onClick={() => setShowReportModal(true)}
        className="px-2.5 sm:px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-amber-400 text-xs font-semibold flex items-center gap-1 transition-all"
        title="Báo lỗi chương truyện"
      >
        <AlertTriangle className="h-3.5 w-3.5 text-amber-400" />
        <span className="hidden md:inline">Báo lỗi</span>
      </button>

      {/* Comic Bubble Translation Toggle Button */}
      <button
        onClick={() => setTranslateBubbles(!translateBubbles)}
        className={`rounded-xl px-2.5 py-1.5 text-xs font-semibold flex items-center gap-1.5 transition-all ${
          translateBubbles
            ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-sm"
            : "hover:bg-black/10 text-slate-400 border border-slate-700/50"
        }`}
        title="Bật/Tắt dịch lời thoại trực tiếp trong bóng thoại"
      >
        <Sparkles className="h-3.5 w-3.5" />
        <span className="hidden sm:inline">{translateBubbles ? "Dịch AI: BẬT" : "Dịch AI: TẮT"}</span>
      </button>

      {/* Settings Toggle (Only on top bar) */}
      {!isBottom && (
        <button
          onClick={() => setShowSettings(!showSettings)}
          className={`rounded-xl p-1.5 transition-colors ${
            showSettings ? "bg-rose-600 text-white" : "bg-slate-800 hover:bg-slate-700 text-slate-300"
          }`}
          title="Cài đặt hiển thị"
        >
          <Settings2 className="h-4 w-4" />
        </button>
      )}
    </div>
  );

  return (
    <div className={`min-h-screen ${themeClasses.bg} transition-colors duration-200 flex flex-col font-${fontFamily}`}>
      {/* Top Reading Progress Bar */}
      <div className="fixed top-0 left-0 right-0 z-50 h-1 bg-transparent">
        <div
          className="h-full bg-gradient-to-r from-rose-500 via-amber-400 to-rose-400 transition-all duration-150"
          style={{ width: `${scrollPercent}%` }}
        />
      </div>

      {/* NetTruyen Compact Top Navbar */}
      <header className={`sticky top-0 z-40 w-full border-b backdrop-blur-md ${themeClasses.navBg}`}>
        <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-3 sm:px-6">
          <div className="flex items-center gap-3">
            <Link
              href={`/novel/${data.novel_id}`}
              className="flex items-center gap-1.5 rounded-lg p-1.5 hover:bg-black/10 transition-colors"
              title="Quay lại mục lục truyện"
            >
              <ArrowLeft className="h-4 w-4 text-slate-400" />
              <span className="hidden sm:inline text-xs font-semibold">Mục lục</span>
            </Link>

            <span className="hidden md:inline text-xs text-slate-500">|</span>
            <span className="text-xs font-bold truncate max-w-[160px] sm:max-w-md text-white">
              {data.novel_title}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-semibold px-2 py-0.5 rounded-md bg-rose-600/20 text-rose-400 border border-rose-500/30">
              Chương {data.chapter_number}
            </span>

            <button
              onClick={() => setShowSettings(!showSettings)}
              className={`rounded-lg p-1.5 transition-colors ${
                showSettings ? "bg-rose-600 text-white" : "hover:bg-black/10 text-slate-300"
              }`}
              title="Cài đặt giao diện đọc"
            >
              <Settings2 className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Settings Drawer */}
        {showSettings && (
          <div className={`border-t px-4 py-4 shadow-xl ${themeClasses.cardBg} transition-all`}>
            <div className="mx-auto max-w-5xl grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 text-xs">
              {/* Theme Selector */}
              <div>
                <label className={`block font-semibold mb-1.5 ${themeClasses.subtext}`}>Màu nền đọc</label>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => updateSetting("theme", "dark", setTheme)}
                    className={`flex-1 flex items-center justify-center gap-1 rounded-lg py-1.5 border ${
                      theme === "dark" ? "border-rose-500 bg-slate-800 text-white font-bold" : "border-slate-700 text-slate-400"
                    }`}
                  >
                    <Moon className="h-3 w-3" />
                    <span>Tối</span>
                  </button>
                  <button
                    onClick={() => updateSetting("theme", "sepia", setTheme)}
                    className={`flex-1 flex items-center justify-center gap-1 rounded-lg py-1.5 border ${
                      theme === "sepia" ? "border-amber-600 bg-[#E8DCBF] text-[#382E25] font-bold" : "border-[#D8CBB0] text-[#706253]"
                    }`}
                  >
                    <Coffee className="h-3 w-3" />
                    <span>Sepia</span>
                  </button>
                  <button
                    onClick={() => updateSetting("theme", "light", setTheme)}
                    className={`flex-1 flex items-center justify-center gap-1 rounded-lg py-1.5 border ${
                      theme === "light" ? "border-slate-400 bg-slate-200 text-slate-900 font-bold" : "border-slate-300 text-slate-500"
                    }`}
                  >
                    <Sun className="h-3 w-3" />
                    <span>Sáng</span>
                  </button>
                </div>
              </div>

              {/* Font Size */}
              <div>
                <label className={`block font-semibold mb-1.5 ${themeClasses.subtext}`}>Cỡ chữ ({fontSize}px)</label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => updateSetting("fontSize", Math.max(14, fontSize - 2), setFontSize)}
                    className="rounded-lg border px-2.5 py-1 font-bold hover:bg-black/10"
                  >
                    A-
                  </button>
                  <span className="font-mono text-center flex-1">{fontSize}</span>
                  <button
                    onClick={() => updateSetting("fontSize", Math.min(26, fontSize + 2), setFontSize)}
                    className="rounded-lg border px-2.5 py-1 font-bold hover:bg-black/10"
                  >
                    A+
                  </button>
                </div>
              </div>

              {/* Font Family */}
              <div>
                <label className={`block font-semibold mb-1.5 ${themeClasses.subtext}`}>Kiểu chữ</label>
                <div className="flex items-center gap-1.5">
                  <button
                    onClick={() => updateSetting("fontFamily", "sans", setFontFamily)}
                    className={`flex-1 rounded-lg py-1.5 border text-center font-sans ${
                      fontFamily === "sans" ? "border-rose-500 bg-rose-600/20 text-rose-400 font-bold" : "border-slate-700 opacity-60"
                    }`}
                  >
                    Không chân
                  </button>
                  <button
                    onClick={() => updateSetting("fontFamily", "serif", setFontFamily)}
                    className={`flex-1 rounded-lg py-1.5 border text-center font-serif ${
                      fontFamily === "serif" ? "border-rose-500 bg-rose-600/20 text-rose-400 font-bold" : "border-slate-700 opacity-60"
                    }`}
                  >
                    Có chân
                  </button>
                </div>
              </div>

              {/* Width Selector */}
              <div>
                <label className={`block font-semibold mb-1.5 ${themeClasses.subtext}`}>Khung đọc tranh</label>
                <div className="grid grid-cols-4 gap-1">
                  <button
                    onClick={() => updateSetting("maxWidth", "narrow", setMaxWidth)}
                    className={`rounded-lg py-1 border text-center ${
                      maxWidth === "narrow" ? "border-rose-500 bg-rose-600/20 text-rose-300 font-bold" : "border-slate-700 opacity-60"
                    }`}
                  >
                    Hẹp
                  </button>
                  <button
                    onClick={() => updateSetting("maxWidth", "normal", setMaxWidth)}
                    className={`rounded-lg py-1 border text-center ${
                      maxWidth === "normal" ? "border-rose-500 bg-rose-600/20 text-rose-300 font-bold" : "border-slate-700 opacity-60"
                    }`}
                  >
                    Vừa
                  </button>
                  <button
                    onClick={() => updateSetting("maxWidth", "wide", setMaxWidth)}
                    className={`rounded-lg py-1 border text-center ${
                      maxWidth === "wide" ? "border-rose-500 bg-rose-600/20 text-rose-300 font-bold" : "border-slate-700 opacity-60"
                    }`}
                  >
                    Rộng
                  </button>
                  <button
                    onClick={() => updateSetting("maxWidth", "full", setMaxWidth)}
                    className={`rounded-lg py-1 border text-center ${
                      maxWidth === "full" ? "border-rose-500 bg-rose-600/20 text-rose-300 font-bold" : "border-slate-700 opacity-60"
                    }`}
                  >
                    Full
                  </button>
                </div>
              </div>

              {/* Bilingual View Toggle */}
              <div>
                <label className={`block font-semibold mb-1.5 ${themeClasses.subtext}`}>Chế độ hiển thị</label>
                <button
                  onClick={() => setShowOriginal(!showOriginal)}
                  className={`w-full flex items-center justify-center gap-1.5 rounded-lg py-1.5 border transition-colors ${
                    showOriginal ? "border-rose-500 bg-rose-600/20 text-rose-400 font-bold" : "border-slate-700 hover:bg-black/10"
                  }`}
                >
                  <Columns2 className="h-3 w-3" />
                  <span>{showOriginal ? "Song ngữ" : "Tiếng Việt"}</span>
                </button>
              </div>
            </div>
          </div>
        )}
      </header>

      {/* Reader Main Content */}
      <main className="flex-1 mx-auto w-full px-2 sm:px-4 py-6 max-w-7xl">
        {/* NetTruyen Breadcrumbs */}
        <div className="flex items-center gap-2 text-xs text-slate-400 mb-3 flex-wrap">
          <Link href="/" className="hover:text-rose-400 transition-colors flex items-center gap-1">
            <Home className="h-3.5 w-3.5 text-slate-400" /> Trang chủ
          </Link>
          <span>/</span>
          <Link
            href={`/novel/${data.novel_id}`}
            className="hover:text-rose-400 transition-colors max-w-xs truncate font-medium text-slate-300"
          >
            {data.novel_title}
          </Link>
          <span>/</span>
          <span className="text-rose-400 font-semibold">Chương {data.chapter_number}</span>
        </div>

        {/* Chapter Title & Update Time Header */}
        <div className="text-center mb-4">
          <h1 className="text-lg sm:text-2xl md:text-3xl font-extrabold uppercase tracking-tight text-white mb-1.5">
            {data.novel_title} - Chương {data.chapter_number}
          </h1>
          {data.translated_title && data.translated_title !== data.chapter_title && (
            <p className="text-sm font-semibold text-rose-400 mb-1">
              {data.translated_title}
            </p>
          )}
          <p className="text-xs text-slate-400 italic">
            [Cập nhật lúc: {new Date().toLocaleDateString("vi-VN")}]
          </p>
        </div>

        {/* NetTruyen Notification / Tip Box */}
        <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-3.5 text-xs text-amber-200/90 mb-5 flex items-start gap-2.5 shadow-sm">
          <Info className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p>
              <span className="font-semibold text-amber-300">💡 Mẹo đọc truyện:</span> Sử dụng phím mũi tên{" "}
              <strong>Trái (←)</strong> hoặc <strong>Phải (→)</strong> trên bàn phím để chuyển chapter nhanh!
            </p>
            <p className="text-amber-200/70 text-[11px]">
              Nếu tranh bị mờ hoặc chữ dịch chưa chuẩn, vui lòng bấm nút <strong>Báo lỗi</strong> để hệ thống tự động xử lý lại.
            </p>
          </div>
        </div>

        {/* Top NetTruyen Toolbar */}
        <div className="mb-6">{renderNetTruyenToolbar(false)}</div>

        {/* Content Paragraphs / Webtoon Comic Canvas */}
        <div className={`mx-auto ${getMaxWidthClass()}`}>
          <article
            ref={contentRef}
            className="leading-relaxed selection:bg-rose-500/30"
            style={{
              fontSize: `${fontSize}px`,
              lineHeight: lineHeight,
              fontFamily:
                fontFamily === "serif"
                  ? '"Lora", "Merriweather", "Georgia", "Times New Roman", serif'
                  : '"Be Vietnam Pro", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif',
            }}
          >
            {(() => {
              type ContentBlock =
                | { type: "images"; urls: string[]; startIndex: number }
                | { type: "text"; text: string; origText?: string; index: number };

              // 1. Normalize line breaks
              let transText = (data.translated_text || data.original_text || "")
                .replace(/\r\n/g, "\n")
                .replace(/\r/g, "\n");
              const origText = (data.original_text || "")
                .replace(/\r\n/g, "\n")
                .replace(/\r/g, "\n");

              // Extract any original image URLs
              const origImgUrls: string[] = [];
              const origImgRegex = /\[IMG:\s*([^\]]+?)\s*\]/g;
              let origMatch: RegExpExecArray | null;
              while ((origMatch = origImgRegex.exec(origText)) !== null) {
                origImgUrls.push(origMatch[1].trim());
              }

              // Restore images from [Minh họa X] or [Illustration X] if present
              if (origImgUrls.length > 0 && !transText.includes("[IMG:")) {
                transText = transText.replace(
                  /\[(?:Minh họa|Illustration|Minh hoạ|Minh hoa)\s*(\d+)\]/gi,
                  (m, idx) => {
                    const num = parseInt(idx, 10);
                    return num < origImgUrls.length ? `[IMG:${origImgUrls[num]}]` : m;
                  }
                );
                // If translation stripped images but original had them, restore
                if (!transText.includes("[IMG:")) {
                  transText = transText + "\n\n" + origImgUrls.map((u) => `[IMG:${u}]`).join("\n\n");
                }
              }

              // Original paragraphs for bilingual view
              const origParas = origText
                .split(/\n\s*\n/)
                .map((p) => p.trim())
                .filter(Boolean);

              const contentBlocks: ContentBlock[] = [];
              const imgRegex = /\[IMG:\s*([^\]]+?)\s*\]/g;
              let lastIdx = 0;
              let match: RegExpExecArray | null;
              let textBlockCount = 0;

              while ((match = imgRegex.exec(transText)) !== null) {
                const textBefore = transText.substring(lastIdx, match.index).trim();
                if (textBefore) {
                  const paras = textBefore.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
                  for (const p of paras) {
                    contentBlocks.push({
                      type: "text",
                      text: p,
                      origText: origParas[textBlockCount],
                      index: contentBlocks.length,
                    });
                    textBlockCount++;
                  }
                }

                const url = match[1].trim();
                const lastBlock = contentBlocks[contentBlocks.length - 1];
                if (lastBlock && lastBlock.type === "images") {
                  lastBlock.urls.push(url);
                } else {
                  contentBlocks.push({
                    type: "images",
                    urls: [url],
                    startIndex: contentBlocks.length,
                  });
                }

                lastIdx = imgRegex.lastIndex;
              }

              const textAfter = transText.substring(lastIdx).trim();
              if (textAfter) {
                const paras = textAfter.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
                for (const p of paras) {
                  contentBlocks.push({
                    type: "text",
                    text: p,
                    origText: origParas[textBlockCount],
                    index: contentBlocks.length,
                  });
                  textBlockCount++;
                }
              }

              const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

              return contentBlocks.map((block) => {
                if (block.type === "images") {
                  return (
                    <div
                      key={`img_strip_${block.startIndex}_${translateBubbles}`}
                      className="flex flex-col items-center w-full m-0 p-0 shadow-2xl bg-black rounded-lg overflow-hidden"
                      style={{ gap: 0 }}
                    >
                      {block.urls.map((rawImgUrl, subIdx) => {
                        const proxiedImgUrl = `${apiBase}/proxy/image?url=${encodeURIComponent(rawImgUrl)}&translate=${translateBubbles ? "true" : "false"}`;

                        return (
                          <div
                            key={subIdx}
                            className="relative w-full group flex justify-center items-center m-0 p-0 min-h-[260px] sm:min-h-[480px] bg-slate-900/60"
                          >
                            <img
                              src={proxiedImgUrl}
                              alt={`Trang ${subIdx + 1}`}
                              referrerPolicy="no-referrer"
                              loading={subIdx < 3 ? "eager" : "lazy"}
                              className="w-full block m-0 p-0 rounded-none border-0 shadow-none transition-opacity duration-200"
                              style={{ display: "block", margin: 0, padding: 0 }}
                              onError={(e) => {
                                const imgEl = e.target as HTMLImageElement;
                                if (!imgEl) return;
                                const retryCount = Number(imgEl.dataset.retry || 0);
                                const fallbackUrl = `${apiBase}/proxy/image?url=${encodeURIComponent(rawImgUrl)}&translate=false`;
                                if (retryCount === 0) {
                                  imgEl.dataset.retry = "1";
                                  // Fallback to proxy without translation (100% reliable)
                                  imgEl.src = fallbackUrl;
                                } else if (retryCount === 1) {
                                  imgEl.dataset.retry = "2";
                                  setTimeout(() => {
                                    imgEl.src = `${fallbackUrl}&retry=1`;
                                  }, 1500);
                                }
                              }}
                            />
                            {/* NetTruyen Page Number Indicator in Corner */}
                            <span className="absolute bottom-2 right-2 px-2 py-0.5 rounded bg-black/60 backdrop-blur-sm text-[10px] font-mono text-slate-300 opacity-40 group-hover:opacity-100 transition-opacity pointer-events-none">
                              {subIdx + 1} / {block.urls.length}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  );
                }

                const isDialogue =
                  block.text.startsWith('"') ||
                  block.text.startsWith('“') ||
                  block.text.startsWith('「') ||
                  block.text.startsWith('『') ||
                  block.text.startsWith('—') ||
                  block.text.startsWith('-');

                return (
                  <div key={`text_${block.index}`} className="group transition-opacity my-6 px-4">
                    <p className={`${isDialogue ? themeClasses.dialogue : ""} tracking-normal text-justify`}>
                      {block.text}
                    </p>
                    {showOriginal && block.origText && (
                      <p className={`mt-1.5 text-xs italic ${themeClasses.subtext} border-l-2 border-slate-500/30 pl-3`}>
                        {block.origText}
                      </p>
                    )}
                  </div>
                );
              });
            })()}
          </article>
        </div>

        {/* Bottom NetTruyen Toolbar */}
        <div className="mt-10 mb-12">{renderNetTruyenToolbar(true)}</div>

        {/* NetTruyen Comments Section */}
        <div className="mx-auto max-w-4xl mt-12 pt-8 border-t border-slate-800">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-rose-500" />
              <h2 className="text-base sm:text-lg font-bold text-white">
                Bình Luận ({comments.length})
              </h2>
            </div>
            <span className="text-xs text-slate-400">NetTruyen Community</span>
          </div>

          {/* Comment Form */}
          <form onSubmit={handlePostComment} className="mb-8 rounded-2xl bg-slate-900/80 border border-slate-800 p-4 shadow-lg">
            <div className="mb-3">
              <input
                type="text"
                placeholder="Tên của bạn (hoặc để trống làm ẩn danh)..."
                value={commentAuthor}
                onChange={(e) => setCommentAuthor(e.target.value)}
                className="w-full sm:w-72 rounded-xl bg-slate-800 border border-slate-700 px-3.5 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500 transition-all"
              />
            </div>
            <div className="mb-3">
              <textarea
                rows={3}
                placeholder="Viết bình luận của bạn về chương truyện này..."
                value={commentText}
                onChange={(e) => setCommentText(e.target.value)}
                className="w-full rounded-xl bg-slate-800 border border-slate-700 p-3.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-rose-500 transition-all"
              />
            </div>
            <div className="flex justify-end">
              <button
                type="submit"
                disabled={!commentText.trim()}
                className="px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 disabled:opacity-40 text-white font-bold text-xs flex items-center gap-1.5 transition-all shadow-md shadow-rose-600/20 active:scale-95"
              >
                <Send className="h-3.5 w-3.5" />
                <span>Gửi bình luận</span>
              </button>
            </div>
          </form>

          {/* Comment List */}
          <div className="space-y-4">
            {comments.map((c) => (
              <div key={c.id} className="rounded-2xl bg-slate-900/50 border border-slate-800/80 p-4 flex gap-3.5 transition-all hover:border-slate-700">
                <div className="h-9 w-9 rounded-full bg-gradient-to-br from-rose-500 to-amber-500 flex items-center justify-center font-bold text-white text-xs shrink-0 shadow-md">
                  {c.author.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="font-bold text-xs text-white truncate">{c.author}</span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 font-medium">
                      {c.level}
                    </span>
                    <span className="text-[11px] text-slate-500 ml-auto">{c.time}</span>
                  </div>
                  <p className="text-xs text-slate-300 leading-relaxed mb-2">{c.content}</p>
                  <div className="flex items-center gap-3 text-[11px] text-slate-500">
                    <button className="hover:text-rose-400 flex items-center gap-1 transition-colors">
                      <Heart className="h-3 w-3" />
                      <span>{c.likes}</span>
                    </button>
                    <button className="hover:text-slate-300 transition-colors">Trả lời</button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* NetTruyen Floating Quick Bar (Bottom-Right on Scroll) */}
      {showScrollTop && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 p-1.5 rounded-2xl bg-slate-900/90 border border-slate-700 shadow-2xl backdrop-blur-md transition-all">
          <button
            disabled={!data.prev_chapter_id}
            onClick={() => router.push(`/reader/${data.prev_chapter_id}`)}
            className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-white transition-all"
            title="Chương trước"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button
            disabled={!data.next_chapter_id}
            onClick={() => router.push(`/reader/${data.next_chapter_id}`)}
            className="p-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-white transition-all"
            title="Chương sau"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
          <button
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="p-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white transition-all shadow-md shadow-rose-600/30"
            title="Cuộn lên đầu trang"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* NetTruyen Report Modal */}
      {showReportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-3xl bg-slate-900 border border-slate-800 p-6 shadow-2xl">
            <div className="flex items-center gap-2 text-rose-400 mb-3">
              <AlertTriangle className="h-5 w-5" />
              <h3 className="font-bold text-sm text-white">Báo lỗi chương {data.chapter_number}</h3>
            </div>
            <p className="text-xs text-slate-400 mb-4">
              Vui lòng chọn loại lỗi bạn gặp phải để đội ngũ hỗ trợ kiểm tra và xử lý:
            </p>

            {reportSuccess ? (
              <div className="py-6 text-center">
                <CheckCircle2 className="h-10 w-10 text-emerald-400 mx-auto mb-2" />
                <p className="text-sm font-bold text-white mb-1">Đã ghi nhận báo lỗi!</p>
                <p className="text-xs text-slate-400 mb-4">Hệ thống đang tiến hành kiểm tra lại chương này.</p>
                <button
                  onClick={() => {
                    setShowReportModal(false);
                    setReportSuccess(false);
                  }}
                  className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-white"
                >
                  Đóng
                </button>
              </div>
            ) : (
              <div className="space-y-2 mb-6">
                {[
                  "Ảnh bị lỗi không hiển thị hoặc bị mờ",
                  "Chữ dịch bị đè lên lời thoại cũ",
                  "Lỗi font chữ / thiếu dấu tiếng Việt",
                  "Thiếu trang tranh hoặc sai thứ tự trang",
                  "Khác...",
                ].map((reason) => (
                  <label
                    key={reason}
                    className={`flex items-center gap-2.5 p-2.5 rounded-xl border cursor-pointer text-xs transition-all ${
                      reportReason === reason
                        ? "bg-rose-600/20 border-rose-500 text-rose-300 font-semibold"
                        : "bg-slate-800/50 border-slate-700/60 text-slate-300 hover:bg-slate-800"
                    }`}
                  >
                    <input
                      type="radio"
                      name="report_reason"
                      checked={reportReason === reason}
                      onChange={() => setReportReason(reason)}
                      className="accent-rose-500"
                    />
                    <span>{reason}</span>
                  </label>
                ))}
              </div>
            )}

            {!reportSuccess && (
              <div className="flex items-center justify-end gap-2">
                <button
                  onClick={() => setShowReportModal(false)}
                  className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-300"
                >
                  Hủy
                </button>
                <button
                  onClick={() => setReportSuccess(true)}
                  className="px-5 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-xs font-bold text-white shadow-md shadow-rose-600/30"
                >
                  Gửi báo cáo
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
