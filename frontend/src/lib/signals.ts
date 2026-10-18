// What each error signal of the API means to someone using the app.

const MESSAGES: Record<string, string> = {
  file_type_not_supported: "Only PDF and plain-text files can be uploaded.",
  file_size_exceeded: "The file is larger than the server allows.",
  file_upload_failed: "The file could not be saved. Try again.",
  file_not_found: "That file does not exist in this project.",
  project_not_found: "This project has no documents yet.",
  file_has_no_text: "No text could be read from the file. Scanned PDFs need OCR first.",
  processing_failed: "The file could not be split into chunks.",
  embedding_not_configured:
    "No embedding model is configured. Set OPENAI_API_KEY or EMBEDDING_BASE_URL on the server.",
  embedding_failed:
    "The embedding model failed: it was unreachable, rejected the request or sent an unexpected reply. The API's log says which.",
  llm_not_configured:
    "No language model is configured. Set OPENAI_API_KEY or LLM_BASE_URL on the server.",
  llm_failed:
    "The language model failed: it was unreachable, rejected the request or sent an unexpected reply. The API's log says which.",
  validation_error: "The request was not valid.",
  network_error: "The server could not be reached. Is the API running?",
};

export function signalMessage(signal: string): string {
  return MESSAGES[signal] ?? `The server reported an error (${signal}).`;
}
