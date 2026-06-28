# 레이어: Outbound — TrackEnrichRepositoryPort (psycopg 동기)
from __future__ import annotations

from uuid import UUID

from soundbridge.adapter.outbound.pg.embed_schema_migrate import (
    ensure_embedding_column_dimension_sync,
    ensure_embedding_hnsw_index_sync,
)
from soundbridge.adapter.outbound.pg.tm_schema_ddl import apply_tm_schema_sync
from soundbridge.app.dtos.track_enrich_embed_dto import TrackEnrichTarget
from soundbridge.app.ports.output.track_enrich_repository_port import TrackEnrichRepositoryPort


class TrackEnrichPgRepository(TrackEnrichRepositoryPort):

    def __init__(self, conn) -> None:
        self._conn = conn

    def prepare_schema(self) -> None:
        apply_tm_schema_sync(self._conn)
        ensure_embedding_column_dimension_sync(self._conn)
        ensure_embedding_hnsw_index_sync(self._conn)
        print("[schema] TM columns + embedding dimension ready")

    def fetch_targets(
        self,
        *,
        only_missing_embedding: bool,
        limit: int | None,
        tm_only: bool,
    ) -> list[TrackEnrichTarget]:
        clauses: list[str] = []
        if only_missing_embedding:
            clauses.append("t.embedding IS NULL")
        if tm_only:
            clauses.append("t.source_identifier IS NOT NULL")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        limit_sql = f"LIMIT {int(limit)}" if limit else ""

        query = f"""
            SELECT
                t.id,
                t.title,
                t.artist,
                t.instrument,
                t.genre_lclsf,
                t.genre_mclsf,
                t.genre_sclsf,
                t.jangdan_name,
                t.jangdan_raw,
                t.time_signature,
                t.tempo_label,
                t.description_ko,
                t.whole_emotions,
                t.whole_tones,
                COALESCE(
                    array_agg(tet.emotion_tag ORDER BY tet.sort_order)
                    FILTER (WHERE tet.emotion_tag IS NOT NULL),
                    ARRAY[]::varchar[]
                ) AS emotion_tags
            FROM gugak_tracks t
            LEFT JOIN track_emotion_tags tet ON tet.track_id = t.id
            {where}
            GROUP BY t.id, t.title, t.artist, t.instrument, t.genre_lclsf, t.genre_mclsf,
                     t.genre_sclsf, t.jangdan_name, t.jangdan_raw, t.time_signature,
                     t.tempo_label, t.description_ko, t.whole_emotions, t.whole_tones,
                     t.cue_points, t.created_at, t.source_identifier
            ORDER BY
                CASE WHEN t.source_identifier IS NOT NULL THEN 0 ELSE 1 END,
                t.created_at DESC,
                t.title
            {limit_sql}
        """

        with self._conn.cursor() as cur:
            cur.execute(query)
            rows = cur.fetchall()

        return [
            TrackEnrichTarget(
                id=row[0],
                title=row[1],
                artist=row[2],
                instrument=row[3] or "",
                genre_lclsf=row[4] or "",
                genre_mclsf=row[5] or "",
                genre_sclsf=row[6] or "",
                jangdan_name=row[7] or "",
                jangdan_raw=row[8] or "",
                time_signature=row[9] or "",
                tempo_label=row[10] or "",
                description_ko=row[11] or "",
                whole_emotions=row[12] or [],
                whole_tones=row[13] or [],
                emotion_tags=list(row[14] or []),
            )
            for row in rows
        ]

    def save_description(self, track_id: UUID, description_ko: str) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE gugak_tracks SET description_ko = %s WHERE id = %s",
                (description_ko, str(track_id)),
            )

    def save_embedding(self, track_id: UUID, embedding: list[float]) -> None:
        vec_literal = "[" + ",".join(str(v) for v in embedding) + "]"
        with self._conn.cursor() as cur:
            cur.execute(
                "UPDATE gugak_tracks SET embedding = %s::vector WHERE id = %s",
                (vec_literal, str(track_id)),
            )

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def print_embedding_stats(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM gugak_tracks")
            total = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM gugak_tracks WHERE embedding IS NOT NULL")
            embedded = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM gugak_tracks WHERE embedding IS NULL")
            missing = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM gugak_tracks
                WHERE cue_points IS NOT NULL AND jsonb_array_length(cue_points) >= 3
                """
            )
            with_cue = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM gugak_tracks
                WHERE cue_points IS NOT NULL AND jsonb_array_length(cue_points) >= 3
                  AND embedding IS NULL
                """
            )
            cue_missing = cur.fetchone()[0]
        print(f"gugak_tracks total: {total}")
        print(f"with cue_points (>=3): {with_cue}")
        print(f"embedded: {embedded}")
        print(f"missing: {missing}")
        print(f"cue tracks still missing embedding: {cue_missing}")
