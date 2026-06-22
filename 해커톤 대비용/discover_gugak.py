# discover_gugak.py
# DISCOVER 모드 핵심 유스케이스
#
# 흐름:
#   사용자 입력 (텍스트)
#     → Claude: 감성 분석
#     → Gemini: 쿼리 임베딩 (RETRIEVAL_QUERY)
#     → pgvector: 코사인 유사도 Top 3 매칭
#     → Claude: 매칭 설명 생성 (한국어 + 영어)
#     → MatchResult 반환
 
from __future__ import annotations
 
import os
import uuid
from dataclasses import dataclass, field
from typing import Optional
 
import anthropic
import google.generativeai as genai
import psycopg
from dotenv import load_dotenv
 
load_dotenv()
 
# ── 설정 ──────────────────────────────────────────────────────────────────────
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "your_claude_api_key")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "your_gemini_api_key")
DB_URL         = os.getenv("DATABASE_URL", "postgresql://user:password@localhost:5432/soundbridge")
VECTOR_DIM     = 768
 
genai.configure(api_key=GEMINI_API_KEY)
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)
 
 
# ── 도메인 객체 ───────────────────────────────────────────────────────────────
@dataclass
class GugakTrack:
    id:                  str
    title:               str
    artist:              str
    instrument:          str
    jangdan:             str
    emotion_tags:        list[str]
    bpm:                 int
    audio_url:           str
    public_license_type: str
    description_ko:      str
    description_en:      str
    similarity:          float = 0.0     # pgvector 유사도 점수
 
 
@dataclass
class MatchResult:
    tracks:      list[GugakTrack]
    explanation_ko: str
    explanation_en: str
    emotion_summary: str                 # Claude 감성 분석 결과 요약
 
 
# ── 임베딩 함수 (QUERY용) ─────────────────────────────────────────────────────
def get_query_embedding(text: str) -> list[float]:
    """
    사용자 검색 입력용 임베딩.
    task_type="RETRIEVAL_QUERY" — 나는 이런 내용을 찾고 있다.
    embed_pipeline의 RETRIEVAL_DOCUMENT와 반드시 구분.
    """
    result = genai.embed_content(
        model="models/gemini-embedding-001",
        content=text,
        task_type="RETRIEVAL_QUERY",
        output_dimensionality=VECTOR_DIM
    )
    return result["embedding"]
 
 
# ── Claude Port ───────────────────────────────────────────────────────────────
class ClaudePort:
    """Claude API 호출 담당. 감성 분석 + 매칭 설명 생성."""
 
    def analyze_emotion(self, user_input: str) -> str:
        """
        사용자 입력 → 임베딩에 쓸 감성 텍스트 생성.
        "아이유 좋아해요" → "서정적, 호흡이 긴, 단순한 멜로디, 감성적, 조용함"
        """
        message = claude_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=300,
            messages=[{
                "role": "user",
                "content": f"""다음 음악 취향을 감성·분위기·악기 구조로 분석해줘.
임베딩 검색에 쓸 텍스트이므로 간결하게 키워드 중심으로 작성.
한국어로 답변.
 
입력: {user_input}
 
형식:
감성: (예: 서정적, 슬픔, 차분함)
분위기: (예: 조용하고 내밀한, 에너지 넘치는)
악기 특징: (예: 현악기 중심, 타악기 리듬감)
리듬: (예: 느린 호흡, 빠른 박자)"""
            }]
        )
        return message.content[0].text
 
    def explain_match(
        self,
        user_input: str,
        tracks: list[GugakTrack]
    ) -> tuple[str, str]:
        """
        매칭 결과 → 왜 비슷한가 설명 생성.
        한국어 + 영어 동시 반환.
        """
        track_info = "\n".join([
            f"- {t.title} ({t.instrument}, {t.jangdan}, 감성: {', '.join(t.emotion_tags)})"
            for t in tracks
        ])
 
        message = claude_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=600,
            messages=[{
                "role": "user",
                "content": f"""사용자가 좋아하는 음악과 매칭된 국악 음원에 대해
"왜 비슷한가"를 설명해줘.
 
사용자 입력: {user_input}
 
매칭된 국악:
{track_info}
 
다음 형식으로 답변:
[KO]
(한국어 설명 — 2~3문장, 감성적 연결 중심)
 
[EN]
(English explanation — 2~3 sentences, focus on emotional connection)"""
            }]
        )
 
        raw = message.content[0].text
        ko  = raw.split("[EN]")[0].replace("[KO]", "").strip()
        en  = raw.split("[EN]")[1].strip() if "[EN]" in raw else ""
        return ko, en
 
 
