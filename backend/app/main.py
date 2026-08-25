from contextlib import asynccontextmanager
from pathlib import Path
from secrets import token_urlsafe

from fastapi import Cookie, Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from .ai import call_openrouter
from .db import authenticate_user, create_board, create_user, get_user, init_db, list_boards, read_board, write_board
from .schemas import AIResponse, BoardData, BoardSummary, CreateBoard, Credentials, UserResponse


class AIRequest(BaseModel):
    prompt: str
    boardId: int


sessions: dict[str, int] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Project Management MVP Backend", lifespan=lifespan)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


def get_current_user(pm_session: str | None = Cookie(default=None)) -> dict[str, int | str]:
    user_id = sessions.get(pm_session or "")
    user = get_user(user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in required")
    return user


def start_session(response: Response, user_id: int) -> None:
    token = token_urlsafe(32)
    sessions[token] = user_id
    response.set_cookie("pm_session", token, httponly=True, samesite="lax")


@app.get("/api/ping")
def ping() -> dict[str, str]:
    return {"status": "ok", "message": "pong"}


@app.post("/api/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(credentials: Credentials, response: Response) -> UserResponse:
    try:
        user = create_user(credentials.username.strip(), credentials.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    start_session(response, user["id"])
    return UserResponse(**user)


@app.post("/api/auth/login", response_model=UserResponse)
def login(credentials: Credentials, response: Response) -> UserResponse:
    user = authenticate_user(credentials.username.strip(), credentials.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    start_session(response, user["id"])
    return UserResponse(**user)


@app.get("/api/auth/me", response_model=UserResponse)
def current_user(user: dict[str, int | str] = Depends(get_current_user)) -> UserResponse:
    return UserResponse(**user)


@app.post("/api/logout")
def logout(response: Response, pm_session: str | None = Cookie(default=None)) -> dict[str, str]:
    if pm_session:
        sessions.pop(pm_session, None)
    response.delete_cookie("pm_session")
    return {"status": "ok", "message": "signed out"}


@app.get("/api/boards", response_model=list[BoardSummary])
def get_boards(user: dict[str, int | str] = Depends(get_current_user)) -> list[BoardSummary]:
    return [BoardSummary(**board) for board in list_boards(int(user["id"]))]


@app.post("/api/boards", response_model=BoardSummary, status_code=status.HTTP_201_CREATED)
def post_board(payload: CreateBoard, user: dict[str, int | str] = Depends(get_current_user)) -> BoardSummary:
    return BoardSummary(**create_board(int(user["id"]), payload.title))


@app.get("/api/boards/{board_id}", response_model=BoardData)
def get_board(board_id: int, user: dict[str, int | str] = Depends(get_current_user)) -> BoardData:
    board_data = read_board(int(user["id"]), board_id)
    if board_data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    try:
        return BoardData(**board_data)
    except ValidationError as exc:
        raise HTTPException(status_code=500, detail="Saved board state is invalid") from exc


@app.put("/api/boards/{board_id}", response_model=BoardData)
def put_board(board_id: int, board_data: BoardData, user: dict[str, int | str] = Depends(get_current_user)) -> BoardData:
    if not write_board(int(user["id"]), board_id, board_data.model_dump()):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    return board_data


@app.post("/api/ai/chat", response_model=AIResponse)
def ai_chat(request: AIRequest, user: dict[str, int | str] = Depends(get_current_user)) -> AIResponse:
    board = read_board(int(user["id"]), request.boardId)
    if board is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
    response = call_openrouter(request.prompt, board)
    return AIResponse(**response) if isinstance(response, dict) else AIResponse(message=str(response), boardUpdate=None)


@app.get("/", response_class=FileResponse)
def read_index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/{full_path:path}", response_class=FileResponse)
def read_static(full_path: str) -> FileResponse:
    if full_path.startswith("api/"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    candidate = static_dir / full_path
    if candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(static_dir / "index.html")
