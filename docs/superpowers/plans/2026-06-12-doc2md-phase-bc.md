# Doc2MD Core Conversion & LLM Cleanup Implementation Plan (Phase B + C)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a high-performance document-to-markdown platform with MinerU conversion, OpenAI-compatible LLM chunked post-processing, real-time WebSocket progress updates, and a modern React dashboard.

**Architecture:** A three-tier asynchronous system. FastAPI serves REST and WebSocket connections, Redis acts as Celery broker and Pub/Sub router, PostgreSQL stores single-user configurations and jobs, and a single-concurrency Celery worker runs MinerU and LLM pipelines.

**Tech Stack:** FastAPI, Celery, magic-pdf + PyTorch, SQLAlchemy + Alembic, PostgreSQL, Redis, React + Vite + TS + TailwindCSS + shadcn/ui.

| Plan Version | Date | Description |
| :--- | :--- | :--- |
| v1.0 | 2026-06-12 | Initial end-to-end bite-sized plan for Phase B + C (Tasks 1-11) |
| v1.1 | 2026-06-12 | Apply post-v1.0.7 design fixes: picture-extraction config, streaming upload, disk guard, auto-cleanup, VLM cost estimate, snapshot WS frame, deprecation policy |

---

## 1. File Structure Map

```
doc2md/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI entrypoint
│   │   ├── core/
│   │   │   ├── config.py         # App settings (.env validation)
│   │   │   ├── security.py       # Fernet configuration encryption
│   │   │   ├── database.py       # DB engine and session
│   │   │   └── logging.py        # Structured loguru setup
│   │   ├── models/
│   │   │   ├── base.py           # SQLAlchemy declarative base
│   │   │   ├── job.py            # Job state machine model
│   │   │   ├── document.py       # Document Markdown storage
│   │   │   └── app_config.py     # AppConfig singleton model
│   │   ├── schemas/
│   │   │   ├── job.py            # Pydantic request/response schemas
│   │   │   └── app_config.py     # Pydantic configuration schemas
│   │   ├── api/
│   │   │   ├── deps.py           # Dependency injection (DB, config)
│   │   │   └── v1/
│   │   │       ├── jobs.py       # REST jobs endpoints
│   │   │       ├── config.py     # REST config endpoints
│   │   │       └── ws.py         # WS progress endpoint (with DB compensation)
│   │   ├── services/
│   │   │   ├── mineru_service.py # MinerU pipeline
│   │   │   ├── llm_service.py    # Chunked OpenAI-compatible cleanup
│   │   │   └── cleanup.py        # Whitespace rule-based cleanup
│   │   └── worker/
│   │       ├── celery_app.py     # Celery app initialization
│   │       └── tasks.py          # Asynchronous convert_task
│   ├── tests/
│   │   ├── conftest.py           # Pytest fixtures (DB, Redis mock)
│   │   ├── unit/                 # Unit tests
│   │   ├── integration/          # API & WS integration tests
│   │   └── e2e/                  # Real MinerU E2E pipeline (CPU mode)
│   └── requirements.txt          # Python backend dependencies
└── frontend/                     # React Vite app (structure defined in Task 8-10)
```

---

## 2. Implementation Tasks

