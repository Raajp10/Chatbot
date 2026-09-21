# PNW Student Knowledge Chatbot

A chatbot that answers Purdue University Northwest (PNW) students' questions about university policies, deadlines, procedures, courses, and programs, grounded in approved PNW sources.

This is a course-project design. Design artifacts (spec, plan, research, data model, API contract, quickstart, tasks) live in [`specs/001-pnw-student-chatbot/`](specs/001-pnw-student-chatbot/).

**Stack**: FastAPI + React (Vite) + ChromaDB + Google Gemini (free tier). Runs via Docker Compose.

## Run it

```bash
cp backend/.env.example backend/.env   # set GEMINI_API_KEY
docker compose up --build
```

- Frontend: http://localhost:5173
- Backend: http://localhost:8000
- FastAPI docs: http://localhost:8000/docs

Stop with `docker compose down`. See [`specs/001-pnw-student-chatbot/quickstart.md`](specs/001-pnw-student-chatbot/quickstart.md) for ingestion, validation scenarios, and full setup detail.
