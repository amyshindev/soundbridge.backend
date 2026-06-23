# 레이어: Outbound — Gemini 임베딩 EmbeddingPort 구현
from __future__ import annotations

import asyncio
import uuid

import google.generativeai as genai
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from soundbridge.app.constants.embedding_constants import EMBEDDING_DIMENSION
from soundbridge.app.ports.output.embedding_port import EmbeddingPort
from soundbridge.infrastructure.exceptions import EmbeddingException
from soundbridge.infrastructure.settings import settings

genai.configure(api_key=settings.gemini_api_key)


class GeminiEmbeddingAdapter(EmbeddingPort):
    """v5.0 Task 5-5 — 임베딩 생성 + pgvector 유사도 검색."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def embed_text(self, text_content: str) -> list[float]:
        model = settings.gemini_embed_model or settings.gemini_embedding_model
        try:
            result = await asyncio.to_thread(
                genai.embed_content,
                model=model,
                content=text_content,
                task_type="retrieval_query",
                output_dimensionality=EMBEDDING_DIMENSION,
            )
            embedding = result.get("embedding")
            if not embedding:
                raise EmbeddingException("Empty embedding response")
            if len(embedding) != EMBEDDING_DIMENSION:
                raise EmbeddingException(
                    f"Unexpected embedding dim: {len(embedding)} (expected {EMBEDDING_DIMENSION})"
                )
            return list(embedding)
        except EmbeddingException:
            raise
        except Exception as e:
            raise EmbeddingException(f"Embedding failed: {e}") from e

    async def find_similar_tracks(
        self,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict | None = None,
    ) -> list[uuid.UUID]:
        vec_literal = "[" + ",".join(str(v) for v in query_vector) + "]"
        result = await self._session.execute(
            text("""
                SELECT id FROM gugak_tracks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> CAST(:vec AS vector)
                LIMIT :k
            """),
            {"vec": vec_literal, "k": top_k},
        )
        return [row[0] for row in result.fetchall()]