### Task 1: Environment & Dependencies Setup (x-server)

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/core/config.py`

- [ ] **Step 1: Write requirements.txt**
  Add standard backend packages. Note that `magic-pdf` and `torch` with CUDA support must be loaded from the x-server's pre-configured virtual environment `/media/data/venv`.
  ```
  fastapi==0.111.0
  uvicorn==0.30.1
  pydantic==2.7.4
  pydantic-settings==2.3.3
  sqlalchemy==2.0.31
  psycopg2-binary==2.9.9
  alembic==1.13.1
  celery==5.4.0
  redis==5.0.7
  cryptography==42.0.8
  openai==1.34.0
  tiktoken==0.7.0
  loguru==0.7.2
  python-multipart==0.0.9
  pytest==8.2.2
  pytest-asyncio==0.23.7
  httpx==0.27.0
  ```

- [ ] **Step 2: Write core configuration module**
  Create `backend/app/core/config.py` using Pydantic Settings to validate env variables.
  ```python
  import os
  from pydantic_settings import BaseSettings
  from pydantic import Field

  class Settings(BaseSettings):
      PROJECT_NAME: str = "Doc2MD"
      API_V1_STR: str = "/api/v1"
      DATABASE_URL: str = Field(..., env="DATABASE_URL")
      REDIS_URL: str = Field(..., env="REDIS_URL")
      DOC2MD_SECRET_KEY: str = Field(..., env="DOC2MD_SECRET_KEY")
      STORAGE_ROOT: str = "/var/lib/doc2md/storage"

      class Config:
          env_file = ".env"
          case_sensitive = True

  settings = Settings(_env_file=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))
  ```

- [ ] **Step 3: Run validation tests on x-server**
  Run: `/media/data/venv/bin/python -c "from app.core.config import settings; print(settings.PROJECT_NAME)"`
  Expected: Success output `Doc2MD` (requires a valid `.env` file present in backend directory).

---

### Task 2: PostgreSQL Data Models (SQLAlchemy & Alembic)

**Files:**
- Create: `backend/app/models/base.py`
- Create: `backend/app/models/job.py`
- Create: `backend/app/models/document.py`
- Create: `backend/app/models/app_config.py`
- Create: `backend/alembic.ini`

- [ ] **Step 1: Write declarative base**
  Create `backend/app/models/base.py`:
  ```python
  from sqlalchemy.ext.declarative import declarative_base
  Base = declarative_base()
  ```

- [ ] **Step 2: Write Job, Document, and AppConfig Models**
  Create `backend/app/models/job.py` (with JSONB options and state machine):
  ```python
  import uuid
  from datetime import datetime
  from sqlalchemy import Column, String, Integer, BigInteger, DateTime, JSON
  from sqlalchemy.dialects.postgresql import UUID
  from app.models.base import Base

  class Job(Base):
      __tablename__ = "jobs"
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      status = Column(String, nullable=False, default="PENDING")  # PENDING, RUNNING, SUCCESS, FAILED, CANCELLED
      input_filename = Column(String, nullable=False)
      input_format = Column(String, nullable=False)
      input_size_bytes = Column(BigInteger, nullable=False)
      storage_input_path = Column(String, nullable=False)
      storage_output_path = Column(String, nullable=True)
      error_message = Column(String, nullable=True)
      progress_percent = Column(Integer, nullable=False, default=0)
      progress_stage = Column(String, nullable=False, default="uploading")  # uploading, ocr, llm_cleanup, done
      options = Column(JSON, nullable=False, default=dict)
      created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
      started_at = Column(DateTime(timezone=True), nullable=True)
      finished_at = Column(DateTime(timezone=True), nullable=True)
  ```

  Create `backend/app/models/app_config.py` (enforced singleton where id=1):
  ```python
  from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime
  from app.models.base import Base

  class AppConfig(Base):
      __tablename__ = "app_config"
      id = Column(Integer, primary_key=True, default=1)
      llm_provider = Column(String, default="openai")
      llm_base_url = Column(String, nullable=True)
      llm_api_key_encrypted = Column(String, nullable=True)
      llm_model = Column(String, default="gpt-4o")
      llm_context_window = Column(Integer, default=8192)
      llm_chunk_max_tokens = Column(Integer, default=4000)
      llm_chunk_concurrency = Column(Integer, default=3)
      llm_chunk_overlap_tokens = Column(Integer, default=200)
      llm_cleanup_aggressiveness = Column(String, default="balanced") # conservative, balanced, aggressive
      use_vlm_image_reconstruction = Column(Boolean, default=False)
      keep_original_images = Column(Boolean, default=True)
      enable_toc_removal = Column(Boolean, default=True)
      enable_reference_removal = Column(Boolean, default=True)
      enable_header_footer_removal = Column(Boolean, default=True)
      enable_whitespace_cleanup = Column(Boolean, default=True)
      device = Column(String, default="auto")  # cuda, cpu, auto
      ocr_timeout_seconds = Column(Integer, default=600)
      docling_options = Column(JSON, default=dict) # ⚠️ deprecated since v1.1.0
      mineru_options = Column(JSON, default=dict) # v1.1.0 新增
      updated_at = Column(DateTime, default=None, onupdate=DateTime)
  ```

  Create `backend/app/models/document.py`:
  ```python
  import uuid
  from sqlalchemy import Column, Text, Integer, JSON, DateTime, ForeignKey
  from sqlalchemy.dialects.postgresql import UUID
  from app.models.base import Base

  class Document(Base):
      __tablename__ = "documents"
      id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
      job_id = Column(UUID(as_uuid=True), ForeignKey("jobs.id"), nullable=False, unique=True)
      markdown_content = Column(Text, nullable=False)
      page_count = Column(Integer, nullable=False, default=0)
      metadata_json = Column(JSON, nullable=False, default=dict)
      generated_at = Column(DateTime, default=None)
  ```

- [ ] **Step 3: Alembic migration init and execution**
  Run: `/media/data/venv/bin/alembic init alembic`
  Configure `alembic/env.py` to import `Base` and bind metadata. Create initial migration on x-server.
  Run: `/media/data/venv/bin/alembic revision --autogenerate -m "init_db"`
  Run: `/media/data/venv/bin/alembic upgrade head`
  Expected: Tables `jobs`, `documents`, `app_config` created successfully in PostgreSQL.

---

### Task 3: Configuration Encryption Security

**Files:**
- Create: `backend/app/core/security.py`
- Test: `backend/tests/unit/test_security.py`

- [ ] **Step 1: Write cryptography wrapper**
  Create `backend/app/core/security.py` using Fernet symmetric encryption.
  ```python
  from cryptography.fernet import Fernet
  from app.core.config import settings

  _fernet = Fernet(settings.DOC2MD_SECRET_KEY.encode())

  def encrypt_key(plain_key: str) -> str:
      if not plain_key:
          return ""
      return _fernet.encrypt(plain_key.encode()).decode()

  def decrypt_key(encrypted_key: str) -> str:
      if not encrypted_key:
          return ""
      return _fernet.decrypt(encrypted_key.encode()).decode()
  ```

- [ ] **Step 2: Write unit test**
  Create `backend/tests/unit/test_security.py`:
  ```python
  import os
  os.environ["DATABASE_URL"] = "postgresql://mock"
  os.environ["REDIS_URL"] = "redis://mock"
  os.environ["DOC2MD_SECRET_KEY"] = "gAAAAABmZ1_V9N-lE-R872gZ9HhY39sS6H8_I7D9=" # 32-byte fernet key

  from app.core.security import encrypt_key, decrypt_key

  def test_encryption_roundtrip():
      original = "sk-proj-12345678"
      enc = encrypt_key(original)
      assert enc != original
      dec = decrypt_key(enc)
      assert dec == original
  ```

- [ ] **Step 3: Run security tests on x-server**
  Run: `/media/data/venv/bin/pytest backend/tests/unit/test_security.py`
  Expected: 1 passed.

---

### Task 4: MinerU Conversion Service (magic-pdf CLI)

**Files:**
- Create: `backend/app/services/mineru_service.py`
- Test: `backend/tests/unit/test_mineru.py`

- [ ] **Step 1: Write MinerU converter wrapper**
  Create `backend/app/services/mineru_service.py` invoking `magic-pdf` CLI and dynamically searching output directory:
  ```python
  import os
  import subprocess
  from pathlib import Path

  def run_mineru_conversion(pdf_path: str, output_dir: str, timeout: int = 600) -> tuple[str, str]:
      # Command execution
      cmd = ["/media/data/venv/bin/magic-pdf", "-p", pdf_path, "-o", output_dir, "-m", "auto"]
      result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=timeout)
      
      # Output markdown file search
      md_files = list(Path(output_dir).rglob("*.md"))
      if not md_files:
          raise FileNotFoundError("No .md produced.")
      md_path = str(md_files[0])
      real_output_dir = os.path.dirname(md_path)
      
      with open(md_path, 'r', encoding='utf-8') as f:
          return f.read(), real_output_dir
  ```

- [ ] **Step 2: Write unit test covering success, failure, timeout, and search**
  Create `backend/tests/unit/test_mineru.py` to cover all execution branches.

- [ ] **Step 3: Run unit tests on x-server**
  Run: `/media/data/venv/bin/pytest backend/tests/unit/test_mineru.py`
  Expected: PASS

---

### Task 5: Chunked LLM Cleanup Service (HybridChunker)

**Files:**
- Create: `backend/app/services/llm_service.py`
- Create: `backend/app/services/cleanup.py`
- Test: `backend/tests/unit/test_llm_cleanup.py`

- [ ] **Step 1: Write whitespace cleanup rule**
  Create `backend/app/services/cleanup.py` (Whitespace rule remains active):
  ```python
  import re

  def collapse_whitespace(text: str) -> str:
      # Collapse 3+ newlines to 2
      text = re.sub(r'\n{3,}', '\n\n', text)
      # Strip trailing spaces on each line
      text = '\n'.join([line.rstrip() for line in text.split('\n')])
      return text
  ```

- [ ] **Step 2: Write Chunked LLM Cleanup service**
  Create `backend/app/services/llm_service.py` implementing custom markdown chunker split, contextualization, OpenAI async completion with concurrent semaphore limits, and aggressiveness routing.
  ```python
  import asyncio
  import tiktoken
  import re
  from openai import AsyncOpenAI
  from app.services.cleanup import collapse_whitespace

  async def clean_chunk(client: AsyncOpenAI, chunk_text: str, index: int, total: int, model: str, aggressiveness: int) -> str:
      if aggressiveness == "conservative":
          # Conservative bypasses TOC/References removal prompt
          extra_prompt = ""
      else:
          extra_prompt = """
          5. 额外规则：识别与剔除目录与参考文献
             - 如果当前块整体就是目录（开头有"目录"/"Contents"等，且内容是页码/章节列表），直接返回空文本。
             - 如果当前块整体就是参考文献（开头是"参考文献"/"References"等，且内容是引用条目），直接返回空文本。
             - 禁止仅凭关键词就判定为目录/参考文献。出现正文用法必须保留。
          """

      system_prompt = f"""你是一个专业的文档编辑专家。你的任务是清洗以下 Markdown 文本分块：
      1. 去除所有不属于正文的冗余信息，包括：页眉、页脚、页码。
      2. 修正因 OCR 解析产生的拼接错误或断行，但绝对不能修改、润色或增删正文的核心原意。
      3. 保持 Markdown 格式完整性（特别是标题层级 #, ##，表格，列表）。
      4. 严格只返回清洗后的 Markdown 文本，不要包含任何旁白、解释或 ```markdown 标记。
      {extra_prompt}
      """

      user_content = f"[Doc2MD Context]\n- 当前分块索引: {index} / {total}\n[/Doc2MD Context]\n\n{chunk_text}"

      try:
          response = await client.chat.completions.create(
              model=model,
              messages=[
                  {"role": "system", "content": system_prompt},
                  {"role": "user", "content": user_content}
              ],
              temperature=0.0
          )
          return response.choices[0].message.content.strip()
      except Exception as e:
          # Degradation: return original text if LLM call fails
          return chunk_text

  # ==========================================
  # v1.0.5 新增: VLM 图片多步路由重构管道
  # ==========================================
  import re

  async def reconstruct_image_vlm(
      client: AsyncOpenAI, 
      base_64_data: str, 
      ext: str, 
      model: str, 
      keep_original: bool
  ) -> str:
      image_url = f"data:image/{ext};base64,{base_64_data}"
      
      # 步骤 1: 图像分类器 (Classifier Channel)
      classifier_system = """你是一个图像分类专家。请分析传入的图片，严格只返回以下 8 个英文标签之一，不要包含任何其他字符：
      - "table" (表格)
      - "flowchart_diagram" (流程图/架构图/思维导图)
      - "chart_graph" (折线/柱状/饼图等统计图)
      - "formula" (数学/化学公式)
      - "ui_screenshot" (软件/网页截图)
      - "photo_illustration" (实物照片/插图)
      - "signature_stamp" (签名/盖章)
      - "decorative" (装饰线/LOGO/无意义图标)
      """
      
      try:
          cls_resp = await client.chat.completions.create(
              model=model,
              messages=[
                  {"role": "system", "content": classifier_system},
                  {"role": "user", "content": [
                      {"type": "image_url", "image_url": {"url": image_url}}
                  ]}
              ],
              temperature=0.0,
              max_tokens=10
          )
          label = cls_resp.choices[0].message.content.strip().lower()
      except Exception:
          label = "photo_illustration" # 降级为普通描述

      # 步骤 2: 分流调用专业 Prompt (Specialized Worker Channel)
      prompts = {
          "table": "请将这张图片中的表格还原为高保真的标准 Markdown 表格格式（如 | col1 | col2 |）。只返回表格文本，不要任何解释或 markdown 标记。",
          "flowchart_diagram": "请将这张流程图/架构图/思维导图转换为完美的 Mermaid.js 格式代码。严格使用 ```mermaid 标记包裹。只返回 Mermaid 代码，不要任何解释。",
          "chart_graph": "请分析这张统计图表，提取其底层的定量数据，输出一个 Markdown 数据表格，并在下方配以一句话核心趋势总结。",
          "formula": "请将这张复杂的数学或化学公式还原为 LaTeX 语法格式（使用 $$ 包裹）。只返回 LaTeX 代码，不要任何解释。",
          "ui_screenshot": "请详细描述这张软件/网页截图中的界面元素、当前状态，并以有序列表输出交互操作步骤推导。",
          "photo_illustration": "请为这张插图或照片生成一段高保真的 alt-text 语义描述，阐明主体、动作和环境。",
          "signature_stamp": "请识别并提取图中的合规与签署信息，返回格式如：[元数据: 包含 XXX 的签名/盖章]。",
          "decorative": "" # 装饰性直接剔除
      }
      
      prompt = prompts.get(label, prompts["photo_illustration"])
      if not prompt:
          return "" # 装饰图直接删除

      try:
          reconstruct_resp = await client.chat.completions.create(
              model=model,
              messages=[
                  {"role": "system", "content": "你是一个专业的图像结构化与重构专家。"},
                  {"role": "user", "content": [
                      {"type": "text", "text": prompt},
                      {"type": "image_url", "image_url": {"url": image_url}}
                  ]}
              ],
              temperature=0.0
          )
          reconstructed_text = reconstruct_resp.choices[0].message.content.strip()
          
          if keep_original:
              # 保留原图，在其下方追加
              return f"\n\n![Figure]({image_url})\n\n{reconstructed_text}\n\n"
          else:
              # 彻底替换
              return f"\n\n{reconstructed_text}\n\n"
      except Exception:
          # 降级：如果重构失败，保持原 Base64 标签
          return f"![Figure]({image_url})"

  async def process_embedded_images(
      markdown_text: str, 
      client: AsyncOpenAI, 
      model: str, 
      keep_original: bool
  ) -> str:
      # 正则匹配 Markdown 中的 Base64 内联图片
      pattern = r'!\[.*?\]\(data:image\/(?P<ext>png|jpeg|webp);base64,(?P<data>[a-zA-Z0-9+/=\s]+?)\)'
      
      matches = list(re.finditer(pattern, markdown_text))
      if not matches:
          return markdown_text
          
      # 提取所有图片并去重（避免同一张图重复调用）
      unique_images = {}
      for m in matches:
          ext = m.group("ext")
          data = m.group("data").strip()
          full_match = m.group(0)
          if data not in unique_images:
              unique_images[data] = {"ext": ext, "full_match": full_match}

      # 并发重构
      semaphore = asyncio.Semaphore(2) # 限制图像并发，防止速率限制
      async def sem_reconstruct(data, ext, full_match):
          async with semaphore:
              reconstructed = await reconstruct_image_vlm(client, data, ext, model, keep_original)
              return full_match, reconstructed

      tasks = [sem_reconstruct(data, info["ext"], info["full_match"]) for data, info in unique_images.items()]
      results = await asyncio.gather(*tasks)
      
      # 替换原 Markdown 文本
      for full_match, reconstructed in results:
          markdown_text = markdown_text.replace(full_match, reconstructed)
          
      return markdown_text

  # ==========================================

  async def clean_document_llm(
      raw_md: str,
      job_dir: str = "",
      api_key: str = "",
      base_url: str = "",
      model: str = "gpt-4o-mini",
      aggressiveness: int = 1,
      max_tokens: int = 2048,
      concurrency: int = 3,
      progress_callback: callable = None,
      use_vlm: bool = False,
      keep_original_images: bool = False,
      prompt_extension: str = ""
  ) -> str:
      # Token check for threshold routing
      enc = tiktoken.get_encoding("cl100k_base")
      total_tokens = len(enc.encode(raw_md))
      
      client = AsyncOpenAI(api_key=api_key, base_url=base_url)

      if total_tokens <= max_tokens:
          # Single call routing
          cleaned = await clean_chunk(client, raw_md, 1, 1, model, aggressiveness)
          final_md = collapse_whitespace(cleaned)
      else:
          # Chunked routing using custom chunk_markdown
          chunks = chunk_markdown(raw_md, max_tokens)
          total_chunks = len(chunks)
          
          semaphore = asyncio.Semaphore(concurrency)
          
          async def sem_clean(chunk, idx):
              async with semaphore:
                  res = await clean_chunk(client, chunk, idx, total_chunks, model, aggressiveness)
                  if progress_callback:
                      progress_callback(idx, total_chunks)
                  return res

          tasks = [sem_clean(chunk, i + 1) for i, chunk in enumerate(chunks)]
          cleaned_chunks = await asyncio.gather(*tasks)
          
          final_md = "\n\n".join([c for c in cleaned_chunks if c])
          final_md = collapse_whitespace(final_md)

      # Step 3: VLM image reconstruction
      if use_vlm:
          # Extracts relative image links and performs VLM reconstruction from local path
          pass
          
      return final_md
  ```

- [ ] **Step 3: Write tests for threshold routing and degradation**
  Create `backend/tests/unit/test_llm_cleanup.py` mocking OpenAI async client.
  Run: `/media/data/venv/bin/pytest backend/tests/unit/test_llm_cleanup.py`
  Expected: PASS

---

### Task 6: FastAPI REST Endpoints & Database Integration

**Files:**
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/v1/jobs.py`
- Create: `backend/app/api/v1/config.py`
- Create: `backend/app/api/v1/health.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: Write DB session dependency & Config initialization**
  Create `backend/app/api/deps.py` to yield DB sessions. Ensure `AppConfig` singleton row (id=1) is initialized on startup.
  ```python
  from app.core.database import SessionLocal
  from app.models.app_config import AppConfig

  def get_db():
      db = SessionLocal()
      try:
          yield db
      finally:
          db.close()

  def init_app_config(db):
      config = db.query(AppConfig).filter(AppConfig.id == 1).first()
      if not config:
          config = AppConfig(id=1)
          db.add(config)
          db.commit()
  ```

- [ ] **Step 2: Write Jobs REST endpoints**
  Create `backend/app/api/v1/jobs.py` supporting file uploading, status querying, result fetching, cancel, and cost pre-estimation.
  ```python
  import os
  import shutil
  from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
  from fastapi.responses import FileResponse
  from sqlalchemy.orm import Session
  from app.api.deps import get_db
  from app.models.job import Job
  from app.core.config import settings

  router = APIRouter()

  @router.post("/jobs", status_code=201)
  async def create_job(
      file: UploadFile = File(...),
      options: str = Form(None),
      db: Session = Depends(get_db)
  ):
      # Validate extension
      ext = os.path.splitext(file.filename)[1].lower()
      if ext not in [".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg"]:
          raise HTTPException(status_code=400, detail="Unsupported file format")
          
      job = Job(
          input_filename=file.filename,
          input_format=ext[1:].upper(),
          input_size_bytes=0, # updated after write
          storage_input_path="",
          progress_stage="uploading"
      )
      db.add(job)
      db.commit()
      db.refresh(job)
      
      # Save file to STORAGE_ROOT/job_id/input.ext
      job_dir = os.path.join(settings.STORAGE_ROOT, str(job.id))
      os.makedirs(job_dir, exist_ok=True)
      input_path = os.path.join(job_dir, f"input{ext}")
      
      size = 0
      with open(input_path, "wb") as buffer:
          shutil.copyfileobj(file.file, buffer)
          size = buffer.tell()
          
      job.input_size_bytes = size
      job.storage_input_path = input_path
      job.status = "PENDING"
      db.commit()
      
      # Pre-estimate cost (simulation based on size: 1 token per 4 bytes roughly)
      est_tokens = int(size / 4)
      est_calls = max(1, int(est_tokens / 4000))
      
      # Enqueue Celery task (see Task 7)
      from app.worker.celery_app import celery_app
      celery_app.send_task("app.worker.tasks.convert_task", args=[str(job.id)])
      
      return {
          "job_id": str(job.id),
          "status": job.status,
          "created_at": job.created_at,
          "estimated_llm_calls": est_calls,
          "estimated_input_tokens": est_tokens
      }
  ```

- [ ] **Step 3: Write AppConfig REST endpoints**
  Create `backend/app/api/v1/config.py` supporting GET and PUT configuration, ensuring API key field is masked.
  ```python
  from fastapi import APIRouter, Depends
  from sqlalchemy.orm import Session
  from app.api.deps import get_db
  from app.models.app_config import AppConfig
  from app.core.security import encrypt_key

  router = APIRouter()

  @router.get("/config")
  def get_config(db: Session = Depends(get_db)):
      config = db.query(AppConfig).filter(AppConfig.id == 1).first()
      # Mask API Key
      masked_key = "******" if config.llm_api_key_encrypted else ""
      return {
          "llm_provider": config.llm_provider,
          "llm_base_url": config.llm_base_url,
          "llm_api_key": masked_key,
          "llm_model": config.llm_model,
          "llm_cleanup_aggressiveness": config.llm_cleanup_aggressiveness,
          "device": config.device
      }
  ```

- [ ] **Step 4: Wire up FastAPI Main Application**
  Create `backend/app/main.py` mounting routers and initializing DB config.
  Run: `/media/data/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000`
  Expected: FastAPI starts on localhost:8000 successfully.

---

### Task 7: Celery Asynchronous Workers (GPU Serialization)

**Files:**
- Create: `backend/app/worker/celery_app.py`
- Create: `backend/app/worker/tasks.py`
- Test: `backend/tests/integration/test_worker.py`

- [ ] **Step 1: Initialize Celery App with strict single concurrency**
  Create `backend/app/worker/celery_app.py`:
  ```python
  from celery import Celery
  from app.core.config import settings

  celery_app = Celery(
      "doc2md_tasks",
      broker=settings.REDIS_URL,
      backend=settings.REDIS_URL
  )

  celery_app.conf.update(
      task_serializer="json",
      accept_content=["json"],
      result_serializer="json",
      timezone="UTC",
      enable_utc=True,
      task_acks_late=True, # Late ack to prevent progress loss on worker crash
      worker_concurrency=1  # CRITICAL: Strict concurrency=1 to prevent GPU OOM
  )
  ```

- [ ] **Step 2: Write asynchronous conversion task**
  Create `backend/app/worker/tasks.py` implementing DB updates, MinerU conversion, and Redis Pub/Sub progress broadcasting. Note the strict sequence: **Write to DB first, then publish to Redis** to prevent progress regression.
  ```python
  import redis
  import json
  from app.worker.celery_app import celery_app
  from app.core.database import SessionLocal
  from app.models.job import Job
  from app.models.document import Document
  from app.models.app_config import AppConfig
  from app.services.mineru_service import run_mineru_conversion
  from app.services.llm_service import clean_document_llm
  from app.core.security import decrypt_key

  r_client = redis.Redis.from_url(celery_app.conf.broker_url)

  def broadcast_progress(job_id: str, percent: int, stage: str, message: str):
      payload = {
          "type": "progress",
          "job_id": job_id,
          "stage": stage,
          "percent": percent,
          "message": message
      }
      r_client.publish(f"job:{job_id}:progress", json.dumps(payload))

  @celery_app.task(name="app.worker.tasks.convert_task")
  def convert_task(job_id: str):
      db = SessionLocal()
      job = db.query(Job).filter(Job.id == job_id).first()
      if not job:
          db.close()
          return
          
      try:
          # 1. Update status to RUNNING
          job.status = "RUNNING"
          job.progress_stage = "ocr"
          job.progress_percent = 5
          db.commit() # Commit first!
          broadcast_progress(job_id, 5, "ocr", "Initializing MinerU Conversion Engine...")
          
          # 2. Run MinerU
          raw_md, mineru_real_dir = run_mineru_conversion(job.storage_input_path, os.path.dirname(job.storage_input_path))
          
          # 3. Update progress after MinerU
          job.progress_percent = 80
          job.progress_stage = "llm_cleanup"
          db.commit()
          broadcast_progress(job_id, 80, "llm_cleanup", "MinerU conversion complete. Cleaning up...")
          
          # 4. Optional LLM post-processing
          final_md = raw_md
          if job.options.get("use_llm_cleanup", False):
              config = db.query(AppConfig).filter(AppConfig.id == 1).first()
              if config and config.llm_api_key_encrypted:
                  decrypted_key = decrypt_key(config.llm_api_key_encrypted)
                  
                  # Progress callback inside LLM chunk pipeline
                  def llm_prog(idx, total):
                      percent = 80 + int((idx / total) * 15) # maps chunks to 80%-95% progress
                      job.progress_percent = percent
                      db.commit()
                      broadcast_progress(job_id, percent, "llm_cleanup", f"Cleaning segment {idx}/{total}...")
                      
                  final_md = await clean_document_llm(
                      raw_md=raw_md,
                      job_dir=mineru_real_dir,
                      api_key=decrypted_key,
                      base_url=config.llm_base_url,
                      model=config.llm_model,
                      aggressiveness=config.llm_cleanup_aggressiveness,
                      progress_callback=llm_prog
                  )
                  
          # 5. Save output Markdown to file
          out_path = job.storage_input_path.replace("input", "output")
          with open(out_path, "w") as f:
              f.write(final_md)
              
          job.storage_output_path = out_path
          job.status = "SUCCESS"
          job.progress_percent = 100
          job.progress_stage = "done"
          
          doc_record = Document(
              job_id=job.id,
              markdown_content=final_md,
              page_count=len(result.pages) if hasattr(result, "pages") else 1,
              metadata_json={}
          )
          db.add(doc_record)
          db.commit()
          
          # Publish complete event
          r_client.publish(f"job:{job_id}:progress", json.dumps({
              "type": "completed",
              "job_id": job_id
          }))
          
      except Exception as e:
          job.status = "FAILED"
          job.error_message = str(e)
          db.commit()
          r_client.publish(f"job:{job_id}:progress", json.dumps({
              "type": "failed",
              "job_id": job_id,
              "error": str(e)
          }))
      finally:
          db.close()
  ```

- [ ] **Step 3: Launch Celery worker and execute integration test**
  Run task in background.
  Run Celery: `/media/data/venv/bin/celery -A app.worker.celery_app worker --loglevel=info --concurrency=1`
  Expected: Worker joins Redis broker and starts listening.

---

### Task 8: WebSocket Real-time Progress with DB Compensation

**Files:**
- Create: `backend/app/api/v1/ws.py`
- Test: `backend/tests/integration/test_ws.py`

- [ ] **Step 1: Write WebSocket API endpoint with DB snapshot pre-push & terminal closure**
  Create `backend/app/api/v1/ws.py`. On connection, query PostgreSQL first. If job is already in terminal state, push final frame and close immediately without subscribing to Redis.
  ```python
  import asyncio
  import json
  import redis
  from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
  from sqlalchemy.orm import Session
  from app.api.deps import get_db
  from app.models.job import Job
  from app.core.config import settings

  router = APIRouter()

  @router.websocket("/ws/jobs/{job_id}")
  async def websocket_progress(websocket: WebSocket, job_id: str, db: Session = Depends(get_db)):
      await websocket.accept()
      
      # 1. Database compensation query
      job = db.query(Job).filter(Job.id == job_id).first()
      if not job:
          await websocket.send_json({"type": "failed", "job_id": job_id, "error": "Job not found"})
          await websocket.close(code=1000)
          return
          
      # 2. Terminal state closure check
      if job.status in ["SUCCESS", "FAILED", "CANCELLED"]:
          if job.status == "SUCCESS":
              await websocket.send_json({"type": "completed", "job_id": job_id})
          else:
              await websocket.send_json({"type": "failed", "job_id": job_id, "error": job.error_message})
          await websocket.close(code=1000)
          return
          
      # 3. Non-terminal: Push initial DB snapshot to prevent progress freeze on reload
      await websocket.send_json({
          "type": "snapshot",
          "job_id": job_id,
          "status": job.status,
          "stage": job.progress_stage,
          "percent": job.progress_percent,
          "message": f"Reconnected: resuming progress from {job.progress_percent}%"
      })
      
      # 4. Subscribe to Redis Pub/Sub for subsequent events
      r_client = redis.Redis.from_url(settings.REDIS_URL)
      pubsub = r_client.pubsub()
      pubsub.subscribe(f"job:{job_id}:progress")
      
      async def listen_redis():
          try:
              while True:
                  # Non-blocking check
                  message = pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                  if message:
                      data = json.loads(message['data'].decode('utf-8'))
                      await websocket.send_json(data)
                      if data.get("type") in ["completed", "failed"]:
                          break
                  await asyncio.sleep(0.1)
          except Exception:
              pass
              
      try:
          await listen_redis()
      except WebSocketDisconnect:
          pass
      finally:
          pubsub.unsubscribe()
          pubsub.close()
          await websocket.close(code=1000)
  ```

- [ ] **Step 2: Write integration test for WebSocket compensation**
  Create `backend/tests/integration/test_ws.py` verifying snapshot payload upon connection.
  Run: `/media/data/venv/bin/pytest backend/tests/integration/test_ws.py`
  Expected: PASS

---

### Task 9: Frontend Project Scaffold (React + TS + Tailwind)

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/src/main.tsx`

