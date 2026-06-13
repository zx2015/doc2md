# Architecture Overview

| Version | Date | Description | Author |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-06-12 | Initial blueprint for Doc2MD system architecture | Gemini CLI |
| v1.1.0 | 2026-06-13 | Switch core parsing engine from Docling to MinerU (MagicDocs) | Gemini CLI |

---

## 1. System Components

```mermaid
graph TD
    Client[Web UI / API Clients] -->|REST / WS| FastAPI[FastAPI API Gateway]
    FastAPI -->|Enqueue Task| TaskQueue[Task Queue / Background Workers]
    TaskQueue -->|Execute| MinerUEngine[MinerU Conversion Engine]
    MinerUEngine -->|Local Compute| Hardware[CPU / GPU Scheduler]
    MinerUEngine -->|Images & Fragments| ExternalLLM[External LLM API]
    MinerUEngine -->|Output| MarkdownFile[Markdown Result]
```

## 2. Component Specifications

- **Frontend**: Single-page application providing user controls for CPU/GPU configuration and model selection.
- **Backend API**: Exposes asynchronous conversion tasks, status polling, and configuration adjustment.
- **Engine Layer**: Interfaces directly with MinerU (PDF-Extract-Kit), supporting high-precision document layout analysis, table recognition, and mathematical formula parsing. GPU acceleration strongly recommended.

---

## Related
- [Design Index](index.md)
- [Requirements Index](../requirements/index.md)
