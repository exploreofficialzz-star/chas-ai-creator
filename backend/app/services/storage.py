"""Cloud storage service for files."""

import uuid
from typing import Optional

import boto3
from botocore.config import Config

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class StorageService:
    """Service for managing cloud storage."""
    
    def __init__(self):
        self.provider = "aws"  # or "firebase", "gcp"
        self.bucket = settings.AWS_S3_BUCKET
        
        # Initialize S3 client
        if settings.AWS_ACCESS_KEY_ID:
            self.s3_client = boto3.client(
                "s3",
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION,
                config=Config(
                    retries={"max_attempts": 3},
                    connect_timeout=10,
                    read_timeout=30,
                ),
            )
        else:
            self.s3_client = None
    
    async def upload_file(
        self,
        file_data: bytes,
        filename: Optional[str] = None,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload file to cloud storage."""
        
        if not filename:
            filename = f"uploads/{uuid.uuid4()}"
        
        try:
            if self.s3_client:
                # Upload to S3
                self.s3_client.put_object(
                    Bucket=self.bucket,
                    Key=filename,
                    Body=file_data,
                    ContentType=content_type,
                )
                
                # Generate URL
                url = f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
                
            else:
                # Fallback: save locally (development only)
                import os
                
                local_path = f"/tmp/{filename}"
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                with open(local_path, "wb") as f:
                    f.write(file_data)
                
                url = f"file://{local_path}"
            
            logger.info("File uploaded", filename=filename, size=len(file_data))
            return url
            
        except Exception as e:
            logger.error("Upload failed", error=str(e), filename=filename)
            raise
    
    async def download_file(self, url: str) -> bytes:
        """Download file from URL."""
        
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=60.0)
            response.raise_for_status()
            return response.content
    
    async def delete_file(self, url: str) -> bool:
        """Delete file from storage."""
        
        try:
            if self.s3_client and "s3" in url:
                # Extract key from URL
                key = url.split(f"{self.bucket}.s3.")[1].split("/", 1)[1]
                
                self.s3_client.delete_object(
                    Bucket=self.bucket,
                    Key=key,
                )
                
                logger.info("File deleted", key=key)
                return True
                
        except Exception as e:
            logger.error("Delete failed", error=str(e), url=url)
        
        return False
    
    async def get_presigned_url(
        self,
        filename: str,
        expiration: int = 3600,
    ) -> str:
        """Generate presigned URL for temporary access."""
        
        if self.s3_client:
            url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": filename},
                ExpiresIn=expiration,
            )
            return url
        
        return ""
    
    def get_cdn_url(self, filename: str) -> str:
        """Get CDN URL for file."""
        
        # In production, use CloudFront or similar CDN
        return f"https://{self.bucket}.s3.{settings.AWS_REGION}.amazonaws.com/{filename}"
