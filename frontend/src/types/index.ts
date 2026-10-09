export type ChapterStatus = "pending" | "queued" | "processing" | "translating" | "completed" | "failed";

export interface Chapter {
  id: number;
  chapter_number: number;
  title: string;
  url: string;
  status: ChapterStatus;
  has_translation?: boolean;
}

export interface Novel {
  id: number;
  title: string;
  author: string;
  cover_url: string;
  description: string;
  url: string;
  source_domain: string;
  total_chapters: number;
  translated_count?: number;
  created_at: string;
  updated_at?: string;
  chapters?: Chapter[];
}

export interface AnalyzeResult {
  success: boolean;
  novel?: {
    id?: number;
    title: string;
    author: string;
    cover: string;
    description: string;
    url: string;
    source_domain: string;
    total_chapters: number;
    chapters: Chapter[];
  };
  error?: {
    code: string;
    message: string;
  };
}

export interface TranslationJob {
  job_id: string;
  chapter_id: number;
  status: "queued" | "processing" | "translating" | "quality_check" | "completed" | "failed";
  current_chunk: number;
  total_chunks: number;
  progress_percent: number;
  message: string;
  error_message?: string;
  error?: string;
}

export interface BulkTranslateResponse {
  success: boolean;
  queued_count: number;
  jobs: TranslationJob[];
}

export interface ReaderData {
  chapter_id: number;
  novel_id: number;
  novel_title: string;
  chapter_number: number;
  chapter_title: string;
  translated_title: string;
  translated_text: string;
  original_text: string;
  prev_chapter_id: number | null;
  next_chapter_id: number | null;
  status: ChapterStatus;
}

export interface GlossaryItem {
  id: number;
  novel_id: number;
  source_term: string;
  translated_term: string;
  note: string;
  created_at: string;
}