# ── Track Repository ──────────────────────────────────────────────────────────
class TrackRepository:
    """pgvector 코사인 유사도 검색 + match_logs 기록."""
 
    def __init__(self, db_url: str):
        self.db_url = db_url
 
    def find_similar(
        self,
        query_vector: list[float],
        top_k: int = 3
    ) -> list[GugakTrack]:
        """
        코사인 유사도로 가장 가까운 트랙 top_k개 반환.
        <=> 연산자: pgvector 코사인 거리 (0=완전일치, 1=완전반대)
        similarity = 1 - 거리
        """
        conn = psycopg.connect(self.db_url)
        cur  = conn.cursor()
 
        cur.execute("""
            SELECT
                g.id,
                g.title,
                g.artist,
                g.instrument,
                g.jangdan,
                g.emotion_tags,
                g.bpm,
                g.audio_url,
                g.public_license_type,
                g.description_ko,
                g.description_en,
                1 - (e.embedding_vector <=> %s::vector) AS similarity
            FROM track_embeddings e
            JOIN gugak_tracks g ON e.track_id = g.id
            ORDER BY e.embedding_vector <=> %s::vector
            LIMIT %s
        """, (query_vector, query_vector, top_k))
 
        rows = cur.fetchall()
        cur.close()
        conn.close()
 
        return [
            GugakTrack(
                id=str(row[0]),
                title=row[1],
                artist=row[2],
                instrument=row[3],
                jangdan=row[4],
                emotion_tags=row[5] or [],
                bpm=row[6],
                audio_url=row[7],
                public_license_type=row[8],
                description_ko=row[9],
                description_en=row[10],
                similarity=round(float(row[11]), 4),
            )
            for row in rows
        ]
 
    def log_match(
        self,
        input_text: str,
        matched_track_id: str,
        similarity_score: float
    ) -> None:
        """match_logs 테이블에 검색 기록 저장 — 심사 증빙 자료."""
        conn = psycopg.connect(self.db_url)
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO match_logs (id, input_text, matched_track_id, similarity_score, created_at)
            VALUES (%s, %s, %s, %s, NOW())
        """, (str(uuid.uuid4()), input_text, matched_track_id, similarity_score))
        conn.commit()
        cur.close()
        conn.close()
 
 
# ── DiscoverGugakUseCase ──────────────────────────────────────────────────────
class DiscoverGugakUseCase:
    """
    DISCOVER 모드 핵심 유스케이스.
    헥사고날 아키텍처: Port에만 의존, DB/API 구현 세부사항 모름.
    """
 
    def __init__(
        self,
        claude_port: ClaudePort,
        track_repo:  TrackRepository,
    ):
        self.claude_port = claude_port
        self.track_repo  = track_repo
 
    def execute(self, user_input: str) -> MatchResult:
        # 1. Claude: 감성 분석
        emotion_summary = self.claude_port.analyze_emotion(user_input)
 
        # 2. Gemini: 감성 텍스트 → 쿼리 임베딩 (RETRIEVAL_QUERY)
        query_vec = get_query_embedding(emotion_summary)
 
        # 3. pgvector: 코사인 유사도 Top 3 매칭
        tracks = self.track_repo.find_similar(query_vec, top_k=3)
 
        # 4. match_logs 기록 (Top 1만 기록)
        if tracks:
            self.track_repo.log_match(
                input_text=user_input,
                matched_track_id=tracks[0].id,
                similarity_score=tracks[0].similarity,
            )
 
        # 5. Claude: 매칭 설명 생성 (한/영 동시)
        explanation_ko, explanation_en = self.claude_port.explain_match(
            user_input, tracks
        )
 
        return MatchResult(
            tracks=tracks,
            explanation_ko=explanation_ko,
            explanation_en=explanation_en,
            emotion_summary=emotion_summary,
        )
 
 
# ── 의존성 주입 팩토리 ─────────────────────────────────────────────────────────
def get_discover_use_case() -> DiscoverGugakUseCase:
    """FastAPI Depends()에서 호출하는 팩토리 함수."""
    return DiscoverGugakUseCase(
        claude_port=ClaudePort(),
        track_repo=TrackRepository(db_url=DB_URL),
    )
 
 
# ── 로컬 테스트 ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    use_case = get_discover_use_case()
 
    test_inputs = [
        "아이유 좋아해요",
        "I love Billie Eilish",
        "재즈 느낌 나는 음악 추천해줘",
    ]
 
    for text in test_inputs:
        print(f"\n{'='*50}")
        print(f"입력: {text}")
        result = use_case.execute(text)
        print(f"\n[감성 분석]\n{result.emotion_summary}")
        print(f"\n[매칭 Top 3]")
        for t in result.tracks:
            print(f"  - {t.title} ({t.instrument}) 유사도: {t.similarity:.2%}")
        print(f"\n[설명 KO]\n{result.explanation_ko}")
        print(f"\n[설명 EN]\n{result.explanation_en}")