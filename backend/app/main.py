from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from .ai import call_openrouter
from .db import init_db, read_board, write_board
from .schemas import AIResponse, BoardData


class AIRequest(BaseModel):
    prompt: str
    board: BoardData | None = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="Project Management MVP Backend", lifespan=lifespan)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/api/ping")
def ping() -> dict[str, str]:
    return {"status": "ok", "message": "pong"}


@app.post("/api/logout")
def logout() -> dict[str, str]:
    return {"status": "ok", "message": "signed out"}


@app.post("/api/ai/chat", response_model=AIResponse)
def ai_chat(request: AIRequest) -> AIResponse:
    response = call_openrouter(request.prompt, request.board.dict() if request.board else None)
    if isinstance(response, dict):
        return AIResponse(**response)
    return AIResponse(message=str(response), boardUpdate=None)


@app.get("/api/board", response_model=BoardData)
def get_board() -> BoardData:
    board_data = read_board()
    try:
        return BoardData(**board_data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=500,
            detail="Saved board state is invalid. Restore or recreate the board.",
        ) from exc


@app.put("/api/board", response_model=BoardData)
def put_board(board_data: BoardData) -> BoardData:
    return write_board(board_data.model_dump())


@app.get("/", response_class=FileResponse)
def read_index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/{full_path:path}", response_class=FileResponse)
def read_static(full_path: str) -> FileResponse:
    candidate = static_dir / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(static_dir / "index.html")