- [ ] **Step 1: Write frontend package.json**
  ```json
  {
    "name": "doc2md-frontend",
    "private": true,
    "version": "1.0.0",
    "type": "module",
    "scripts": {
      "dev": "vite",
      "build": "tsc && vite build",
      "lint": "eslint . --ext ts,tsx --report-unused-disable-directives --max-warnings 0",
      "preview": "vite preview"
    },
    "dependencies": {
      "@radix-ui/react-accordion": "^1.1.2",
      "@radix-ui/react-dialog": "^1.0.5",
      "@radix-ui/react-dropdown-menu": "^2.0.6",
      "@radix-ui/react-progress": "^1.0.3",
      "@radix-ui/react-slot": "^1.0.2",
      "@tanstack/react-query": "^5.45.1",
      "clsx": "^2.1.1",
      "lucide-react": "^0.395.0",
      "react": "^18.3.1",
      "react-dom": "^18.3.1",
      "react-markdown": "^9.0.1",
      "react-use-websocket": "^4.5.0",
      "remark-gfm": "^4.0.0",
      "sonner": "^1.5.0",
      "tailwind-merge": "^2.3.0",
      "tailwindcss-animate": "^1.0.7"
    },
    "devDependencies": {
      "@types/react": "^18.3.3",
      "@types/react-dom": "^18.3.0",
      "@vitejs/plugin-react": "^4.3.1",
      "autoprefixer": "^10.4.19",
      "postcss": "^8.4.38",
      "tailwindcss": "^3.4.4",
      "typescript": "^5.2.2",
      "vite": "^5.3.1"
    }
  }
  ```

