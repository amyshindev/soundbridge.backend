# 레이어: Application — Cloudflare R2 스토리지 설정 DTO
from dataclasses import dataclass


@dataclass(frozen=True)
class R2StorageConfig:
    access_key_id: str
    secret_access_key: str
    endpoint_url: str
    bucket_name: str
    public_base_url: str
    key_prefix: str = ""

    def object_key(self, filename: str) -> str:
        prefix = self.key_prefix.strip("/")
        if prefix:
            return f"{prefix}/{filename}"
        return filename

    def public_url(self, filename: str) -> str:
        base = self.public_base_url.rstrip("/")
        return f"{base}/{self.object_key(filename)}"
