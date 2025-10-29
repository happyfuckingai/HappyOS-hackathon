"""
S3 configuration constants
"""

from ...config.settings import settings


class S3Config:
    """S3 configuration constants"""
    
    # Bucket configuration
    BUCKET_NAME = settings.AWS_S3_BUCKET_NAME or "ui-resources-storage"
    REGION = settings.AWS_S3_REGION or "us-east-1"
    
    # Key prefixes for different data types
    SNAPSHOTS_PREFIX = "snapshots"
    AUDIT_LOGS_PREFIX = "audit-logs"
    ARCHIVES_PREFIX = "archives"
    
    # File formats
    SNAPSHOT_FORMAT = "json.gz"
    AUDIT_LOG_FORMAT = "jsonl.gz"
    
    # Retention policies (days)
    SNAPSHOT_RETENTION_DAYS = 30
    AUDIT_LOG_RETENTION_DAYS = 90
    ARCHIVE_RETENTION_DAYS = 365
    
    # Batch sizes
    MAX_BATCH_SIZE = 1000
    MAX_FILE_SIZE_MB = 100