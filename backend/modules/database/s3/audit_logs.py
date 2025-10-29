"""
S3 audit log management operations
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

from botocore.exceptions import ClientError

from .config import S3Config
from .utils import compress_data, decompress_data

logger = logging.getLogger(__name__)


class AuditLogManager:
    """Manages audit logs in S3"""
    
    def __init__(self, s3_client):
        self.s3_client = s3_client
    
    def _build_audit_log_key(self, tenant_id: str, date: str, log_type: str = "general") -> str:
        """Build S3 key for audit log"""
        return f"{S3Config.AUDIT_LOGS_PREFIX}/{tenant_id}/{date}/{log_type}.{S3Config.AUDIT_LOG_FORMAT}"
    
    async def write_audit_log(
        self,
        tenant_id: str,
        log_entries: List[Dict[str, Any]],
        log_type: str = "general"
    ) -> str:
        """
        Write audit log entries to S3
        
        Args:
            tenant_id: Tenant ID for isolation
            log_entries: List of log entries
            log_type: Type of log (general, security, operations)
            
        Returns:
            str: S3 key of the log file
        """
        date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        # Build log data (JSONL format)
        log_lines = []
        for entry in log_entries:
            # Ensure timestamp is present
            if 'timestamp' not in entry:
                entry['timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # Add tenant context
            entry['tenant_id'] = tenant_id
            entry['log_type'] = log_type
            
            log_lines.append(json.dumps(entry))
        
        log_data = '\n'.join(log_lines) + '\n'
        
        # Compress data
        compressed_data = compress_data(log_data)
        
        # Build S3 key with timestamp to avoid conflicts
        timestamp = datetime.now(timezone.utc).strftime('%H-%M-%S')
        base_key = self._build_audit_log_key(tenant_id, date, log_type)
        s3_key = base_key.replace(f'.{S3Config.AUDIT_LOG_FORMAT}', f'_{timestamp}.{S3Config.AUDIT_LOG_FORMAT}')
        
        # Upload to S3
        await self.s3_client.put_object(
            Bucket=S3Config.BUCKET_NAME,
            Key=s3_key,
            Body=compressed_data,
            ContentType='application/x-ndjson',
            ContentEncoding='gzip',
            Metadata={
                'tenant-id': tenant_id,
                'log-type': log_type,
                'entry-count': str(len(log_entries)),
                'log-date': date
            }
        )
        
        logger.debug(f"Wrote audit log: {s3_key} ({len(log_entries)} entries)")
        return s3_key
    
    async def read_audit_logs(
        self,
        tenant_id: str,
        start_date: str,
        end_date: Optional[str] = None,
        log_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Read audit log entries from S3
        
        Args:
            tenant_id: Tenant ID for isolation
            start_date: Start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)
            log_type: Optional log type filter
            
        Returns:
            List[Dict[str, Any]]: List of log entries
        """
        if not end_date:
            end_date = start_date
        
        log_entries = []
        
        # Generate date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        current_dt = start_dt
        while current_dt <= end_dt:
            date_str = current_dt.strftime('%Y-%m-%d')
            
            # Build prefix for the date
            prefix = f"{S3Config.AUDIT_LOGS_PREFIX}/{tenant_id}/{date_str}/"
            
            # List objects for this date
            try:
                response = await self.s3_client.list_objects_v2(
                    Bucket=S3Config.BUCKET_NAME,
                    Prefix=prefix
                )
                
                if 'Contents' not in response:
                    current_dt += timedelta(days=1)
                    continue
                
                # Process each log file
                for obj in response['Contents']:
                    key = obj['Key']
                    
                    # Apply log type filter
                    if log_type and f"/{log_type}_" not in key and not key.endswith(f"/{log_type}.{S3Config.AUDIT_LOG_FORMAT}"):
                        continue
                    
                    # Read and decompress log file
                    try:
                        log_response = await self.s3_client.get_object(
                            Bucket=S3Config.BUCKET_NAME,
                            Key=key
                        )
                        
                        compressed_data = await log_response['Body'].read()
                        log_data = decompress_data(compressed_data)
                        
                        # Parse JSONL format
                        for line in log_data.strip().split('\n'):
                            if line:
                                try:
                                    entry = json.loads(line)
                                    log_entries.append(entry)
                                except json.JSONDecodeError as e:
                                    logger.warning(f"Failed to parse log line: {e}")
                                    continue
                                    
                    except Exception as e:
                        logger.warning(f"Failed to read log file {key}: {e}")
                        continue
            
            except ClientError as e:
                if e.response['Error']['Code'] != 'NoSuchKey':
                    logger.warning(f"Failed to list logs for {date_str}: {e}")
            
            current_dt += timedelta(days=1)
        
        # Sort by timestamp
        log_entries.sort(key=lambda x: x.get('timestamp', ''))
        
        logger.debug(f"Read {len(log_entries)} audit log entries for tenant {tenant_id}")
        return log_entries