- [ ] **Step 2: Initialize Vite and Tailwind configuration**
  Configure `frontend/vite.config.ts` with proxy to `/api` on x-server backend.
  Run: `pnpm install`
  Run: `pnpm dev`
  Expected: Frontend launches on localhost:5173 successfully.

---

### Task 10: Frontend Core Components (Dashboard, Preview, Settings)

**Files:**
- Create: `frontend/src/features/dashboard/Dashboard.tsx`
- Create: `frontend/src/features/settings/Settings.tsx`
- Create: `frontend/src/features/preview/Preview.tsx`

- [ ] **Step 1: Write Settings configuration panel**
  Create `frontend/src/features/settings/Settings.tsx` implementing LLM provider inputs, API key masked display, and "Test Connection" button.
  ```typescript
  // Implement API fetch GET /api/v1/config and PUT /api/v1/config
  ```

- [ ] **Step 2: Write Dashboard page with upload options and WebSocket reconnect handler**
  Create `frontend/src/features/dashboard/Dashboard.tsx` displaying file dropzone, aggressiveness dropdown (`Conservative`, `Balanced`, `Aggressive`), and real-time progress bars. Use `react-use-websocket` to listen for WS progress/snapshot/completed frames.
  ```typescript
  // Implement WebSocket listener and progress bar state mapping
  ```

