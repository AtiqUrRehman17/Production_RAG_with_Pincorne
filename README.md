# RAG: Chat With Your Documents

Upload PDF, Word (DOCX) and text (TXT) files, then ask questions about them. Every answer comes from your
documents only and cites its sources like `[1]`. If the documents don't contain the answer, the system says
*"I couldn't find this in your documents."* instead of making one up.

Use it from the command line (`python main.py ...`) or through the web API (`python -m api`), which a React
frontend will use. Slow work (uploads, deletes, evaluations) runs in a background worker (`python -m workers`).
A full step-by-step explanation of the system is in `doc_RAG.pdf` (saved on the Desktop, outside this folder;
written before the backend was added).

## Contents

- [How it works](#how-it-works)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Setup](#setup)
- [Configuration (.env)](#configuration-env)
- [Commands](#commands)
  - [Documents: ingest, list, delete](#documents)
  - [Questions: search, ask, chat](#questions)
  - [Embedding test](#embedding-test)
  - [Evaluation: evaluate](#evaluation-evaluate)
  - [AI judges: RAGAS and DeepEval](#ai-judges-ragas-and-deepeval)
  - [LangSmith: dataset push and experiment](#langsmith-dataset-push-and-experiment)
  - [Accounts: users, make-admin, move-data](#accounts-users-make-admin-move-data)
- [Backend: API and background worker](#backend-api-and-background-worker)
  - [Starting it](#starting-it)
  - [Accounts and login](#accounts-and-login)
  - [Endpoints](#endpoints)
  - [Examples](#examples)
  - [Debugging with logs and traces](#debugging-with-logs-and-traces)
- [Golden dataset](#golden-dataset)
- [Free-tier limits](#free-tier-limits)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

## How it works

**Uploading a file** (`ingest`):

1. **Validate:** checks the type and size. It also confirms the content really matches the extension, and that
   the file isn't corrupted, password-protected, scanned or empty.
2. **Duplicate check:** the same user uploading the same file content is skipped (SHA-256 fingerprint).
3. **Load:** PDF page by page, DOCX and TXT as one document. Everything is turned into Markdown (headings,
   lists, tables).
4. **Clean:** fixes odd characters and words split at line ends, and removes repeated headers and footers.
5. **Metadata:** document ID, user, file name, type and page number.
6. **Chunk:** splits by headings, then by size (800 tokens, 100 overlap), and merges small pieces. Each chunk
   starts with `Document:` / `Section:`.
7. **Embed:** Gemini `gemini-embedding-001` (768 dimensions), with retries.
8. **Store:** Pinecone index `rag-documents`, one namespace per user.
9. **Register:** keeps a copy in `data/uploads/<user>/` and adds a record to the `documents` table of the app
   database (`data/app.db`). If anything fails, everything already done is undone (rollback).

Through the API, the upload is checked at once (steps 1 and 2) and the rest runs in the background worker.

**Answering a question** (`ask` / `chat`):

1. **Rewrite follow-ups** (chat only): "and the second one?" becomes a standalone question.
2. **Vector search:** finds the 20 most similar chunks in the user's namespace.
3. **Off-topic gate:** if the best similarity is below 0.55, the answer is "not found" and the LLM isn't called.
4. **Rerank:** the Pinecone `bge-reranker-v2-m3` reranker keeps at most 8 chunks scoring 0.15 or higher. If
   the reranker fails, embedding scores are used instead.
5. **Merge:** neighbouring chunks of the same section become one passage.
6. **Answer:** Groq `openai/gpt-oss-120b` answers only from the numbered sources, with `[n]` citations. The
   answer is streamed as it is written.
7. **Check citations:** every `[n]` must match a real source, and the sources are listed under the answer.

## Tech stack

| Part | Tool |
|---|---|
| Framework | LangChain |
| Answer model | Groq `openai/gpt-oss-120b` (or Google Gemini via `LLM_PROVIDER=gemini`) |
| Embeddings | Google Gemini `gemini-embedding-001`, 768 dimensions |
| Vector database | Pinecone (serverless, cosine) |
| Reranker | Pinecone-hosted `bge-reranker-v2-m3` |
| File parsing | PyMuPDF / PyMuPDF4LLM, python-docx, charset-normalizer |
| Tracing, datasets, experiments | LangSmith |
| AI judges | RAGAS 0.4.3 and DeepEval 4.3.3, judge model Groq `qwen/qwen3.8-27b` |
| Backend API | FastAPI + Uvicorn |
| Database | SQLAlchemy + SQLite (`data/app.db`; PostgreSQL later) |
| Background jobs | Arq + Redis |
| Accounts | Argon2 password hashes (argon2-cffi), JWT access tokens (PyJWT), refresh tokens in an HttpOnly cookie |
| Settings | pydantic-settings + `.env` |

## Project structure

```
RAG/
├── main.py                  # command-line interface (all commands)
├── .env                     # settings and secret API keys (never commit or share)
├── requirements.txt         # pinned package versions
├── docker-compose.yml       # Redis for the job queue (if Redis isn't installed already)
├── api/                     # web API (FastAPI): python -m api
│   ├── main.py              # the app: CORS, request IDs, error format, routers
│   ├── routers/             # endpoints: health, documents, jobs, conversations, search, feedback, admin
│   ├── schemas/             # request / response shapes
│   ├── services/            # chat, uploads, LangSmith traces
│   └── errors.py, middleware.py, dependencies.py, pagination.py
├── workers/                 # background worker (Arq): python -m workers
│   ├── worker.py            # job names, time limits, retries
│   ├── tasks.py             # ingest, delete, evaluation, feedback, daily log cleanup
│   ├── jobs.py              # job records (queued -> processing -> done / failed)
│   └── queue.py             # the Redis queue
├── accounts/                # register, login, tokens, password change, delete account, move data
├── database/                # tables, connection, saving logs to the database
├── utils/                   # config, errors, logging, hashing, token counting, LangSmith tracing
├── ingestion/               # validator, loaders, cleaning, registry, service (upload pipeline)
├── chunking/                # structure-aware chunker
├── embeddings/              # Gemini embeddings (retries, normalisation, checks)
├── vectordb/                # Pinecone store (add, list, delete vectors)
├── retrieval/               # retriever, reranker, citation labels
├── prompts/                 # answer prompt and follow-up rewrite prompt
├── llm/                     # chat model (Groq / Gemini) and the RAG chain
├── evaluation/
│   ├── datasets/golden_v1.json   # 42 test questions with answers and sources
│   ├── results/                  # saved evaluation runs (JSON)
│   ├── dataset.py, metrics.py, runner.py, report.py
│   ├── langsmith_dataset.py, langsmith_experiment.py
│   ├── judge.py                  # RAGAS judge
│   └── deepeval_judge.py         # DeepEval judge
└── data/
    ├── app.db               # app database: documents, jobs, chats, feedback, logs
    ├── uploads/<user>/      # copies of uploaded files
    ├── incoming/            # API uploads waiting for the worker (emptied automatically)
    └── documents.json.imported  # the old JSON registry, imported into app.db once (backup)
```

## Setup

Requirements: **Python 3.11** on Windows (the commands below use PowerShell; on macOS/Linux use
`source venv/bin/activate`).

```powershell
# 1. Create and activate the virtual environment
python -m venv venv
venv\Scripts\activate

# 2. Install the exact package versions
pip install -r requirements.txt

# 3. Create .env and fill in your keys (see Configuration below)

# 4. Check that everything starts
python main.py --help

# 5. For the API: Redis must run (see "Backend" below). Without a local Redis:
docker compose up -d redis
```

You need these accounts and API keys:

| Service | Used for | Where to get the key |
|---|---|---|
| Google AI Studio | Embeddings (always), answers if `LLM_PROVIDER=gemini` | https://aistudio.google.com/apikey |
| Groq | Answers and the AI judges | https://console.groq.com/keys |
| Pinecone | Vector database and reranker | https://app.pinecone.io |
| LangSmith (optional) | Tracing, datasets, experiments | https://smith.langchain.com → Settings → API Keys |

> `pip check` reports one known, harmless warning: `huggingface-hub` (installed with RAGAS) wants a newer
> `click` than the one DeepEval needs. Both only use `click` for command-line tools this project doesn't run.

## Configuration (.env)

All settings live in `.env` and are checked at start-up by `utils/config.py`. A wrong value stops the program
with a clear message. **Never commit or share `.env`: it contains your secret keys.**

```ini
# App
APP_ENV=development
LOG_LEVEL=WARNING

# LLM (answers and follow-up rewriting): groq or gemini
LLM_PROVIDER=groq
LLM_MAX_OUTPUT_TOKENS=2048

# Groq
GROQ_API_KEY=your-groq-key
GROQ_LLM_MODEL=openai/gpt-oss-120b
GROQ_TEMPERATURE=0.1

# Google Gemini (embeddings always; answers when LLM_PROVIDER=gemini)
GEMINI_API_KEY=your-gemini-key
GEMINI_LLM_MODEL=gemini-3.6-flash
LLM_THINKING_LEVEL=low
GEMINI_EMBEDDING_MODEL=gemini-embedding-001
EMBEDDING_DIMENSION=768            # 768, 1536 or 3072; must match the Pinecone index
EMBEDDING_BATCH_SIZE=100

# Pinecone
PINECONE_API_KEY=your-pinecone-key
PINECONE_INDEX_NAME=rag-documents
PINECONE_METRIC=cosine
PINECONE_CLOUD=aws
PINECONE_REGION=us-east-1

# User (CLI mode: no login yet)
DEFAULT_USER_ID=local-user

# File validation
ALLOWED_EXTENSIONS=pdf,txt,docx
MAX_FILE_SIZE_MB=50
MAX_PDF_PAGES=500
MIN_TEXT_CHARS_PER_PAGE=50         # below this a PDF is treated as scanned and rejected

# Local storage
UPLOAD_DIR=data/uploads
DOCUMENT_REGISTRY_PATH=data/documents.json   # old JSON registry: imported into the database once

# Chunking (tokens)
CHUNK_SIZE=800
CHUNK_OVERLAP=100
MIN_CHUNK_SIZE=50

# Retrieval
TOP_K=5                            # passages kept when reranking is off
MIN_RELEVANCE_SCORE=0.55           # off-topic gate
RELATIVE_SCORE_MARGIN=0.1

# Reranking
RERANKER_ENABLED=true
RERANK_MODEL=bge-reranker-v2-m3
RETRIEVAL_FETCH_K=20               # candidates sent to the reranker
RERANK_TOP_N=8                     # most passages kept
RERANK_MIN_SCORE=0.15
RERANK_MIN_BEST_SCORE=0.02         # the reranker's #1 only needs this

# Chat
CHAT_HISTORY_TURNS=5

# Evaluation
EVAL_USER_ID=eval
EVAL_DATASET_PATH=evaluation/datasets/golden_v1.json
EVAL_RESULTS_DIR=evaluation/results

# AI judge (RAGAS)
JUDGE_MODEL=qwen/qwen3.8-27b
JUDGE_REASONING_EFFORT=none        # none for Qwen; low / medium / high for gpt-oss models
JUDGE_METRICS=faithfulness,answer_relevancy,context_precision,context_recall
RAGAS_DO_NOT_TRACK=true

# AI judge (DeepEval), same judge model
DEEPEVAL_METRICS=correctness,citation_quality,completeness,contextual_relevancy
DEEPEVAL_THRESHOLD=0.7
DEEPEVAL_TELEMETRY_OPT_OUT=YES

# LangSmith
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=Rag
LANGSMITH_ENDPOINT=https://api.smith.langchain.com   # EU: https://eu.api.smith.langchain.com

# Backend API (python -m api)
API_HOST=127.0.0.1
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173   # web pages allowed to call the API (React dev server)
ADMIN_API_KEY=a-long-random-secret   # for scripts: opens /api/v1/admin via the X-Admin-Key header
DATABASE_URL=sqlite:///data/app.db
INCOMING_DIR=data/incoming

# Background worker (python -m workers)
REDIS_URL=redis://127.0.0.1:6379/1   # use 127.0.0.1, not localhost, on Windows
WORKER_MAX_JOBS=2                    # jobs one worker runs at the same time
LOG_DB_LEVEL=INFO                    # app logs saved to the database (never below LOG_LEVEL)
LOG_RETENTION_DAYS=14

# Accounts (login)
JWT_SECRET=a-long-random-secret      # signs login tokens (32+ characters); changing it logs everyone out
ACCESS_TOKEN_MINUTES=15              # how long a login token works; the frontend then refreshes it
REFRESH_TOKEN_DAYS=7                 # how long you stay logged in without using the app
REGISTRATION_OPEN=true               # false: nobody can create a new account
AUTH_COOKIE_SECURE=false             # true when the site runs on HTTPS (production)
```

`JWT_SECRET` and `ADMIN_API_KEY` were generated randomly into your `.env`. To make a new one: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Commands

Run every command from the project folder with the virtual environment active. Add `--help` to any command
to see its options, e.g. `python main.py evaluate --help`.

```powershell
python main.py --help
python main.py <command> --help
```

When `--user` is left out, the user is `DEFAULT_USER_ID` (`local-user`). For `evaluate` and `experiment` it is
`EVAL_USER_ID` (`eval`).

### Documents

#### `ingest`: upload a file

```powershell
python main.py ingest "C:\path\to\handbook.pdf"                 # upload for the default user
python main.py ingest "C:\path\to\notes.docx" --user alice      # upload for another user
python main.py ingest "C:\path\to\report.txt" --dry-run         # validate, load and chunk only; store nothing
python main.py ingest "C:\path\to\handbook.pdf" --dry-run --show-chunks 10   # also print the first 10 chunks
python main.py ingest "C:\path\to\handbook.pdf" --dry-run --show-chunks 0    # summary only, no chunks
```

| Option | Meaning |
|---|---|
| `file` | Path to a `.pdf`, `.docx` or `.txt` file |
| `--user USER_ID` | Owner of the document (letters, numbers, `-`, `_`; max 64) |
| `--dry-run` | Only validate, load and chunk; nothing is stored |
| `--show-chunks N` | With `--dry-run`: print the first N chunks (default 3) |

Uploading the same file again for the same user is skipped and shows the existing document ID.

#### `list`: show your documents

```powershell
python main.py list
python main.py list --user alice
python main.py list --user eval
```

Shows the ID, type, chunk count, upload time and file name, and compares the registered chunks with the
vectors in Pinecone.

#### `delete`: remove a document

```powershell
python main.py delete <document_id>
python main.py delete <document_id> --user alice
```

Deletes the document's vectors in Pinecone, its stored copy and its registry record. The document ID is shown
by `list`.

### Questions

#### `search`: see which passages are found (no AI answer)

```powershell
python main.py search "What temperature is the model called with?"
python main.py search "sick leave rules" --user alice
python main.py search "sick leave rules" --doc <document_id>                  # only one document
python main.py search "sick leave rules" --doc <id_1> --doc <id_2>            # several documents
python main.py search "sick leave rules" --top-k 3                            # at most 3 passages
python main.py search "sick leave rules" --full                               # print whole passages
python main.py search "sick leave rules" --no-rerank                          # embedding scores only
```

| Option | Meaning |
|---|---|
| `--user USER_ID` | Whose documents to search |
| `--doc DOCUMENT_ID` | Only search this document (repeat for several) |
| `--top-k N` | Most passages returned (defaults to `RERANK_TOP_N` / `TOP_K`) |
| `--full` | Print full passages instead of the first 400 characters |
| `--no-rerank` | Rank by embedding scores only (for comparison) |

#### `ask`: one question, one cited answer

```powershell
python main.py ask "What temperature is the model called with?"
python main.py ask "Who is the proposal prepared for?" --user alice
python main.py ask "What does section 3 say?" --doc <document_id>
python main.py ask "What temperature is the model called with?" --show-passages   # also print the sources sent to the LLM
python main.py ask "What temperature is the model called with?" --no-rerank
```

| Option | Meaning |
|---|---|
| `--user USER_ID` | Whose documents to use |
| `--doc DOCUMENT_ID` | Only use this document (repeatable) |
| `--show-passages` | Also print the passages given to the LLM |
| `--no-rerank` | Rank by embedding scores only |

#### `chat`: a conversation with your documents

```powershell
python main.py chat
python main.py chat --user alice
python main.py chat --doc <document_id>
python main.py chat --no-rerank
```

Inside the chat: type your questions; follow-ups like *"and the second one?"* are understood. Type `clear` to
start a new conversation and `exit` (or `quit`, or Ctrl+C) to leave. The last `CHAT_HISTORY_TURNS` turns are
remembered.

### Embedding test

#### `embed-test`: rank a file's chunks for a question, locally (no Pinecone)

```powershell
python main.py embed-test "C:\path\to\handbook.pdf" "How many sick days do I get?"
python main.py embed-test "C:\path\to\handbook.pdf" "How many sick days do I get?" --top 5
```

Useful to see how well embeddings match a question before uploading a file.

### Evaluation: `evaluate`

Runs the golden dataset through the real system and scores it. The dataset's documents must be uploaded for
the evaluation user first:

```powershell
python main.py ingest "C:\path\to\Quiz_Generation_Project_Documentation.pdf" --user eval
python main.py ingest "C:\path\to\AI-Guide-Chat-Gemini-Upgrade-Proposal.pdf" --user eval
```

Check the dataset and documents (no API calls):

```powershell
python main.py evaluate --check
python main.py evaluate --check --dataset evaluation/datasets/golden_v1.json --user eval
```

Run evaluations:

```powershell
python main.py evaluate                                   # full: retrieval + answers (tag "full")
python main.py evaluate --retrieval-only                  # search only, no LLM answers (tag "retrieval")
python main.py evaluate --no-rerank                       # without the reranker (tag "full-no-rerank")
python main.py evaluate --retrieval-only --no-rerank      # (tag "retrieval-no-rerank")
python main.py evaluate --tag baseline                    # name the run so it can be compared later
python main.py evaluate --ids q001,q016,q028              # only these questions
python main.py evaluate --limit 5                         # only the first 5 questions
python main.py evaluate --dataset evaluation/datasets/golden_v1.json --user eval
python main.py evaluate --no-failures                     # don't list the failed questions
python main.py evaluate --verbose                         # keep the per-step log messages
```

Compare two saved runs (tags or result file paths):

```powershell
python main.py evaluate --compare baseline fresh-groq
python main.py evaluate --compare evaluation/results/20261028T074010_baseline-groq-gptoss120b.json fresh-groq
```

| Option | Meaning |
|---|---|
| `--dataset FILE` | Dataset file (defaults to `EVAL_DATASET_PATH`) |
| `--user USER_ID` | User whose documents are searched (defaults to `EVAL_USER_ID`) |
| `--retrieval-only` | Only score retrieval (cheaper, faster) |
| `--no-rerank` | Evaluate with embedding scores only |
| `--tag NAME` | Name of this run (letters, numbers, `-`, `_`; max 40) |
| `--ids q001,q002` | Only these question IDs |
| `--limit N` | Only the first N questions |
| `--check` | Only validate the dataset and its documents |
| `--compare A B` | Compare two saved runs |
| `--no-failures` | Don't list failed questions in the report |
| `--judge [METRICS]` | Also grade with RAGAS (see below) |
| `--judge-run TAG` | Grade a saved run with RAGAS |
| `--deepeval [METRICS]` | Also grade with DeepEval (see below) |
| `--deepeval-run TAG` | Grade a saved run with DeepEval |
| `--verbose` | Keep the per-step log messages |

Every run is saved in `evaluation/results/` as `<time>_<tag>.json`.

**Scores:**

- **Retrieval:**
  - **Hit rate:** a correct source was found.
  - **MRR:** how high the first correct source was ranked.
  - **Precision:** the share of useful passages.
  - **Context recall:** the share of all needed sources that were found.
  - **Correct empty:** off-topic questions returned nothing.
- **Answers:**
  - **Refusal correct:** answered or said "not found" correctly.
  - **Key facts found.**
  - **Citations valid.**
  - **Cites the right source.**
- **Counts:** false refusals and hallucinations.

**When a question passes:**

- **Answerable:** it answered, all key facts are present, and it cites a correct source.
- **Unanswerable:** it said "not found".

Questions that crash (e.g. a rate limit) are reported separately, not counted as failures.

### AI judges: RAGAS and DeepEval

AI judges grade answers by **meaning** using a second model (`JUDGE_MODEL`, Groq `qwen/qwen3.8-27b`). Only
answerable questions are judged. Judge scores are shown next to the normal scores and **never change
pass/fail**. A score the judge couldn't give is left out, never counted as 0.

| Judge | Metrics (score 0 to 1) |
|---|---|
| RAGAS | `faithfulness`, `answer_relevancy`, `context_precision`, `context_recall` |
| DeepEval | `correctness`, `citation_quality`, `completeness`, `contextual_relevancy`. Each comes with a written reason; a score of `DEEPEVAL_THRESHOLD` (0.7) or more counts as a pass |

**RAGAS:**

```powershell
python main.py evaluate --judge                                        # new full run + all RAGAS metrics
python main.py evaluate --judge faithfulness                           # only some metrics
python main.py evaluate --judge faithfulness,answer_relevancy
python main.py evaluate --ids q001,q020 --judge                        # small judged run
python main.py evaluate --judge-run fresh-groq                         # grade a saved run (saved as fresh-groq-judged)
python main.py evaluate --judge-run fresh-groq --judge faithfulness    # saved run, some metrics
python main.py evaluate --judge-run fresh-groq --tag my-judged-run     # choose the saved name
```

**DeepEval:**

```powershell
python main.py evaluate --deepeval                                     # new full run + all DeepEval checks
python main.py evaluate --deepeval correctness,completeness            # only some checks
python main.py evaluate --ids q001,q020,q041 --deepeval                # small judged run (good first test)
python main.py evaluate --deepeval-run fresh-groq                      # grade a saved run
python main.py evaluate --deepeval-run fresh-groq --deepeval citation_quality
python main.py evaluate --deepeval-run fresh-groq --tag my-deepeval-run
```

**Both judges:**

```powershell
python main.py evaluate --judge --deepeval                             # new run, both judges
python main.py evaluate --judge-run fresh-groq --deepeval              # saved run, both judges
python main.py evaluate --deepeval-run fresh-groq --judge              # same, the other way round
python main.py evaluate --compare fresh-groq fresh-groq-judged         # compare runs, including judge scores
```

`--judge-run` and `--deepeval-run` can't be used together. To grade a saved run with both judges, add the other
judge's option as shown above. When a saved run is graded by one judge, the scores of the other judge are kept.

### LangSmith: dataset push and experiment

These need `LANGSMITH_API_KEY` in `.env`.

#### `dataset push`: upload / sync the golden dataset

```powershell
python main.py dataset push --dry-run                    # show what would change, upload nothing
python main.py dataset push                              # create or sync the dataset (named golden_v1)
python main.py dataset push --tag v1                     # sync and name this dataset version
python main.py dataset push --name my-dataset            # use another LangSmith dataset name
python main.py dataset push --dataset evaluation/datasets/golden_v1.json --name golden_v1 --tag v2
```

Questions are matched by ID: new ones are created, changed ones updated and removed ones deleted. Pushing again
never creates duplicates.

#### `experiment`: run the dataset in LangSmith

```powershell
python main.py experiment                                # full run (answers + scores)
python main.py experiment --retrieval-only               # search only
python main.py experiment --no-rerank                    # without the reranker
python main.py experiment --split table                  # only one question type
python main.py experiment --split table --split two-part # several types
python main.py experiment --version v1                   # a tagged dataset version
python main.py experiment --repetitions 3                # each question 3 times (1-5), to test stability
python main.py experiment --prefix tuning-rerank         # start of the experiment name
python main.py experiment --name golden_v1 --dataset evaluation/datasets/golden_v1.json --user eval
python main.py experiment --judge                        # + RAGAS columns (ragas_*)
python main.py experiment --judge faithfulness
python main.py experiment --deepeval                     # + DeepEval columns (deepeval_*, reason as comment)
python main.py experiment --deepeval correctness
python main.py experiment --judge --deepeval             # both judges
python main.py experiment --verbose
```

| Option | Meaning |
|---|---|
| `--dataset FILE` | Local dataset file (says which documents must be uploaded) |
| `--name NAME` | LangSmith dataset name (defaults to the dataset label, e.g. `golden_v1`) |
| `--user USER_ID` | User whose documents are searched (defaults to `EVAL_USER_ID`) |
| `--retrieval-only` | Only score retrieval |
| `--no-rerank` | Rank by embedding scores only |
| `--split TYPE` | Only questions of this type (repeatable) |
| `--version TAG` | Dataset version tag (defaults to the latest) |
| `--repetitions N` | Run every question N times (1-5) |
| `--prefix NAME` | Start of the experiment name |
| `--judge [METRICS]` | Also grade with RAGAS |
| `--deepeval [METRICS]` | Also grade with DeepEval |
| `--verbose` | Keep the per-step log messages |

Split types: `clear`, `reworded`, `unusual-wording`, `two-part`, `table`, `specific-doc`, `unanswerable`,
`off-topic`, `follow-up`.

**Tracing:** with `LANGSMITH_TRACING=true`, the commands `ingest`, `search`, `ask`, `chat`, `evaluate` and
`embed-test` are traced in the LangSmith project `LANGSMITH_PROJECT`. Set it to `false` to switch tracing off.

### Accounts: users, make-admin, move-data

Accounts are created through the API (`POST /api/v1/auth/register`); these commands manage them.

```powershell
python main.py users                                    # list accounts: ID, role, active, created, email
python main.py make-admin you@example.com               # give an account admin rights
python main.py make-admin you@example.com --remove      # take them away
python main.py move-data --from local-user --to you@example.com   # give one user's documents and chats to an account
```

| Command | Option | What it does |
|---|---|---|
| `make-admin` | `email` | The account to change |
| | `--remove` | Make it a normal user again |
| `move-data` | `--from USER_ID` | Current owner, e.g. `local-user` (the CLI's default user) |
| | `--to EMAIL` | The account that receives the documents (vectors, files, records) and chats |

To use the CLI on an account's documents, pass its ID (from `python main.py users`) as `--user`, e.g.
`python main.py ask "..." --user <account id>`.

## Backend: API and background worker

The backend is a thin layer over the same code the CLI uses. It has three parts:

```
React frontend ──HTTP/JSON──► API (FastAPI, python -m api) ──► the same engine as the CLI
                                   │  ▲                          (ingestion, retrieval, llm, evaluation)
                     put job in    │  │ read status
                                   ▼  │
                            Redis queue ──► Worker (python -m workers): uploads, deletes,
                                                    evaluations, feedback to LangSmith
                                   both use the database data/app.db
```

- **API:** answers requests. Questions are answered directly (optionally streamed word by word). Slow work is
  handed to the worker, and the API replies at once with a job to follow.
- **Worker:** a separate program that takes jobs from the Redis queue. If a job fails for a passing reason
  (network, Pinecone or embedding error), it is tried again up to 3 times (after 30 s, then 60 s).
- **Database** (`data/app.db`, SQLite): documents, jobs, conversations, messages, feedback and app logs. The
  CLI and the API share the same document list.

Every endpoint except health and `/auth` needs a login: each account sees only its own documents, chats and
jobs (its vectors are in a Pinecone namespace named after its account ID). Admin endpoints need an admin
account, or the `ADMIN_API_KEY` for scripts. The CLI is unchanged and keeps using `--user`.

### Starting it

Redis must be running. If Redis is installed on this PC, it is already running. Otherwise use
`docker compose up -d redis` (stop it with `docker compose stop redis`).

Then open **two terminals** in the project folder (virtual environment active):

```powershell
# Terminal 1: the background worker (Ctrl+C to stop)
python -m workers

# Terminal 2: the API (Ctrl+C to stop)
python -m api
python -m api --reload      # development: restarts when the code changes
```

Then open:

| Address | What it is |
|---|---|
| http://127.0.0.1:8000/docs | Interactive docs: try every endpoint in the browser |
| http://127.0.0.1:8000/redoc | The same docs, easier to read |
| http://127.0.0.1:8000/openapi.json | Machine-readable description (can generate TypeScript types for React) |
| http://127.0.0.1:8000/api/v1/health/ready | Are the database, Redis, worker, Pinecone and LangSmith reachable? |

In `/docs`: run **POST /api/v1/auth/login** (or register), copy the `access_token`, click **Authorize** at the
top and paste it. Every endpoint then runs as you. (Admin endpoints also have an `X-Admin-Key` field.)

### Accounts and login

```
Register / Login ──► access token (in the reply, works 15 min)  +  refresh token (HttpOnly cookie, 7 days)
Every request    ──► header  Authorization: Bearer <access token>
Token expired    ──► POST /auth/refresh (the browser sends the cookie) ──► new access token
Logout           ──► the refresh token is cancelled on the server
```

- **Passwords** are stored only as Argon2 hashes. Rules: 8 to 128 characters, not your email address.
- **Refresh tokens** are kept in a cookie that page scripts can't read (`HttpOnly`), is only sent to
  `/api/v1/auth` and never with requests started by other websites (`SameSite=Strict`). Each refresh replaces
  it; if an old one is used again (it was copied), that login ends everywhere and a warning is logged.
- **Limits:** 5 wrong passwords for one email → wait 15 minutes; 20 login attempts per IP address per 15
  minutes; 5 registrations per IP address per hour. The reply is `429 too_many_attempts` with `Retry-After`.
- A wrong email and a wrong password get the same message, so nobody can find out which emails have accounts.
- **Changing the password** logs out every other device; this device gets new tokens.
- **Admins:** `python main.py make-admin <email>` (takes effect at the next login or refresh).
- **Your earlier documents:** the **first** account registered automatically receives everything stored under
  `DEFAULT_USER_ID` (`local-user`): documents, vectors, files and chats. The register reply has a
  `transfer_job_id` to follow (the worker must be running). Later: `python main.py move-data --from local-user --to <email>`.
- **For the React app:** keep the access token in memory (not in localStorage), send the cookie with
  `credentials: "include"` on the `/auth` calls, and call `/auth/refresh` when a request answers
  `401 token_expired` (and once when the page loads, to stay logged in). Use the same host name for the
  frontend and the API (`localhost` for both, or a Vite proxy), or the browser won't send the cookie.

### Endpoints

Every endpoint starts with `/api/v1`. Lists are paged: `?limit=20`, then `?cursor=<next_cursor>` from the
previous page (`next_cursor` is `null` on the last page).

**Health**

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | The server is running |
| GET | `/health/ready` | Database, Redis, worker, Pinecone and LangSmith checks, plus which API keys are set (never their values). 503 if a required part is down |

**Accounts** (no login needed for register, login, refresh and logout)

| Method | Path | What it does |
|---|---|---|
| POST | `/auth/register` | Create an account and log in: `{"email", "password", "name"}` → access token, user, `transfer_job_id` |
| POST | `/auth/login` | Log in: `{"email", "password"}` → access token and user; sets the refresh cookie |
| POST | `/auth/refresh` | New access token (uses and replaces the refresh cookie) |
| POST | `/auth/logout` | Log out this device (cancels the refresh token, clears the cookie) |
| GET | `/auth/me` | Who is logged in: id, email, name, role |
| PATCH | `/auth/me` | Change your name: `{"name"}` |
| POST | `/auth/change-password` | `{"current_password", "new_password"}`; logs out your other devices, returns new tokens |
| DELETE | `/auth/me` | Delete your account with all documents, vectors, files and chats: `{"password"}` |

**Documents and jobs** (login needed from here on)

| Method | Path | What it does |
|---|---|---|
| POST | `/documents` | Upload a file (form field `file`). Quick checks run at once; then **202** with a job |
| GET | `/documents` | Your documents, newest first |
| GET | `/documents/{document_id}` | One document |
| DELETE | `/documents/{document_id}` | Delete it and its chunks (**202** with a job) |
| GET | `/jobs` | Your recent jobs. Filters: `?status=queued&status=processing`, `?type=ingest` |
| GET | `/jobs/{job_id}` | One job: `queued` → `processing` → `done` (with `result`) or `failed` (with `error`) |

**Chat and search**

| Method | Path | What it does |
|---|---|---|
| POST | `/conversations` | Start a chat. Optional: `title`, `document_ids` (only use these documents) |
| GET | `/conversations` | Your chats, most recently used first |
| GET | `/conversations/{id}` | A chat with all its messages, citations and feedback |
| PATCH | `/conversations/{id}` | Rename it or change its documents |
| DELETE | `/conversations/{id}` | Delete it and its messages |
| POST | `/conversations/{id}/messages` | Ask a question; returns the saved question and answer. Optional `no_rerank` |
| POST | `/conversations/{id}/messages/stream` | The same, streamed as Server-Sent Events (see below) |
| POST | `/search` | Retrieval only: the passages that would be used (`question`, optional `document_ids`, `top_k`, `no_rerank`) |
| POST | `/messages/{message_id}/feedback` | 👍 / 👎 on an answer: `{"rating": "up" or "down", "comment": "..."}` (also copied to the LangSmith trace) |
| DELETE | `/messages/{message_id}/feedback` | Remove that feedback |

The streaming endpoint sends these events:

| Event | Data |
|---|---|
| `question` | The saved question (a message) |
| `token` | `{"text": "..."}`: the next piece of the answer |
| `answer` | The saved answer with `citations`, `found`, `searched_for`, `trace_id`, `latency_ms` |
| `error` | `{"error": {...}}` in the usual error format |

**Admin** (an admin account's login, or the header `X-Admin-Key: <ADMIN_API_KEY>`)

| Method | Path | What it does |
|---|---|---|
| GET | `/admin/logs` | App logs of the API and worker. Filters: `level` (this level and above), `request_id`, `q` (text), `source` (`api` / `worker`), `since`, `until` |
| GET | `/admin/traces` | Recent LangSmith traces. Filters: `errors_only`, `min_seconds` (slow ones), `since` (default: last 7 days), `conversation_id`, `request_id` |
| GET | `/admin/traces/{trace_id}` | One trace step by step (rewrite, retrieval, rerank, answer) with times, tokens, errors, inputs and outputs, and a link to open it in LangSmith |
| GET | `/admin/stats` | Last `hours` (default 24): questions, answered / not found / errors, average and p95 response time, feedback, jobs, warnings and errors |
| GET | `/admin/jobs` | Jobs of every user, including evaluations |
| GET | `/admin/jobs/{job_id}` | Any job (evaluations show `progress`: step, done, total) |
| POST | `/admin/evaluations` | Start an evaluation (background job). Body: `retrieval_only`, `no_rerank`, `tag`, `ids`, `limit`, `ragas`, `ragas_metrics`, `deepeval`, `deepeval_metrics`; or `saved_run` (a tag) with `ragas` / `deepeval` to only grade a saved run |
| GET | `/admin/evaluations` | Saved runs, newest first (the same files the CLI writes) |
| GET | `/admin/evaluations/{tag}` | One saved run with every question's result |
| GET | `/admin/evaluations/compare?a=TAG&b=TAG` | What changed from run A to run B (like `evaluate --compare`) |

**Errors** always look the same, and `message` is safe to show to the user:

```json
{"error": {"code": "duplicate_document", "message": "This file was already uploaded as 'report.pdf'.",
           "request_id": "3f2a9c1d8e7b4a60", "details": {"document_id": "..."}}}
```

Common codes: `invalid_file` (400), `validation_error` / `weak_password` (422), `not_authenticated` /
`token_expired` / `token_revoked` / `invalid_credentials` / `session_expired` (401), `forbidden` /
`wrong_password` / `registration_closed` (403), `document_not_found` / `conversation_not_found` (404),
`duplicate_document` / `upload_in_progress` / `email_taken` (409), `file_too_large` (413), `rate_limited` /
`too_many_attempts` (429), `llm_error` / `vector_store_error` (502), `queue_unavailable` (503),
`internal_error` (500). On `token_expired`, call `/auth/refresh` and repeat the request.

### Examples

PowerShell has its own `curl`, so these use `curl.exe`. Logging in is easiest with `Invoke-RestMethod`,
which gives you the token to keep in a variable:

```powershell
# Is everything reachable?
curl.exe http://127.0.0.1:8000/api/v1/health/ready

# Register (once) or log in, and keep the token in $auth (it works 15 minutes; log in again after)
$body = @{ email = "you@example.com"; password = "your-password"; name = "Your Name" } | ConvertTo-Json
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/auth/register -ContentType "application/json" -Body $body
$login = Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/api/v1/auth/login -ContentType "application/json" -Body $body
$auth = "Authorization: Bearer $($login.access_token)"
curl.exe -H $auth http://127.0.0.1:8000/api/v1/auth/me

# Upload a file, then follow the job until it is "done"
curl.exe -H $auth -F "file=@C:\path\to\handbook.pdf" http://127.0.0.1:8000/api/v1/documents
curl.exe -H $auth http://127.0.0.1:8000/api/v1/jobs/<job id>

# List and delete documents
curl.exe -H $auth http://127.0.0.1:8000/api/v1/documents
curl.exe -H $auth -X DELETE http://127.0.0.1:8000/api/v1/documents/<document id>

# Start a chat and ask (whole answer, then streamed)
curl.exe -H $auth -X POST http://127.0.0.1:8000/api/v1/conversations -H "Content-Type: application/json" -d "{}"
curl.exe -H $auth -X POST http://127.0.0.1:8000/api/v1/conversations/<id>/messages -H "Content-Type: application/json" -d '{\"question\": \"What is the refund period?\"}'
curl.exe -H $auth -N -X POST http://127.0.0.1:8000/api/v1/conversations/<id>/messages/stream -H "Content-Type: application/json" -d '{\"question\": \"And for businesses?\"}'

# Feedback on an answer
curl.exe -H $auth -X POST http://127.0.0.1:8000/api/v1/messages/<answer id>/feedback -H "Content-Type: application/json" -d '{\"rating\": \"up\"}'

# Stay logged in with the refresh cookie (curl keeps it in a file), then log out
curl.exe -c cookies.txt -X POST http://127.0.0.1:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{\"email\": \"you@example.com\", \"password\": \"your-password\"}'
curl.exe -b cookies.txt -c cookies.txt -X POST http://127.0.0.1:8000/api/v1/auth/refresh
curl.exe -b cookies.txt -X POST http://127.0.0.1:8000/api/v1/auth/logout

# Admin: logged in as an admin account, use $auth. For scripts, the admin key works too
# (keep it in a variable; never paste it into shared notes)
$h = "X-Admin-Key: <your ADMIN_API_KEY>"
curl.exe -H $h "http://127.0.0.1:8000/api/v1/admin/logs?level=WARNING"
curl.exe -H $h "http://127.0.0.1:8000/api/v1/admin/traces?errors_only=true"
curl.exe -H $h "http://127.0.0.1:8000/api/v1/admin/stats?hours=24"
curl.exe -H $h -X POST http://127.0.0.1:8000/api/v1/admin/evaluations -H "Content-Type: application/json" -d '{\"retrieval_only\": true, \"ids\": [\"q001\", \"q002\"], \"tag\": \"api-check\"}'
curl.exe -H $h "http://127.0.0.1:8000/api/v1/admin/evaluations/compare?a=fresh-groq&b=rerank-015"
```

The `/docs` page is often easier than curl: every endpoint has a **Try it out** button.

### Debugging with logs and traces

Every request gets a **request ID**. It is returned in the `X-Request-ID` response header and in every error
body. The same ID is written on every log line (in the terminal as `[3f2a9c1d8e7b4a60]`, and in the database),
including the worker's lines for jobs that request started, and saved on the request's LangSmith traces.

To find out what went wrong:

1. Take the request ID from the error (or from the frontend later: "ref: 3f2a9c1d8e7b4a60").
2. `GET /api/v1/admin/logs?request_id=3f2a9c1d8e7b4a60&level=DEBUG`: every saved log line of that request,
   with the full traceback of unexpected errors.
3. `GET /api/v1/admin/traces?request_id=3f2a9c1d8e7b4a60`: its trace. Open it with
   `GET /api/v1/admin/traces/{trace_id}` (or its `url` in LangSmith) to see which step failed or was slow.
4. For a chat answer, the message itself carries its `trace_id`.

Good starting points: `/admin/stats` (is something getting worse?), `/admin/logs?level=ERROR`,
`/admin/traces?errors_only=true` and `/admin/traces?min_seconds=10`.

Which log lines are kept: `LOG_LEVEL` decides what is logged at all (your `.env` has `WARNING`), and
`LOG_DB_LEVEL` decides which of those are saved to the database. Use `LOG_LEVEL=INFO` to also see the normal
step-by-step lines. Log lines older than `LOG_RETENTION_DAYS` are deleted by the worker every night at 03:00
(and when it starts).

## Golden dataset

`evaluation/datasets/golden_v1.json` holds 42 test questions about two test documents, uploaded for the user
`eval`.

| Type | Count | Type | Count |
|---|---|---|---|
| clear | 11 | specific-doc | 3 |
| reworded | 8 | unanswerable | 4 |
| unusual-wording | 4 | off-topic | 2 |
| two-part | 4 | follow-up | 3 |
| table | 3 | | |

Each item has:

- `id`, `question`, `type` and `answerable`
- `expected_answer`
- `key_facts`: each fact is a text, or a list of accepted spellings
- `expected_sources` and `also_acceptable`: file + section or page
- for follow-ups, a `history`

After editing the file:

```powershell
python main.py evaluate --check          # validate it
python main.py dataset push --tag v2     # sync it to LangSmith as a new version
python main.py experiment --version v2   # run that version
```

## Free-tier limits

| Service | Limit to keep in mind |
|---|---|
| Groq (per model) | Requests and tokens per minute and per day. The judge model `qwen/qwen3.8-27b` allows 1,000 output tokens per minute and 200,000 tokens per day. See https://console.groq.com/settings/limits |
| Pinecone reranker | 500 rerank requests per month on the Starter plan (one per question) |
| Gemini | Embedding quota per minute and day. As the answer model, the free tier allows only about 20 requests per day, which is why answers use Groq |

A full judged run can use a large part of the judge model's daily tokens. When the daily limit is reached, the
judges stop cleanly: scores already given are kept and the report says so. Grade the saved run again later
with `--judge-run` / `--deepeval-run`. To save tokens, start with `--ids`, `--limit` or a single metric.

## Troubleshooting

| Message | What to do |
|---|---|
| `This PDF looks scanned` | Scanned PDFs need OCR, which isn't supported yet. Use a PDF with selectable text. |
| `Skipped: This file was already uploaded` | The same file is already stored for this user; use `list` to see it. |
| `I couldn't find this in your documents` for "what is this file about?" | Fixed: questions about a whole document ("what is this file about?", "summarize the document", "main points of this pdf") skip the reranker, which scores every chunk near 0 for them, and get chunks spread over the document instead (logged as "Overview question"). Other vague questions ("what is this about?" is covered, "tell me everything" isn't) can still get "not found": name the file or ask something specific. |
| `Pinecone index ... has dimension ...` | `EMBEDDING_DIMENSION` must match the Pinecone index (768). |
| `These dataset documents are not uploaded for user 'eval'` | Run the `ingest ... --user eval` commands shown in the message. |
| `Groq's rate limit ... was reached (429)` | Wait (per-minute limit) or try tomorrow (daily limit). |
| `Groq's daily limit for the judge model is used up` | Wait until tokens free up, then grade the saved run again with `--judge-run` / `--deepeval-run`. |
| `LANGSMITH_API_KEY is not set` | Add the key to `.env` to use `dataset push` and `experiment`. |
| `No saved run found for '...'` | Check the tag; saved runs are in `evaluation/results/`. |
| API: `queue_unavailable` (503) | Redis isn't reachable. Start it (`docker compose up -d redis`) and check `REDIS_URL`. |
| API: jobs stay `queued` | The worker isn't running: `python -m workers`. `GET /api/v1/health/ready` shows `"worker": false`. |
| A job stays `processing` after the worker was closed | A worker that stops without warning (window closed, process killed) leaves its job locked. A running worker notices within about a minute and runs the job again (or marks it failed when no tries are left), see `workers/recovery.py`. |
| Upload slow, then `Gemini's embedding limit was reached` | The free tier allows 100 embedding requests and 30,000 tokens per minute (plus a daily amount). Large files are embedded over several minutes, waiting as long as Gemini asks; if the limit doesn't reset, try again later. |
| API: `forbidden` (403) on admin endpoints | The account isn't an admin: `python main.py make-admin <email>`, then log in again. |
| API: `not_authenticated` / `token_expired` (401) | Log in, or refresh the token (`POST /api/v1/auth/refresh`). |
| API: `too_many_attempts` (429) on login | Too many wrong passwords: wait the minutes the message says. |
| API won't start: `JWT_SECRET must be set` | Add `JWT_SECRET` (32+ random characters) to `.env`. |
| Browser: logged out after every reload | The refresh cookie isn't sent: use the same host for frontend and API (`localhost`), and `credentials: "include"`. |
| Redis `Timeout connecting to server` on Windows | Use `127.0.0.1` instead of `localhost` in `REDIS_URL`. |
| Browser: `blocked by CORS policy` | Add the frontend's address to `CORS_ORIGINS` and restart the API. |

## Roadmap

- [x] Phase 1: RAG for digital PDF, DOCX and TXT (validation, chunking, embeddings, Pinecone, reranking,
  cited answers, chat)
- [x] Local evaluation with a golden dataset
- [x] Phase A / A2: LangSmith tracing
- [x] Phase B: dataset in LangSmith
- [x] Phase C: LangSmith experiments
- [x] Phase D: AI judges (RAGAS, DeepEval)
- [ ] Phase E: online evaluation of real conversations
- [ ] OCR for scanned PDFs
- [x] Web API (FastAPI) with streaming chat, feedback, logs and trace endpoints
- [x] Background jobs (Arq + Redis) for uploads, deletes and evaluations
- [x] React frontend (`frontend/`, see its README)
- [x] Accounts: register, login, refresh, logout, password change, delete account; per-user data; admin role
- [ ] More security: forgot-password and email verification (need an email service), Google login, rate limits
  on the other endpoints
