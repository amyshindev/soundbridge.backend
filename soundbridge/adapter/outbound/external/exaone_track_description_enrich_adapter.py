# 레이어: Outbound — EXAONE TM description_ko 풍부화 (배치)
from __future__ import annotations

from openai import OpenAI

from soundbridge.app.policies.track_enrich_policy import MIN_ENRICHED_LEN
from soundbridge.app.ports.output.track_description_enrich_port import TrackDescriptionEnrichPort
from soundbridge.infrastructure.exceptions import ExaoneApiException
from soundbridge.infrastructure.exaone_text_util import clean_enriched_description
from soundbridge.infrastructure.secret_manager import secretmanager
from soundbridge.infrastructure.settings import settings


class ExaoneTrackDescriptionEnrichAdapter(TrackDescriptionEnrichPort):

    def enrich_description(self, prompt: str) -> str:
        client = OpenAI(
            api_key=secretmanager.get_exaone_api_key(),
            base_url=settings.exaone_base_url.rstrip("/"),
            timeout=settings.discover_llm_timeout_sec,
        )
        try:
            response = client.chat.completions.create(
                model=settings.exaone_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=512,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
            )
        except Exception as e:
            raise ExaoneApiException(
                f"EXAONE 풍부화 실패: {e}. Friendli API 키·크레딧·모델({settings.exaone_model})을 확인하세요."
            ) from e

        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise ExaoneApiException("EXAONE 응답이 비어 있습니다.")
        enriched = clean_enriched_description(content)
        if len(enriched) < MIN_ENRICHED_LEN:
            raise ExaoneApiException(
                f"EXAONE 풍부화 결과가 너무 짧습니다 ({len(enriched)}자)."
            )
        return enriched
