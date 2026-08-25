from typing import Any, Dict, List

from pydantic import BaseModel, Field


class Card(BaseModel):
    id: str
    title: str
    details: str


class Column(BaseModel):
    id: str
    title: str
    cardIds: List[str]


class BoardData(BaseModel):
    columns: List[Column]
    cards: Dict[str, Card]


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=100)


class UserResponse(BaseModel):
    id: int
    username: str


class BoardSummary(BaseModel):
    id: int
    title: str


class CreateBoard(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class AIResponse(BaseModel):
    message: str
    boardUpdate: BoardData | dict[str, Any] | None = None
