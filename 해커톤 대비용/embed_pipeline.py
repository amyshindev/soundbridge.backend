# embed_pipeline.py
# 국악 음원 500건 텍스트 메타데이터 → Gemini 임베딩 → pgvector 저장
#
# 실행 순서:
#   1. psql -c "CREATE EXTENSION IF NOT EXISTS vector;"
#   2. Alembic migrate (테이블 생성)
#   3. python embed_pipeline.py
#
# 환경변수 (.env):
#   GEMINI_API_KEY=...
#   DATABASE_URL=postgresql://user:password@localhost:5432/soundbridge
 
import os
import time
import psycopg2
from psycopg2.extras import execute_values
import google.generativeai as genai
from dotenv import load_dotenv
 
load_dotenv()
 
# ── 설정 ──────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your_gemini_api_key")
DB_URL         = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/soundbridge")
BATCH_SIZE     = 20     # 한 번에 처리할 트랙 수
SLEEP_SEC      = 0.5    # API 레이트 리밋 방지 (gemini-embedding-001 분당 1500 요청)
VECTOR_DIM     = 768    # gemini-embedding-001 기본 출력 차원
 
genai.configure(api_key=GEMINI_API_KEY)
 
 
# ── 1. DB에서 임베딩 안 된 트랙 조회 ─────────────────────────────────────────
def fetch_unembedded_tracks(conn, limit: int = 500) -> list:
    """
    gugak_tracks 중 track_embeddings에 없는 것만 조회.
    파이프라인을 중단했다가 재실행해도 이어받기 가능.
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT
            g.id,
            g.title,
            g.artist,
            g.instrument,
            g.jangdan,
            g.emotion_tags,
            g.bpm,
            g.description_ko
        FROM gugak_tracks g
        LEFT JOIN track_embeddings e ON g.id = e.track_id
        WHERE e.track_id IS NULL
        ORDER BY g.created_at ASC
        LIMIT %s
    """, (limit,))
    rows = cur.fetchall()
    cur.close()
    return rows
 
 
# ── 2. 트랙 → 임베딩용 텍스트 조합 ───────────────────────────────────────────
def build_embed_text(track: dict) -> str:
    """
    임베딩 품질의 핵심.
    숫자(bpm)보다 감성 텍스트를 풍부하게 넣어야
    "아이유 → 정가", "Billie Eilish → 거문고 산조" 매칭이 잘 됨.
    """
    emotion_str = ", ".join(track["emotion_tags"]) if track["emotion_tags"] else "알 수 없음"
    description = track["description_ko"] or ""
 
    return f"""국악 음원: {track['title']}
연주자/단체: {track['artist']}
악기: {track['instrument']}
장단: {track['jangdan']}
감성: {emotion_str}
BPM: {track['bpm']}
설명: {description}""".strip()
 
 
# ── 3. Gemini API로 임베딩 생성 (DOCUMENT용) ─────────────────────────────────
def get_embedding(text: str) -> list[float]:
    """
    음원 DB 저장용 임베딩.
    task_type="RETRIEVAL_DOCUMENT" — 내가 이런 내용을 담고 있다.
    """
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text,
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=VECTOR_DIM
    )
    return result["embedding"]
 
 
# ── 4. 사용자 쿼리 임베딩 (QUERY용, UseCase에서 호출) ─────────────────────────
def get_query_embedding(text: str) -> list[float]:
    """
    사용자 검색 입력용 임베딩.
    task_type="RETRIEVAL_QUERY" — 나는 이런 내용을 찾고 있다.
    DOCUMENT와 task_type을 구분해야 유사도 정확도가 올라감.
    """
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=VECTOR_DIM
    )
    return result["embedding"]
 
 
# ── 5. DB에 임베딩 저장 ───────────────────────────────────────────────────────
def save_embeddings(conn, records: list[tuple]) -> None:
    """
    records = [(track_id, [0.1, 0.2, ...]), ...]
    ON CONFLICT DO NOTHING → 중복 실행해도 안전
    """
    cur = conn.cursor()
    execute_values(
        cur,
        """
        INSERT INTO track_embeddings (track_id, embedding_vector, created_at)
        VALUES %s
        ON CONFLICT (track_id) DO NOTHING
        """,
        [(r[0], r[1], "NOW()") for r in records],
        template="(%s, %s::vector, %s)"
    )
    conn.commit()
    cur.close()
 
 
# ── 6. pgvector 인덱스 생성 ───────────────────────────────────────────────────
def create_index(conn) -> None:
    """
    임베딩 저장 완료 후 1회만 실행.
    IF NOT EXISTS → 중복 실행해도 안전.
    500건 기준 lists=20 적합 (일반 권장: sqrt(행 수)).
    """
    cur = conn.cursor()
    print("\n📌 pgvector 인덱스 생성 중...")
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_track_embeddings_vector
        ON track_embeddings
        USING ivfflat (embedding_vector vector_cosine_ops)
        WITH (lists = 20);
    """)
    conn.commit()
    cur.close()
    print("✅ 인덱스 생성 완료")
 
 
# ── 7. 전체 파이프라인 실행 ───────────────────────────────────────────────────
def run_pipeline(limit: int = 500) -> None:
    conn = psycopg2.connect(DB_URL)
 
    # 임베딩 대상 조회
    print("📦 임베딩 대상 트랙 조회 중...")
    rows = fetch_unembedded_tracks(conn, limit=limit)
    total = len(rows)
 
    if total == 0:
        print("✅ 임베딩할 트랙이 없습니다. 모두 완료된 상태입니다.")
        conn.close()
        return
 
    print(f"✅ 총 {total}건 처리 시작\n")
 
    success = 0
    failed  = 0
 
    for i in range(0, total, BATCH_SIZE):
        batch = rows[i:i + BATCH_SIZE]
        records = []
 
        for row in batch:
            track = {
                "id":             row[0],
                "title":          row[1],
                "artist":         row[2],
                "instrument":     row[3],
                "jangdan":        row[4],
                "emotion_tags":   row[5] or [],
                "bpm":            row[6],
                "description_ko": row[7],
            }
 
            try:
                text   = build_embed_text(track)
                vector = get_embedding(text)
                records.append((track["id"], vector))
                success += 1
 
            except Exception as e:
                title = track.get("title", "unknown")
                print(f"  ❌ [{title}] 실패: {e}")
                failed += 1
 
        # 배치 단위로 저장
        if records:
            save_embeddings(conn, records)
 
        # 진행률 출력
        done = min(i + BATCH_SIZE, total)
        pct  = round(done / total * 100)
        print(f"  [{done:>3}/{total}] {pct:>3}% | ✅ {success}건 | ❌ {failed}건")
 
        # 레이트 리밋 방지
        time.sleep(SLEEP_SEC)
 
    conn.close()
    print(f"\n🎉 임베딩 완료 — 성공 {success}건 / 실패 {failed}건")
 
    # 임베딩 완료 후 인덱스 생성
    conn = psycopg2.connect(DB_URL)
    create_index(conn)
    conn.close()
 
 
# ── 실행 ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    run_pipeline(limit=500)