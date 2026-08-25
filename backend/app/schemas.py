from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator


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

    @model_validator(mode="after")
    def check_invariants(self) -> "BoardData":
        column_ids = [column.id for column in self.columns]
        if len(column_ids) != len(set(column_ids)):
            raise ValueError("Column ids must be unique")

        for card_id, card in self.cards.items():
            if card_id != card.id:
                raise ValueError(f"Card key '{card_id}' does not match card id '{card.id}'")

        placed_card_ids: list[str] = []
        for column in self.columns:
            placed_card_ids.extend(column.cardIds)
        if len(placed_card_ids) != len(set(placed_card_ids)):
            raise ValueError("A card cannot appear in more than one column")

        missing = set(placed_card_ids) - set(self.cards)
        if missing:
            raise ValueError(f"cardIds reference unknown cards: {sorted(missing)}")

        return self


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
