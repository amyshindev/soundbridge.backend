"""Cohere embed-v4.0 연결 확인."""
from __future__ import annotations

from soundbridge.infrastructure.cohere_embed import embed_text_sync
from soundbridge.infrastructure.secret_manager import secretmanager
from soundbridge.infrastructure.settings import settings


def main() -> None:
    secretmanager.bootstrap()
    key = secretmanager.get_cohere_api_key()
    print("model:", settings.embed_model)
    print("dimension:", settings.embedding_dimension)
    print("key_len:", len(key))

    vector = embed_text_sync("국악 서정적인 가창", input_type="search_document")
    print("ok:", len(vector), "dims")


if __name__ == "__main__":
    main()
