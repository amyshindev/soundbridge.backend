import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")  # postgresql+psycopg://... 그대로 사용
BASE_PATH = Path(r"C:\Users\hi\Desktop\국악음원_sample\test\원천데이터")

engine = create_async_engine(DATABASE_URL)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def load_tracks():
    success, fail = 0, 0

    async with AsyncSessionLocal() as session:
        for json_file in BASE_PATH.rglob("*_M*.json"):
            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)

                contents = data.get("contents", {})

                # 감성 태그 (count 높은 순 상위 3개)
                emotions_raw = contents.get("whole_emotions", [])
                emotions = [
                    e["emotion"] for e in
                    sorted(emotions_raw, key=lambda x: x.get("count", 0), reverse=True)[:3]
                ]

                # 악기/장르
                instrument = contents.get("genre_sclsf", "") or data.get("classification_code", "")

                # 장단
                time_sig = contents.get("timeSignature", "")
                jangdan = "자진모리" if "12" in time_sig else "중모리"

                # BPM
                try:
                    bpm = int(float(contents.get("tempo", 0) or 0))
                except:
                    bpm = 0

                # 라벨링 JSON에서 caption 가져오기
                label_file = (
                    json_file.parents[3] /
                    "라벨링데이터" /
                    json_file.parents[1].name /
                    json_file.parent.name /
                    json_file.name.replace("_M", "_P")
                )

                caption_ko, caption_en = "", ""
                if label_file.exists():
                    try:
                        with open(label_file, encoding="utf-8") as f:
                            label = json.load(f)
                        caption_ko = label.get("annotation", {}).get("caption_ko", "")
                        caption_en = label.get("annotation", {}).get("caption_en", "")
                    except:
                        pass

                audio_filename = contents.get("file_name", "")

                # gugak_tracks 삽입
                result = await session.execute(
                    text("""
                        INSERT INTO gugak_tracks 
                            (title, artist, instrument, jangdan_name, bpm,
                             audio_url, public_license_type, description_ko, description_en,
                             cue_points, created_at)
                        VALUES (:title, :artist, :instrument, :jangdan, :bpm,
                                :audio_url, :license, :desc_ko, :desc_en,
                                :cue_points, NOW())
                        RETURNING id
                    """),
                    {
                        "title": data.get("title", json_file.stem),
                        "artist": contents.get("performer", ""),
                        "instrument": instrument,
                        "jangdan": jangdan,
                        "bpm": bpm,
                        "audio_url": audio_filename,
                        "license": "KOGL_1",
                        "desc_ko": caption_ko,
                        "desc_en": caption_en,
                        "cue_points": "[]",
                    }
                )
                track_id = result.scalar_one()

                # track_emotion_tags 삽입
                for idx, emotion in enumerate(emotions):
                    await session.execute(
                        text("""
                            INSERT INTO track_emotion_tags (track_id, emotion_tag, sort_order)
                            VALUES (:track_id, :emotion, :sort_order)
                        """),
                        {"track_id": str(track_id), "emotion": emotion, "sort_order": idx}
                    )

                await session.commit()
                success += 1
                if success % 50 == 0:
                    print(f"진행: {success}건")

            except Exception as e:
                await session.rollback()
                fail += 1
                print(f"❌ {json_file.name}: {e}")

    await engine.dispose()
    print(f"\n✅ 완료 — 성공: {success}건 / 실패: {fail}건")


if __name__ == "__main__":
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(load_tracks())