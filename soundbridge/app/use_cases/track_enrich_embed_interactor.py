# 레이어: Application — TM 트랙 EXAONE 풍부화 + Cohere 임베딩 배치
from __future__ import annotations

import sys
import time

from soundbridge.app.dtos.track_enrich_embed_dto import EnrichEmbedCommand, EnrichEmbedRunResult
from soundbridge.app.policies.track_enrich_policy import (
    DEFAULT_BATCH_INTERVAL_SEC,
    DEFAULT_BATCH_SIZE,
)
from soundbridge.app.ports.output.batch_embedding_port import BatchEmbeddingPort
from soundbridge.app.ports.output.track_description_enrich_port import TrackDescriptionEnrichPort
from soundbridge.app.ports.output.track_enrich_repository_port import TrackEnrichRepositoryPort
from soundbridge.app.services.track_embed_text_builder import (
    build_embedding_document_text,
    build_enrich_prompt,
)
from soundbridge.infrastructure.embedding_config import EMBEDDING_DIMENSION
from soundbridge.infrastructure.settings import settings


class TrackEnrichEmbedInteractor:

    def __init__(
        self,
        repository: TrackEnrichRepositoryPort,
        description_enricher: TrackDescriptionEnrichPort,
        batch_embedding: BatchEmbeddingPort,
    ) -> None:
        self._repository = repository
        self._description_enricher = description_enricher
        self._batch_embedding = batch_embedding

    def print_stats(self) -> None:
        self._repository.print_embedding_stats()

    def run(self, command: EnrichEmbedCommand) -> EnrichEmbedRunResult:
        if command.enrich_only and command.embed_only:
            raise ValueError("--enrich-only 와 --embed-only 는 동시에 사용할 수 없습니다.")

        self._repository.prepare_schema()
        tracks = self._repository.fetch_targets(
            only_missing_embedding=not command.force,
            limit=command.limit,
            tm_only=command.tm_only,
        )
        total = len(tracks)
        result = EnrichEmbedRunResult()

        if total == 0:
            print("처리할 트랙이 없습니다.")
            self._repository.print_embedding_stats()
            return result

        mode = "enrich+embed"
        if command.enrich_only:
            mode = "enrich-only"
        elif command.embed_only:
            mode = "embed-only"

        print(
            f"targets: {total} mode={mode} force={command.force} tm_only={command.tm_only} "
            f"exaone={settings.exaone_model} cohere={settings.embed_model} "
            f"dim={EMBEDDING_DIMENSION} batch={command.batch_size}/"
            f"interval={command.batch_interval_sec}s"
        )

        started = time.time()

        for idx, track in enumerate(tracks, start=1):
            label = f"[{idx}/{total}] {track.title}"

            if command.dry_run:
                prompt = build_enrich_prompt(track)
                print(f"[DRY {idx}/{total}] {track.id} | {track.title}")
                print("  enrich prompt:", prompt[:140].replace("\n", " ") + "...")
                if not command.enrich_only:
                    sample_text = build_embedding_document_text(
                        track,
                        track.description_ko or "(EXAONE 풍부화 예정)",
                    )
                    print("  embed text:", sample_text[:140].replace("\n", " | ") + "...")
                result.success += 1
                continue

            try:
                description_ko = track.description_ko

                if not command.embed_only:
                    prompt = build_enrich_prompt(track)
                    description_ko = self._description_enricher.enrich_description(prompt)
                    self._repository.save_description(track.id, description_ko)
                    print(f"{label} enriched ({len(description_ko)} chars)")

                if not command.enrich_only:
                    embed_input = build_embedding_document_text(track, description_ko)
                    vector = self._batch_embedding.embed_document(embed_input)
                    self._repository.save_embedding(track.id, vector)
                    print(f"{label} embedded")

                self._repository.commit()
                result.success += 1
            except Exception as e:
                self._repository.rollback()
                result.failed += 1
                msg = f"{label} FAILED: {e}"
                result.errors.append(msg)
                print(msg, file=sys.stderr)

            if idx % command.batch_size == 0 and idx < total:
                time.sleep(command.batch_interval_sec)

        result.elapsed_sec = time.time() - started
        print(f"done: success={result.success}, failed={result.failed}, elapsed={result.elapsed_sec:.1f}s")
        if not command.dry_run:
            self._repository.print_embedding_stats()
        return result


def default_enrich_embed_command(**overrides) -> EnrichEmbedCommand:
    return EnrichEmbedCommand(
        batch_size=DEFAULT_BATCH_SIZE,
        batch_interval_sec=DEFAULT_BATCH_INTERVAL_SEC,
        **overrides,
    )
