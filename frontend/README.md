# Kanban Studio

## Run

The app calls a FastAPI backend for auth, board data, and AI chat. Start the backend first (from the repo root, `scripts/start.ps1` or `scripts/start.sh`, which serves on `http://localhost:8000`), then:

```bash
npm install
npm run dev
```

`npm run dev` runs on `http://localhost:3000` and proxies API calls to `http://localhost:8000` automatically in development.

## Tests

```bash
npm run test:unit
npm run test:e2e   # requires the app running at http://localhost:8000 (see scripts/start.ps1 / start.sh)
```