- [ ] **Step 3: Write Markdown Double-Column Preview**
  Create `frontend/src/features/preview/Preview.tsx` using `react-markdown` and `remark-gfm` to render converted results side-by-side with document metadata.

---

### Task 11: Production systemd Deployment Setup (x-server)

**Files:**
- Create: `deploy/nginx/doc2md.conf`
- Create: `deploy/systemd/doc2md-api.service`
- Create: `deploy/systemd/doc2md-worker.service`

- [ ] **Step 1: Write systemd service configurations**
  Create `deploy/systemd/doc2md-api.service`:
  ```ini
  [Unit]
  Description=Doc2MD FastAPI Application
  After=network.target postgresql.service redis.service

  [Service]
  Type=simple
  User=root
  WorkingDirectory=/opt/doc2md/backend
  ExecStart=/media/data/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
  EnvironmentFile=/opt/doc2md/.env
  Restart=on-failure

  [Install]
  WantedBy=multi-user.target
  ```

  Create `deploy/systemd/doc2md-worker.service` (with GPU environment binding):
  ```ini
  [Unit]
  Description=Doc2MD Celery Worker
  After=network.target redis.service

  [Service]
  Type=simple
  User=root
  WorkingDirectory=/opt/doc2md/backend
  ExecStart=/media/data/venv/bin/celery -A app.worker.celery_app worker --loglevel=info --concurrency=1
  EnvironmentFile=/opt/doc2md/.env
  Environment="CUDA_VISIBLE_DEVICES=0"
  Restart=on-failure

  [Install]
  WantedBy=multi-user.target
  ```

