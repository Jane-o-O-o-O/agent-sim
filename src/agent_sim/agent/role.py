"""Role definition for agents."""
from __future__ import annotations

from pydantic import BaseModel, Field


class Role(BaseModel):
    """Agent 角色定义。

    Attributes:
        name: 角色名称
        description: 角色描述
        goals: 角色目标列表
    """

    name: str = "default"
    description: str = ""
    goals: list[str] = Field(default_factory=list)

    def __str__(self) -> str:
        return f"Role({self.name})"
