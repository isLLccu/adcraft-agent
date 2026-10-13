"""Public structured output and restricted tool arguments for the AI workflow."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

PROMPT_VERSION = "1.0"
TOOL_VERSION = "1.0"
Platform = Literal["xiaohongshu", "taobao", "douyin"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Claim(StrictModel):
    text: str = Field(min_length=1, max_length=600)
    fact_ids: list[str] = Field(min_length=1, max_length=12)


class ImagePrompt(StrictModel):
    label: str = Field(min_length=1, max_length=80)
    prompt: str = Field(min_length=1, max_length=1600)
    negative_prompt: str = Field(max_length=600)


class Draft(StrictModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=5000)
    slogan: str = Field(max_length=120)
    selling_points: list[str] = Field(min_length=1, max_length=8)
    claims: list[Claim] = Field(max_length=20)
    evidence_ids: list[str] = Field(max_length=30)
    image_prompts: list[ImagePrompt] = Field(min_length=1, max_length=6)
    platform: Platform


class EmptyToolArgs(StrictModel):
    pass


class SearchKnowledgeArgs(StrictModel):
    query: str = Field(min_length=1, max_length=1000)
    top_k: int | None = Field(default=None, ge=1, le=10)


def draft_json_schema() -> dict:
    return Draft.model_json_schema()