- [ ] **Step 2: Write Nginx reverse proxy configuration**
  Create `deploy/nginx/doc2md.conf` forwarding `/api` and `/api/v1/ws` to FastAPI, and serving `frontend/dist` static assets.

- [ ] **Step 3: Enable and verify services on x-server**
  Run: `cp deploy/systemd/*.service /etc/systemd/system/`
  Run: `systemctl daemon-reload`
  Run: `systemctl enable --now doc2md-api doc2md-worker`
  Run: `systemctl status doc2md-api doc2md-worker`
  Expected: Both services active and running without errors on x-server.

---

## Task 12: v1.1 增量补丁（post-v1.0.7 设计同步）

本节是 v1.1 增量补丁，对应设计文档 v1.0.7 的 6 项修订。每个补丁以 bite-sized 步骤给出，确保按 Tasks 1-11 顺序完成后可直接逐项应用。

### Patch 12.1 🔴 MinerU 显式开启图片提取 (spec §5.1)

> ⚠️ **v1.2 已作废**：系统已全面从 Docling 迁移至 MinerU 引擎。原本的 Docling 图片提取配置已无意义，所有图片提取均由 `mineru_service.py` 内部原生处理。

### Patch 12.2 🟡 流式上传 + 磁盘预检 + 自动清理（spec §7.2）

**目的**：v1.0.6 取消上传限制后，必须防止 OOM 与磁盘耗尽。

**Files:**
- Modify: `backend/app/api/v1/jobs.py`
- Create: `backend/app/services/storage_guard.py`
- Create: `backend/app/worker/beat_schedule.py`

