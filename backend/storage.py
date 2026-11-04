"""Where the public game counters are kept.

Two backends behind one async interface:

- Local disk (DATA_DIR), for development or hosts with a persistent volume.
- Any S3-compatible bucket (Cloudflare R2, Backblaze B2, AWS S3, ...), for
  hosts whose filesystem is wiped on restart, such as Render's free tier.
  Used whenever S3_BUCKET is set.
"""

import asyncio
from pathlib import Path

from . import config


class LocalStorage:
    def __init__(self, root: Path):
        self.root = root

    def _path(self, key: str) -> Path:
        return self.root / key

    async def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def exists(self, key: str) -> bool:
        return self._path(key).exists()


class S3Storage:
    def __init__(self):
        import boto3
        from botocore.config import Config

        self.bucket = config.S3_BUCKET
        self.client = boto3.client(
            "s3",
            endpoint_url=config.S3_ENDPOINT_URL or None,
            aws_access_key_id=config.S3_ACCESS_KEY_ID,
            aws_secret_access_key=config.S3_SECRET_ACCESS_KEY,
            region_name=config.S3_REGION,
            config=Config(retries={"max_attempts": 3, "mode": "standard"}, connect_timeout=5, read_timeout=20),
        )
        self._missing = self.client.exceptions.NoSuchKey

    def _get(self, key: str) -> bytes | None:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self._missing:
            return None

    def _exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    async def get(self, key: str) -> bytes | None:
        return await asyncio.to_thread(self._get, key)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self.client.put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    async def exists(self, key: str) -> bool:
        return await asyncio.to_thread(self._exists, key)


def create():
    if config.S3_BUCKET:
        return S3Storage()
    return LocalStorage(config.DATA_DIR)


store = create()
