"""
Provider-Independent Object Storage Service.
Implements S3-compatible client (Boto3) for SeaweedFS/MinIO with automatic local directory
mirroring/fallback to ensure continuous operation across development profiles.
"""

import os
import io
import shutil
import hashlib
import logging
from pathlib import Path
from typing import BinaryIO, Dict, Any, Optional, Tuple, Generator
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError, EndpointConnectionError

from backend.app.config import settings

logger = logging.getLogger("satquery.services.storage")


class ObjectStore:
    def __init__(self):
        self.endpoint_url = settings.S3_ENDPOINT_INTERNAL
        self.public_endpoint_url = settings.S3_ENDPOINT_PUBLIC
        self.access_key = settings.S3_ACCESS_KEY_ID
        self.secret_key = settings.S3_SECRET_ACCESS_KEY
        self.region = settings.S3_REGION
        self.addressing_style = settings.S3_ADDRESSING_STYLE
        self.local_storage_root = Path(settings.SATQUERY_STORAGE_ROOT)
        self.local_storage_root.mkdir(parents=True, exist_ok=True)
        
        self._s3_client = None
        self._s3_available = None

    def get_client(self):
        """Lazy-initialize Boto3 S3 client."""
        if self._s3_client is None:
            config = Config(
                s3={"addressing_style": self.addressing_style},
                signature_version="s3v4",
                connect_timeout=2,
                read_timeout=5,
                retries={"max_attempts": 2}
            )
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key,
                aws_secret_access_key=self.secret_key,
                region_name=self.region,
                config=config
            )
        return self._s3_client

    def is_s3_available(self) -> bool:
        """Check if S3 endpoint is reachable."""
        try:
            client = self.get_client()
            client.list_buckets()
            self._s3_available = True
            return True
        except (EndpointConnectionError, ClientError, Exception) as e:
            logger.debug(f"S3 endpoint {self.endpoint_url} unavailable ({e}); using local storage mirror.")
            self._s3_available = False
            return False

    def ensure_bucket(self, bucket_name: str) -> None:
        """Ensure bucket exists in S3 and local storage root."""
        local_bucket_dir = self.local_storage_root / bucket_name
        local_bucket_dir.mkdir(parents=True, exist_ok=True)
        
        if self.is_s3_available():
            client = self.get_client()
            try:
                client.head_bucket(Bucket=bucket_name)
            except ClientError:
                try:
                    client.create_bucket(Bucket=bucket_name)
                except Exception as e:
                    logger.warning(f"Could not create bucket {bucket_name} on S3: {e}")

    def put_stream(
        self,
        bucket: str,
        key: str,
        stream: BinaryIO,
        content_type: str = "application/octet-stream",
        chunk_size: int = 1024 * 1024
    ) -> Tuple[int, str]:
        """
        Streams binary data into storage, computing SHA-256 and total bytes.
        Writes simultaneously to local storage root and S3 if available.
        """
        self.ensure_bucket(bucket)
        local_path = self.local_storage_root / bucket / key
        local_path.parent.mkdir(parents=True, exist_ok=True)

        hasher = hashlib.sha256()
        total_bytes = 0

        with open(local_path, "wb") as f_out:
            while True:
                chunk = stream.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
                total_bytes += len(chunk)
                f_out.write(chunk)

        sha256_hex = hasher.hexdigest()

        # If S3 is reachable, upload the mirrored file
        if self.is_s3_available():
            try:
                client = self.get_client()
                with open(local_path, "rb") as f_in:
                    client.put_object(
                        Bucket=bucket,
                        Key=key,
                        Body=f_in,
                        ContentType=content_type
                    )
            except Exception as e:
                logger.warning(f"Failed to replicate {key} to S3 ({e}); retained in local mirror.")

        return total_bytes, sha256_hex

    def put_file(
        self,
        bucket: str,
        key: str,
        local_src_path: str,
        content_type: str = "application/octet-stream"
    ) -> Tuple[int, str]:
        """Copies an existing local file into storage."""
        with open(local_src_path, "rb") as f_in:
            return self.put_stream(bucket, key, f_in, content_type)

    def head(self, bucket: str, key: str) -> Optional[Dict[str, Any]]:
        """Retrieve object metadata."""
        local_path = self.local_storage_root / bucket / key
        if local_path.is_file():
            stat = local_path.stat()
            return {
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "local_path": str(local_path)
            }
        
        if self.is_s3_available():
            try:
                client = self.get_client()
                resp = client.head_object(Bucket=bucket, Key=key)
                return {
                    "size": resp.get("ContentLength"),
                    "modified": resp.get("LastModified"),
                    "content_type": resp.get("ContentType")
                }
            except ClientError:
                return None
        return None

    def get_local_path(self, bucket: str, key: str) -> str:
        """
        Returns an absolute local filesystem path for the object.
        If object only exists in S3, downloads it to local cache.
        """
        local_path = self.local_storage_root / bucket / key
        if not local_path.is_file() and self.is_s3_available():
            local_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                client = self.get_client()
                client.download_file(bucket, key, str(local_path))
            except Exception as e:
                logger.error(f"Failed to fetch {key} from S3: {e}")
        return str(local_path)

    def get_stream(self, bucket: str, key: str, chunk_size: int = 1024 * 1024) -> Generator[bytes, None, None]:
        """Streams object data in chunks."""
        local_path = self.local_storage_root / bucket / key
        if local_path.is_file():
            with open(local_path, "rb") as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
            return

        if self.is_s3_available():
            client = self.get_client()
            resp = client.get_object(Bucket=bucket, Key=key)
            body = resp["Body"]
            while True:
                chunk = body.read(chunk_size)
                if not chunk:
                    break
                yield chunk
            return

        raise FileNotFoundError(f"Object not found in storage: {bucket}/{key}")

    def get_range(self, bucket: str, key: str, start_byte: int, end_byte: int) -> bytes:
        """Retrieves a specific byte range from an object."""
        local_path = self.local_storage_root / bucket / key
        if local_path.is_file():
            with open(local_path, "rb") as f:
                f.seek(start_byte)
                length = end_byte - start_byte + 1
                return f.read(length)

        if self.is_s3_available():
            client = self.get_client()
            range_header = f"bytes={start_byte}-{end_byte}"
            resp = client.get_object(Bucket=bucket, Key=key, Range=range_header)
            return resp["Body"].read()

        raise FileNotFoundError(f"Object not found in storage: {bucket}/{key}")

    def delete_object(self, bucket: str, key: str) -> bool:
        """Deletes an object from local storage and S3."""
        deleted = False
        local_path = self.local_storage_root / bucket / key
        if local_path.is_file():
            local_path.unlink()
            deleted = True

        if self.is_s3_available():
            try:
                client = self.get_client()
                client.delete_object(Bucket=bucket, Key=key)
                deleted = True
            except Exception as e:
                logger.warning(f"Failed to delete {key} from S3: {e}")
        return deleted

    def presign_get(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        """Generates a short-lived download URL."""
        if self.is_s3_available():
            try:
                client = self.get_client()
                return client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": bucket, "Key": key},
                    ExpiresIn=expires_in
                )
            except Exception as e:
                logger.warning(f"Presigning failed ({e}), generating local API route URL.")
        # Local API fallback URL
        return f"/api/v1/assets/download?bucket={bucket}&key={key}"


# Singleton ObjectStore instance
object_store = ObjectStore()

