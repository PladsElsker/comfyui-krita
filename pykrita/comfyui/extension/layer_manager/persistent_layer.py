from typing import Any

from pydantic import BaseModel


class PersistentLayer(BaseModel):
    quuid: Any
