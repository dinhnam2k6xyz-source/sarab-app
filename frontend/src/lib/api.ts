import {
  Novel,
  Chapter,
  AnalyzeResult,
  TranslationJob,
  BulkTranslateResponse,
  ReaderData,
  GlossaryItem,
} from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

class ApiService {
  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${API_BASE}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    try {
      const res = await fetch(url, { ...options, headers });
      const data = await res.json().catch(() => null);

      if (!res.ok) {
        let errorMsg = "Không thể kết nối đến máy chủ. Vui lòng kiểm tra lại.";
        let errorCode = "UNKNOWN_ERROR";

        if (data && data.error) {
          errorMsg = data.error.message || errorMsg;
          errorCode = data.error.code || errorCode;
        } else if (res.status === 429) {
          errorMsg = "Bạn đã gửi quá nhiều yêu cầu. Vui lòng thử lại sau giây lát.";
          errorCode = "RATE_LIMIT";
        } else if (res.status >= 500) {
          errorMsg = "⚠️ Website nguồn hoặc hệ thống đang tạm thời không phản hồi. Vui lòng thử lại sau.";
          errorCode = "SERVER_ERROR";
        }

        const err = new Error(errorMsg);
        (err as any).code = errorCode;
        (err as any).status = res.status;
        throw err;
      }

      return data as T;
    } catch (err: any) {
      if (err.name === "TypeError" && err.message.includes("fetch")) {
        const networkErr = new Error("❌ Không thể kết nối tới Backend. Hãy chắc chắn Backend đang chạy.");
        (networkErr as any).code = "NETWORK_ERROR";
        throw networkErr;
      }
      throw err;
    }
  }

  // Analyze URL
  async analyzeUrl(url: string): Promise<AnalyzeResult> {
    return this.request<AnalyzeResult>("/analyze", {
      method: "POST",
      body: JSON.stringify({ url }),
    });
  }

  // Novels List & Detail
  async getNovels(limit = 50, offset = 0, search = ""): Promise<Novel[]> {
    const params = new URLSearchParams({ limit: limit.toString(), offset: offset.toString() });
    if (search) params.append("search", search);
    return this.request<Novel[]>(`/novels?${params.toString()}`);
  }

  async getNovel(id: number): Promise<Novel> {
    return this.request<Novel>(`/novels/${id}`);
  }

  async getNovelChapters(
    novelId: number,
    limit = 100,
    offset = 0,
    sort: "asc" | "desc" = "asc",
    search = "",
    statusFilter = ""
  ): Promise<Chapter[]> {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
      sort,
    });
    if (search) params.append("search", search);
    if (statusFilter) params.append("filter_status", statusFilter);

    return this.request<Chapter[]>(`/novels/${novelId}/chapters?${params.toString()}`);
  }

  async deleteNovel(novelId: number): Promise<{ success: boolean; message: string }> {
    return this.request<{ success: boolean; message: string }>(`/novels/${novelId}`, {
      method: "DELETE",
    });
  }

  // Translation Jobs
  async translateChapter(chapterId: number, force = false): Promise<TranslationJob> {
    return this.request<TranslationJob>(`/translate/chapter/${chapterId}`, {
      method: "POST",
      body: JSON.stringify({ force }),
    });
  }

  async translateBulk(chapterIds: number[], force = false): Promise<BulkTranslateResponse> {
    return this.request<BulkTranslateResponse>("/translate/bulk", {
      method: "POST",
      body: JSON.stringify({ chapter_ids: chapterIds, force }),
    });
  }

  async getJobStatus(jobId: string): Promise<TranslationJob> {
    return this.request<TranslationJob>(`/jobs/${jobId}`);
  }

  // Reader
  async getReaderContent(chapterId: number): Promise<ReaderData> {
    return this.request<ReaderData>(`/reader/${chapterId}`);
  }

  // Glossary
  async getGlossary(novelId: number): Promise<GlossaryItem[]> {
    return this.request<GlossaryItem[]>(`/novels/${novelId}/glossary`);
  }

  async addGlossaryTerm(
    novelId: number,
    sourceTerm: string,
    translatedTerm: string,
    note = ""
  ): Promise<GlossaryItem> {
    return this.request<GlossaryItem>(`/novels/${novelId}/glossary`, {
      method: "POST",
      body: JSON.stringify({
        source_term: sourceTerm,
        translated_term: translatedTerm,
        note,
      }),
    });
  }

  async deleteGlossaryTerm(novelId: number, termId: number): Promise<{ success: boolean }> {
    return this.request<{ success: boolean }>(`/novels/${novelId}/glossary/${termId}`, {
      method: "DELETE",
    });
  }

  // Realtime Progress via Server-Sent Events (SSE) with automatic fallback
  subscribeJobProgress(
    jobId: string,
    onProgress: (job: TranslationJob) => void,
    onError: (err: any) => void
  ): () => void {
    const sseUrl = `${API_BASE}/jobs/${jobId}/events`;
    let eventSource: EventSource | null = null;
    let pollInterval: any = null;
    let isTerminated = false;

    try {
      eventSource = new EventSource(sseUrl);

      eventSource.onmessage = (event) => {
        try {
          const data: TranslationJob = JSON.parse(event.data);
          onProgress(data);
          if (data.status === "completed" || data.status === "failed") {
            eventSource?.close();
            isTerminated = true;
          }
        } catch (e) {
          // ignore parse error
        }
      };

      eventSource.onerror = () => {
        eventSource?.close();
        if (isTerminated) return;
        // Fallback to polling every 1.5 seconds if SSE connection drops
        pollInterval = setInterval(async () => {
          try {
            const data = await this.getJobStatus(jobId);
            onProgress(data);
            if (data.status === "completed" || data.status === "failed") {
              clearInterval(pollInterval);
            }
          } catch (pollErr) {
            clearInterval(pollInterval);
            onError(pollErr);
          }
        }, 1500);
      };
    } catch {
      // In case browser does not support SSE or fails
      pollInterval = setInterval(async () => {
        try {
          const data = await this.getJobStatus(jobId);
          onProgress(data);
          if (data.status === "completed" || data.status === "failed") {
            clearInterval(pollInterval);
          }
        } catch (pollErr) {
          clearInterval(pollInterval);
          onError(pollErr);
        }
      }, 1500);
    }

    // Cleanup function
    return () => {
      isTerminated = true;
      if (eventSource) eventSource.close();
      if (pollInterval) clearInterval(pollInterval);
    };
  }
}

export const api = new ApiService();
