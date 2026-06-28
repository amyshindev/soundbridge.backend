# 레이어: Infrastructure — Cohere embed-v4.0 공통 클라이언트
from __future__ import annotations

import json
import urllib.error
import urllib.request

import httpx

from soundbridge.infrastructure.exceptions import EmbeddingException
from soundbridge.infrastructure.secret_manager import secretmanager
from soundbridge.infrastructure.settings import settings

COHERE_EMBED_URL = "https://api.cohere.com/v2/embed"


def _parse_embedding_response(payload: dict) -> list[float]:
    embeddings = payload.get("embeddings", {})
    vectors = embeddings.get("float") if isinstance(embeddings, dict) else None
    if not vectors:
        raise EmbeddingException("Cohere 응답에 embeddings.float 이 없습니다.")
    vector = vectors[0]
    if len(vector) != settings.embedding_dimension:
        raise EmbeddingException(
            f"임베딩 차원 불일치: {len(vector)} (기대 {settings.embedding_dimension})"
        )
    return vector


def _build_payload(text: str, *, input_type: str) -> dict:
    return {
        "model": settings.embed_model,
        "texts": [text],
        "input_type": input_type,
        "embedding_types": ["float"],
        "output_dimension": settings.embedding_dimension,
    }


def embed_text_sync(text: str, *, input_type: str = "search_document") -> list[float]:
    api_key = secretmanager.get_cohere_api_key()
    if not api_key:
        raise EmbeddingException("COHERE_API_KEY 가 설정되지 않았습니다.")

    body = json.dumps(_build_payload(text, input_type=input_type)).encode("utf-8")
    request = urllib.request.Request(
        COHERE_EMBED_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        raise EmbeddingException(f"Cohere 임베딩 요청 실패 ({e.code}): {detail}") from e
    except urllib.error.URLError as e:
        raise EmbeddingException(f"Cohere 임베딩 연결 실패: {e}") from e

    return _parse_embedding_response(payload)


async def embed_text_async(text: str, *, input_type: str = "search_query") -> list[float]:
    api_key = secretmanager.get_cohere_api_key()
    if not api_key:
        raise EmbeddingException("COHERE_API_KEY 가 설정되지 않았습니다.")

    try:
        async with httpx.AsyncClient(timeout=settings.discover_embed_timeout_sec) as client:
            response = await client.post(
                COHERE_EMBED_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=_build_payload(text, input_type=input_type),
            )
            response.raise_for_status()
            return _parse_embedding_response(response.json())
    except EmbeddingException:
        raise
    except httpx.HTTPError as e:
        raise EmbeddingException(f"Cohere 임베딩 요청 실패: {e}") from e
    except Exception as e:
        raise EmbeddingException(f"임베딩 생성 실패: {e}") from e
