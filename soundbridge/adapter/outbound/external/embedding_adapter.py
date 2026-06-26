# 레이어: Outbound — Ollama 임베딩 EmbeddingPort 구현 (768차원, nomic-embed-text)
from __future__ import annotations

from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from soundbridge.app.ports.output.embedding_port import EmbeddingPort
from soundbridge.infrastructure.exceptions import EmbeddingException
from soundbridge.infrastructure.settings import settings


class OllamaEmbeddingAdapter(EmbeddingPort):

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_embed_model

    async def embed_text(self, text: str) -> list[float]:
        url = f"{self._base_url}/api/embeddings"
        try:
            async with httpx.AsyncClient(timeout=settings.discover_embed_timeout_sec) as client:
                response = await client.post(
                    url,
                    json={"model": self._model, "prompt": text},
                )
                response.raise_for_status()
                embedding = response.json().get("embedding")
                if not embedding:
                    raise EmbeddingException("Ollama 응답에 embedding 이 없습니다.")
                if len(embedding) != settings.embedding_dimension:
                    raise EmbeddingException(
                        f"임베딩 차원 불일치: {len(embedding)} (기대 {settings.embedding_dimension})"
                    )
                return embedding
        except EmbeddingException:
            raise
        except httpx.HTTPError as e:
            raise EmbeddingException(
                f"Ollama 임베딩 요청 실패 ({self._base_url}). Ollama가 실행 중인지 확인하세요."
            ) from e
        except Exception as e:
            raise EmbeddingException(f"임베딩 생성 실패: {e}") from e

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
