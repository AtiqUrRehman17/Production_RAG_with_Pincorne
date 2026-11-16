# RAG Documents: frontend

React + TypeScript web app for the RAG backend (`../api`). Built with Vite, Tailwind CSS,
React Router and TanStack Query.

## Start

Needs Node 22.13 or newer. The backend must be running (`python -m api` from the project root,
plus `python -m workers` for uploads).

```powershell
cd frontend
npm install        # first time only
npm run dev        # http://localhost:5173
```

The dev server passes every `/api/*` request on to the backend (`http://127.0.0.1:8000` by default;
set `API_TARGET` in `frontend/.env` to change it, see `.env.example`). The browser therefore sees a
single site, which the login cookie needs.

| Command | What it does |
|---|---|
| `npm run dev` | Dev server with instant reload |
| `npm run build` | Type-check, then build to `dist/` |
| `npm run typecheck` | Type-check only |
| `npm run lint` | ESLint |
| `npm run preview` | Serve the built `dist/` on http://localhost:4173 |

## Structure

```
src/
  api/            one file per backend area; all calls go through client.ts
    client.ts     fetch wrapper: access token, refresh on 401, ApiError
    types.ts      request and response shapes (mirrors api/schemas)
  auth/           login state (AuthProvider, useAuth) and route guards
  components/     shared pieces: app frame, icons, dialogs, toasts, source card
    ui.ts         shared class names (buttons, fields, cards, badges)
  lib/            query client, cache keys, theme, toasts, formatting, answer text
  pages/
    auth/         login and register
    chat/         chat list, streamed answers with citations, feedback, document picker
    documents/    upload with progress, job tracking, document list, passage search
    admin/        overview, logs, traces (with step view), jobs, evaluations
    AccountPage   name, password, log out, delete account
  router.tsx      the routes
  main.tsx        entry point
```

Light and dark mode follow the system setting until the moon/sun button in the side bar is used
(remembered in this browser).

## Login

- The **access token** (15 minutes) lives only in memory and is sent as `Authorization: Bearer`.
- The **refresh token** is an HttpOnly cookie that page scripts can't read. After a page reload,
  or when a call gets 401, `client.ts` calls `/auth/refresh` once and repeats the call.
- Only one refresh runs at a time, even across tabs (`navigator.locks`). The backend replaces the
  refresh token on every use and treats a reused one as stolen.

## Screens

| Screen | What it does |
|---|---|
| Login / Register | Split page; password strength hint; a new account goes to Documents |
| Chat | Chats grouped by date with search; answers streamed word by word with a Stop button; numbered citations that open the source passage; thumbs up/down with an optional comment; "Searched for" on follow-ups; which documents a chat uses; not-found and error states (with request ID and Try again); admins get a link to the answer's trace |
| Documents | Drag-and-drop upload with real upload progress, then the background job (queued, processing, ready or failed with the reason); list with Chat / Delete; passage search without an answer |
| Account | Change name or password (logs out other devices), log out, delete the account |
| Admin | Overview (questions, not-found rate, answer time, feedback, system checks, jobs, recent errors); logs with filters and request-ID links; LangSmith traces with a step-by-step timeline; all jobs; evaluations (start, progress, run details, compare two runs) |

The admin tab, request-ID filter and open trace are in the URL (`/admin?tab=logs&rid=...`), so they can be bookmarked and shared.
