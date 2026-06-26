from pydantic import BaseModel, Field


class TrackSuggestionSchema(BaseModel):
    id: str
    title: str
    artist: str
    album: str = ""
    artwork_url: str = ""
    display: str


class TrackSuggestResponseSchema(BaseModel):
    suggestions: list[TrackSuggestionSchema] = Field(default_factory=list)
