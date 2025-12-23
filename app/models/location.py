from pydantic import BaseModel
from typing import Literal

class Location(BaseModel):
    name: str
    camera_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    type: Literal["box", "line"] = "box"