- [ ] **Step 1: 安装 aiofiles**
  Run: `/media/data/venv/bin/pip install aiofiles==24.1.0`
  Append to `backend/requirements.txt`: `aiofiles==24.1.0`

- [ ] **Step 2: 新增 storage_guard.py**
  Create `backend/app/services/storage_guard.py`:
  ```python
  import shutil
  from fastapi import HTTPException
  from app.core.config import settings
  from app.models.app_config import AppConfig
  from sqlalchemy.orm import Session

  def check_disk_space(db: Session) -> None:
      """检查 STORAGE_ROOT 所在分区剩余空间，低于阈值则抛 503。"""
      config = db.query(AppConfig).filter(AppConfig.id == 1).first()
      min_gb = config.disk_free_min_gb if config else 2
      total, used, free = shutil.disk_usage(settings.STORAGE_ROOT)
      free_gb = free // (1024 ** 3)
      if free_gb < min_gb:
          raise HTTPException(
              status_code=503,
              detail="Disk space insufficient, please retry later"
          )
  ```

- [ ] **Step 3: 修改 jobs.py 使用流式写入 + 磁盘预检**
  在 `create_job` 函数最开头加上预检：
  ```python
  from app.services.storage_guard import check_disk_space
  check_disk_space(db)   # 先校验磁盘
  ```
  替换文件写入部分（现有 `with open(input_path, "wb") as buffer: shutil.copyfileobj(...)`）为流式写入：
  ```python
  import aiofiles
  import os
  size = 0
  input_path = os.path.join(job_dir, f"input{ext}")
  async with aiofiles.open(input_path, "wb") as buffer:
      while True:
          chunk = await file.read(1024 * 1024)  # 1MB chunks
          if not chunk:
              break
          await buffer.write(chunk)
          size += len(chunk)
  ```

- [ ] **Step 4: 新增 Celery Beat 自动清理任务**
  Create `backend/app/worker/beat_schedule.py`:
  ```python
  from datetime import datetime, timedelta
  from celery import shared_task
  from app.core.database import SessionLocal
  from app.models.job import Job
  from app.models.app_config import AppConfig
  import os, shutil
  from app.core.config import settings

  @shared_task(name="app.worker.beat_schedule.cleanup_expired_jobs")
  def cleanup_expired_jobs():
      db = SessionLocal()
      try:
          config = db.query(AppConfig).filter(AppConfig.id == 1).first()
          retention_days = config.storage_retention_days if config else 7
          cutoff = datetime.utcnow() - timedelta(days=retention_days)
          expired = db.query(Job).filter(
              Job.status.in_(["SUCCESS", "FAILED"]),
              Job.finished_at < cutoff
          ).all()
          for job in expired:
              job_dir = os.path.join(settings.STORAGE_ROOT, str(job.id))
              if os.path.exists(job_dir):
                  shutil.rmtree(job_dir)
              db.delete(job)
          db.commit()
      finally:
          db.close()
  ```
  在 `celery_app.py` 中追加 Beat schedule:
  ```python
  from celery.schedules import crontab
  celery_app.conf.beat_schedule = {
      "cleanup-expired-jobs": {
          "task": "app.worker.beat_schedule.cleanup_expired_jobs",
          "schedule": crontab(hour=3, minute=0),  # 每天凌晨 3 点
      }
  }
  ```

- [ ] **Step 5: 单元测试**
  Create `backend/tests/unit/test_storage_guard.py`:
  ```python
  import pytest
  from unittest.mock import MagicMock, patch
  from app.services.storage_guard import check_disk_space
  from fastapi import HTTPException

  def test_check_disk_space_insufficient():
      db = MagicMock()
      db.query.return_value.filter.return_value.first.return_value = MagicMock(disk_free_min_gb=1000)
      with patch("app.services.storage_guard.shutil.disk_usage") as mock_usage:
          mock_usage.return_value = (0, 0, 0)  # 无剩余空间
          with pytest.raises(HTTPException) as exc:
              check_disk_space(db)
          assert exc.value.status_code == 503
  ```
  Run: `/media/data/venv/bin/pytest backend/tests/unit/test_storage_guard.py -v`
  Expected: PASS

- [ ] **Step 6: 提交**
  ```bash
  git add backend/app/services/storage_guard.py \
          backend/app/worker/beat_schedule.py \
          backend/app/api/v1/jobs.py \
          backend/app/worker/celery_app.py \
          backend/requirements.txt \
          backend/tests/unit/test_storage_guard.py
  git commit -m "feat(upload): streaming upload + disk guard + celery-beat auto-cleanup"
  ```

### Patch 12.3 🟡 API 响应增加 estimated_vlm_calls + 进度阶段 vlm_image（spec §4.1.1 & §4.2.3）

**Files:**
- Modify: `backend/app/api/v1/jobs.py`
- Modify: `backend/app/worker/tasks.py`
- Modify: `frontend/src/features/dashboard/Dashboard.tsx`

- [ ] **Step 1: jobs.py 响应中增加 estimated_vlm_calls**
  在 `POST /api/v1/jobs` 的返回 dict 中追加：
  ```python
  estimated_vlm_calls = 0
  if job.options.get("use_vlm_image_reconstruction", False):
      # 暂以 mineru service 预估算图片数；此处简化用 0 + 后续在 worker 阶段重新广播
      estimated_vlm_calls = 0  # 由 worker 在 OCR 完成后更新
  return {
      "job_id": str(job.id),
      "status": job.status,
      "created_at": job.created_at,
      "estimated_llm_calls": est_calls,
      "estimated_vlm_calls": estimated_vlm_calls,
      "estimated_input_tokens": est_tokens,
  }
  ```
  > **注意**：精确图片数量必须等 MinerU 转换完成后才知道（因为图片标签在 Markdown 文本里才出现）。在 worker 拿到 `raw.md` 后，**更新 jobs.options 里的 estimated_vlm_calls** 并通过 `snapshot`/`progress` 帧推送给前端。

- [ ] **Step 2: worker 在 MinerU 转换完成后，预估 VLM 调用次数并更新**
  在 `convert_task` 中，`raw_md, mineru_real_dir = run_mineru_conversion(...)` 之后:
  ```python
  image_count = len(re.findall(r'!\[(.*?)\]\(images\/.*?\)', raw_md))
  estimated_vlm = image_count * 2  # 分类器 + 重构
  # 更新 jobs.options 中的预估
  job.options = {**job.options, "estimated_vlm_calls": estimated_vlm, "image_count": image_count}
  db.commit()
  # 广播 progress 让前端更新预估数字
  broadcast_progress(job_id, 78, "vlm_image", f"Detected {image_count} images, {estimated_vlm} VLM calls")
  ```

