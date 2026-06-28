# 레이어: Outbound — Cohere search_document 배치 임베딩
from soundbridge.app.ports.output.batch_embedding_port import BatchEmbeddingPort
from soundbridge.infrastructure.cohere_embed import embed_text_sync


class CohereBatchEmbeddingAdapter(BatchEmbeddingPort):

    def embed_document(self, text: str) -> list[float]:
        return embed_text_sync(text, input_type="search_document")
