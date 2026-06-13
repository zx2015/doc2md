# Architecture Overview

| Version | Date | Description | Author |
| :--- | :--- | :--- | :--- |
| v1.0.0 | 2026-06-12 | Initial blueprint for Doc2MD system architecture | Gemini CLI |

---

## 1. System Components

```mermaid
graph TD
    Client[Web UI / API Clients] -->|REST / WS| FastAPI[FastAPI API Gateway]
    FastAPI -->|Enqueue Task| TaskQueue[Task Queue / Background Workers]
    TaskQueue -->|Execute| DoclingEngine[Docling Conversion Engine]
    DoclingEngine -->|Local Compute| Hardware[CPU / GPU Scheduler]
    DoclingEngine -->|Enhanced Layout| ExternalLLM[External LLM API]
    DoclingEngine -->|Output| MarkdownFile[Markdown Result]
```

## 2. Component Specifications

- **Frontend**: Single-page application providing user controls for CPU/GPU configuration and model selection.
- **Backend API**: Exposes asynchronous conversion tasks, status polling, and configuration adjustment.
- **Engine Layer**: Interfaces directly with Docling using PyTorch, with automatic device mapping (`cuda` / `cpu`).

---

## Related
- [Design Index](index.md)
- [Requirements Index](../requirements/index.md)
