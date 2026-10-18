// Shapes of the Mini RAG API's requests and responses (see /docs).

export interface Welcome {
  message: string;
  app_name: string;
  app_version: string;
}

export interface Health {
  status: "ok" | "unavailable";
  database: "ok" | "unavailable";
}

export interface Page<T> {
  total: number;
  offset: number;
  limit: number;
  items: T[];
}

export interface ProjectListItem {
  name: string;
  created_at: string;
}

export interface Project {
  name: string;
  created_at: string;
  files_count: number;
  chunks_count: number;
  embedded_chunks_count: number;
}

export interface ProjectUsage {
  answers: number;
  answered: number;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  unpriced_answers: number;
}

export interface FileInfo {
  file_id: string;
  original_name: string;
  content_type: string;
  size_bytes: number;
  created_at: string;
}

export interface ChunkMetadata {
  source?: string;
  page?: number;
  [key: string]: unknown;
}

export interface Chunk {
  chunk_index: number;
  text: string;
  metadata: ChunkMetadata;
}

export interface UploadResult {
  signal: string;
  file_id: string;
}

export interface ProcessOptions {
  chunk_size: number;
  overlap_size: number;
}

export interface ProcessResult {
  signal: string;
  file_id: string;
  chunks_count: number;
}

export interface IndexResult {
  signal: string;
  embedded_count: number;
  chunks_count: number;
}

export interface SearchOptions {
  top_k: number;
  min_score: number | null;
}

export interface SearchHit {
  file_id: string;
  chunk_index: number;
  score: number;
  text: string;
  metadata: ChunkMetadata;
}

export interface SearchResult {
  signal: string;
  results: SearchHit[];
}

export interface Citation {
  number: number;
  file_id: string;
  chunk_index: number;
  page: number | null;
  score: number;
  text: string;
}

export interface Usage {
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: number | null;
}

export interface Answer {
  signal: "answer_success" | "no_answer";
  answer: string | null;
  citations: Citation[];
  prompt_version: string;
  usage: Usage;
}
