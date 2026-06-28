# 레이어: Outbound — Cohere embed-v4.0 EmbeddingPort 구현
from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from soundbridge.app.ports.output.embedding_port import EmbeddingPort
from soundbridge.infrastructure.cohere_embed import embed_text_async


class CohereEmbeddingAdapter(EmbeddingPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def embed_text(self, text: str) -> list[float]:
        return await embed_text_async(text, input_type="search_query")

    async def find_similar_tracks(
        self,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict | None = None,
    ) -> list[UUID]:
        vector_str = "[" + ",".join(map(str, query_vector)) + "]"
        result = await self._session.execute(
            text("""
                SELECT id
                FROM (
                    SELECT DISTINCT ON (title)
                        id,
                        embedding <=> CAST(:vec AS vector) AS dist
                    FROM gugak_tracks
                    WHERE embedding IS NOT NULL
                      AND source_identifier IS NOT NULL
                    ORDER BY title, embedding <=> CAST(:vec AS vector)
                ) ranked
                ORDER BY dist
                LIMIT :k
            """),
            {"vec": vector_str, "k": top_k},
        )
        return [row[0] for row in result.fetchall()]