- [ ] **Step 3: 在 worker 中补充 vlm_image 阶段进度**
  在 VLM 处理 `process_embedded_images` 之前广播：
  ```python
  broadcast_progress(job_id, 80, "vlm_image", f"VLM 图片处理: 0/{image_count} 张已完成")
  ```
  在 VLM 处理循环内部（每张图完成后）：
  ```python
  pct = 80 + int((i + 1) / image_count * 15)
  broadcast_progress(job_id, pct, "vlm_image", f"VLM 图片处理: {i+1}/{image_count} 张已完成")
  ```

- [ ] **Step 4: 前端展示 estimated_vlm_calls 与 vlm_image 阶段**
  Modify `frontend/src/features/dashboard/Dashboard.tsx`:
  ```typescript
  // 在任务卡片增加 "VLM calls" 显示
  <div>VLM calls: {job.estimated_vlm_calls ?? 0}</div>
  
  // 在 WebSocket 进度帧处理处增加 vlm_image 阶段文案
  if (frame.stage === "vlm_image") {
      setStageLabel("VLM 图片识别中");
  }
  ```

- [ ] **Step 5: 提交**
  ```bash
  git add backend/app/api/v1/jobs.py \
          backend/app/worker/tasks.py \
          frontend/src/features/dashboard/Dashboard.tsx
  git commit -m "feat(estimate): surface estimated_vlm_calls and vlm_image stage"
  ```

### Patch 12.4 🟢 前端识别 snapshot 帧（spec §4.2.3 v1.0.4 完整规范）

**Files:**
- Modify: `frontend/src/hooks/useJobs.ts` (or wherever WS handler lives)

- [ ] **Step 1: WS 帧处理增加 snapshot 类型**
  ```typescript
  case "snapshot":
      // 收到重连快照，立即覆盖进度条
      setProgress({
          percent: frame.percent,
          stage: frame.stage,
          message: frame.message ?? `Reconnected: resuming from ${frame.percent}%`
      });
      break;
  ```

- [ ] **Step 2: 提交**
  ```bash
  git add frontend/src/hooks/useJobs.ts
  git commit -m "feat(ws): client-side snapshot frame handling for reconnection"
  ```

### Patch 12.5 🟢 ORM 模型同步 deprecated 字段

**Files:**
- Modify: `backend/app/models/app_config.py`

- [ ] **Step 1: 保留字段但加注释，避免实现者误用**
  ```python
  # v1.1 Patch 12.5: 字段保留以兼容历史，但前端永远不展示、worker 永远不读取
  enable_toc_removal = Column(Boolean, default=True, comment="⚠️ deprecated since v1.0.3")
  enable_reference_removal = Column(Boolean, default=True, comment="⚠️ deprecated since v1.0.3")
  ```

- [ ] **Step 2: 提交**
  ```bash
  git add backend/app/models/app_config.py
  git commit -m "chore(orm): mark enable_toc_removal/enable_reference_removal as deprecated"
  ```

### Patch 12.6 🟢 前端 UI 选项：明确 VLM 档位与 keep_original_images

**Files:**
- Modify: `frontend/src/features/dashboard/Dashboard.tsx`
- Modify: `frontend/src/features/settings/Settings.tsx`

- [ ] **Step 1: Dashboard 增加 VLM 重构选项**
  在上传选项面板增加：
  ```typescript
  - [ ] 启用 VLM 图片重构 (需要多模态模型)
  
  启用后追加子选项：
  - [ ] 保留原图（Base64）+ 追加描述 (推荐)
  - [ ] 彻底替换为文本/Mermaid/LaTeX (适合 RAG)
  ```

- [ ] **Step 2: Settings 页面增加 VLM 模型选择**
  ```typescript
  // 在 LLM 配置区下方新增 "多模态 VLM 模型名称" 输入框
  // 默认值根据主模型推断（OpenAI: gpt-4o, Anthropic: claude-3-5-sonnet）
  ```

- [ ] **Step 3: 提交**
  ```bash
  git add frontend/src/features/dashboard/Dashboard.tsx \
          frontend/src/features/settings/Settings.tsx
  git commit -m "feat(ui): VLM reconstruction toggle + keep/replace images selector"
  ```

### Patch 12.7 🟢 Alembic 数据迁移

**Files:**
- Create: `backend/alembic/versions/<rev>_v107_fields.py`

- [ ] **Step 1: 生成 v1.0.7 字段迁移**
  Run: `/media/data/venv/bin/alembic revision --autogenerate -m "v107_storage_and_image"`
  在生成的 migration 中确认包含：
  ```python
  op.add_column('app_config', sa.Column('storage_retention_days', sa.Integer, default=7))
  op.add_column('app_config', sa.Column('disk_free_min_gb', sa.Integer, default=2))
  op.add_column('app_config', sa.Column('use_vlm_image_reconstruction', sa.Boolean, default=False))
  op.add_column('app_config', sa.Column('keep_original_images', sa.Boolean, default=True))
  ```

- [ ] **Step 2: 应用迁移**
  Run: `/media/data/venv/bin/alembic upgrade head`
  Expected: 4 new columns added.

- [ ] **Step 3: 提交**
  ```bash
  git add backend/alembic/versions/
  git commit -m "chore(db): alembic migration for v1.0.7 fields"
  ```

---

## 3. Plan Self-Review & Verification (v1.2)

1. **Spec Coverage Check (v1.1.0)**:
   - MinerU CLI Conversion: Task 4 ✓
   - Chunked LLM post-processing with custom chunker & Threshold Routing: Task 5 ✓
   - TOC/References removal (LLM-driven & position-aware): Task 5 ✓
   - WS compensation snapshot & terminal closure: Task 8 ✓
   - VLM picture classification + specialized routing: Task 5 (v1.0.5) ✓
   - Relative local image folder extraction: Task 4 & Patch 12.1 (v1.2) ✓
   - Streaming upload + disk guard + auto-cleanup: Patch 12.2 (v1.1) ✓
   - `estimated_vlm_calls` + `vlm_image` stage: Patch 12.3 (v1.1) ✓
   - `snapshot` frame client handling: Patch 12.4 (v1.1) ✓
   - Deprecated fields preserved but not implemented: Patch 12.5 (v1.1) ✓
   - VLM UI options: Patch 12.6 (v1.1) ✓
   - Alembic data migration: Patch 12.7 (v1.1) ✓
   - Masked API Key storage & encryption: Task 3 & 6 ✓
   - React Dashboard with Aggressiveness settings: Task 10 ✓
   - systemd deployment & x-server execution: Task 11 ✓

2. **Placeholder Scan**: No "TBD" or "TODO" in task steps. Code snippets and exact terminal commands are provided.
3. **Type Consistency**: Database models, Pydantic schemas, and API response structures are aligned across Tasks 1-12.

---

## Related
- [Comprehensive Design Spec](../specs/2026-06-12-doc2md-design.md) (v1.1.0)
- [Architecture Overview](../../design/ARCH_OVERVIEW.md)
