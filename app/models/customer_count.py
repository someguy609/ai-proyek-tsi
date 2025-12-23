from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class CustomerCount(BaseModel):
    timestamp: datetime
    camera_id: int
    location_id: str
    gender: str
    count: int
