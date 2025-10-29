"""
HappyOS Unified Service Implementations

Concrete implementations of AWS service facades with local fallbacks.
"""

import asyncio
import json
import sqlite3
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
from pathlib import Path

from .facades import ServiceFacade
from ..config import SDKConfig
from ..exceptions import ServiceUnavailableError


class DatabaseService(ServiceFacade):
    """
    Database service facade supporting DynamoDB with SQLite fallback.
    """
    
    def __init__(self, config: SDKConfig):
        super().__init__("database", config)
        self._dynamodb_client = None
        self._sqlite_path = Path("./local_fallback.db")
    
    async def _execute_aws_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute DynamoDB operation."""
        if not self._dynamodb_client:
            import boto3
            self._dynamodb_client = boto3.client(
                'dynamodb',
                region_name=self.config.services.aws_region
            )
        
        if operation == "put_item":
            return await self._put_item_dynamodb(*args, **kwargs)
        elif operation == "get_item":
            return await self._get_item_dynamodb(*args, **kwargs)
        elif operation == "query":
            return await self._query_dynamodb(*args, **kwargs)
        elif operation == "scan":
            return await self._scan_dynamodb(*args, **kwargs)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _execute_local_fallback(self, operation: str, *args, **kwargs) -> Any:
        """Execute SQLite fallback operation."""
        if operation == "put_item":
            return await self._put_item_sqlite(*args, **kwargs)
        elif operation == "get_item":
            return await self._get_item_sqlite(*args, **kwargs)
        elif operation == "query":
            return await self._query_sqlite(*args, **kwargs)
        elif operation == "scan":
            return await self._scan_sqlite(*args, **kwargs)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _check_aws_health(self) -> Dict[str, Any]:
        """Check DynamoDB health."""
        try:
            if not self._dynamodb_client:
                import boto3
                self._dynamodb_client = boto3.client(
                    'dynamodb',
                    region_name=self.config.services.aws_region
                )
            
            # Simple health check - list tables
            response = self._dynamodb_client.list_tables(Limit=1)
            return {"healthy": True, "tables_accessible": True}
            
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    async def _check_local_health(self) -> Dict[str, Any]:
        """Check SQLite health."""
        try:
            conn = sqlite3.connect(self._sqlite_path)
            conn.execute("SELECT 1")
            conn.close()
            return {"healthy": True, "sqlite_accessible": True}
            
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    # DynamoDB operations
    async def _put_item_dynamodb(self, table_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """Put item to DynamoDB."""
        response = self._dynamodb_client.put_item(
            TableName=table_name,
            Item=self._serialize_dynamodb_item(item)
        )
        return {"success": True, "response": response}
    
    async def _get_item_dynamodb(self, table_name: str, key: Dict[str, Any]) -> Dict[str, Any]:
        """Get item from DynamoDB."""
        response = self._dynamodb_client.get_item(
            TableName=table_name,
            Key=self._serialize_dynamodb_item(key)
        )
        
        item = response.get('Item')
        if item:
            return {"success": True, "item": self._deserialize_dynamodb_item(item)}
        else:
            return {"success": False, "item": None}
    
    async def _query_dynamodb(self, table_name: str, **kwargs) -> Dict[str, Any]:
        """Query DynamoDB."""
        response = self._dynamodb_client.query(TableName=table_name, **kwargs)
        items = [self._deserialize_dynamodb_item(item) for item in response.get('Items', [])]
        return {"success": True, "items": items, "count": response.get('Count', 0)}
    
    async def _scan_dynamodb(self, table_name: str, **kwargs) -> Dict[str, Any]:
        """Scan DynamoDB."""
        response = self._dynamodb_client.scan(TableName=table_name, **kwargs)
        items = [self._deserialize_dynamodb_item(item) for item in response.get('Items', [])]
        return {"success": True, "items": items, "count": response.get('Count', 0)}
    
    # SQLite fallback operations
    async def _put_item_sqlite(self, table_name: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """Put item to SQLite."""
        conn = sqlite3.connect(self._sqlite_path)
        try:
            # Create table if not exists
            conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id TEXT PRIMARY KEY,
                    data TEXT
                )
            """)
            
            # Insert item
            item_id = item.get('id', str(datetime.now().timestamp()))
            conn.execute(
                f"INSERT OR REPLACE INTO {table_name} (id, data) VALUES (?, ?)",
                (item_id, json.dumps(item))
            )
            conn.commit()
            return {"success": True}
            
        finally:
            conn.close()
    
    async def _get_item_sqlite(self, table_name: str, key: Dict[str, Any]) -> Dict[str, Any]:
        """Get item from SQLite."""
        conn = sqlite3.connect(self._sqlite_path)
        try:
            cursor = conn.execute(
                f"SELECT data FROM {table_name} WHERE id = ?",
                (key.get('id'),)
            )
            row = cursor.fetchone()
            
            if row:
                return {"success": True, "item": json.loads(row[0])}
            else:
                return {"success": False, "item": None}
                
        finally:
            conn.close()
    
    async def _query_sqlite(self, table_name: str, **kwargs) -> Dict[str, Any]:
        """Query SQLite (simplified)."""
        conn = sqlite3.connect(self._sqlite_path)
        try:
            cursor = conn.execute(f"SELECT data FROM {table_name}")
            rows = cursor.fetchall()
            items = [json.loads(row[0]) for row in rows]
            return {"success": True, "items": items, "count": len(items)}
            
        finally:
            conn.close()
    
    async def _scan_sqlite(self, table_name: str, **kwargs) -> Dict[str, Any]:
        """Scan SQLite."""
        return await self._query_sqlite(table_name, **kwargs)
    
    def _serialize_dynamodb_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize item for DynamoDB."""
        serialized = {}
        for key, value in item.items():
            if isinstance(value, str):
                serialized[key] = {'S': value}
            elif isinstance(value, (int, float)):
                serialized[key] = {'N': str(value)}
            elif isinstance(value, bool):
                serialized[key] = {'BOOL': value}
            elif isinstance(value, dict):
                serialized[key] = {'M': self._serialize_dynamodb_item(value)}
            elif isinstance(value, list):
                serialized[key] = {'L': [self._serialize_dynamodb_value(v) for v in value]}
            else:
                serialized[key] = {'S': str(value)}
        return serialized
    
    def _serialize_dynamodb_value(self, value: Any) -> Dict[str, Any]:
        """Serialize a single value for DynamoDB."""
        if isinstance(value, str):
            return {'S': value}
        elif isinstance(value, (int, float)):
            return {'N': str(value)}
        elif isinstance(value, bool):
            return {'BOOL': value}
        else:
            return {'S': str(value)}
    
    def _deserialize_dynamodb_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Deserialize item from DynamoDB."""
        deserialized = {}
        for key, value in item.items():
            if 'S' in value:
                deserialized[key] = value['S']
            elif 'N' in value:
                deserialized[key] = float(value['N']) if '.' in value['N'] else int(value['N'])
            elif 'BOOL' in value:
                deserialized[key] = value['BOOL']
            elif 'M' in value:
                deserialized[key] = self._deserialize_dynamodb_item(value['M'])
            elif 'L' in value:
                deserialized[key] = [self._deserialize_dynamodb_value(v) for v in value['L']]
            else:
                deserialized[key] = str(value)
        return deserialized
    
    def _deserialize_dynamodb_value(self, value: Dict[str, Any]) -> Any:
        """Deserialize a single value from DynamoDB."""
        if 'S' in value:
            return value['S']
        elif 'N' in value:
            return float(value['N']) if '.' in value['N'] else int(value['N'])
        elif 'BOOL' in value:
            return value['BOOL']
        else:
            return str(value)


class StorageService(ServiceFacade):
    """
    Storage service facade supporting S3 with local filesystem fallback.
    """
    
    def __init__(self, config: SDKConfig):
        super().__init__("storage", config)
        self._s3_client = None
        self._local_storage_path = Path("./local_storage")
        self._local_storage_path.mkdir(exist_ok=True)
    
    async def _execute_aws_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute S3 operation."""
        if not self._s3_client:
            import boto3
            self._s3_client = boto3.client(
                's3',
                region_name=self.config.services.aws_region
            )
        
        if operation == "put_object":
            return await self._put_object_s3(*args, **kwargs)
        elif operation == "get_object":
            return await self._get_object_s3(*args, **kwargs)
        elif operation == "delete_object":
            return await self._delete_object_s3(*args, **kwargs)
        elif operation == "list_objects":
            return await self._list_objects_s3(*args, **kwargs)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _execute_local_fallback(self, operation: str, *args, **kwargs) -> Any:
        """Execute local filesystem operation."""
        if operation == "put_object":
            return await self._put_object_local(*args, **kwargs)
        elif operation == "get_object":
            return await self._get_object_local(*args, **kwargs)
        elif operation == "delete_object":
            return await self._delete_object_local(*args, **kwargs)
        elif operation == "list_objects":
            return await self._list_objects_local(*args, **kwargs)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _check_aws_health(self) -> Dict[str, Any]:
        """Check S3 health."""
        try:
            if not self._s3_client:
                import boto3
                self._s3_client = boto3.client(
                    's3',
                    region_name=self.config.services.aws_region
                )
            
            # Simple health check - list buckets
            response = self._s3_client.list_buckets()
            return {"healthy": True, "s3_accessible": True}
            
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    async def _check_local_health(self) -> Dict[str, Any]:
        """Check local storage health."""
        try:
            test_file = self._local_storage_path / "health_check.txt"
            test_file.write_text("health_check")
            test_file.unlink()
            return {"healthy": True, "local_storage_accessible": True}
            
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    # S3 operations
    async def _put_object_s3(self, bucket: str, key: str, data: bytes) -> Dict[str, Any]:
        """Put object to S3."""
        response = self._s3_client.put_object(Bucket=bucket, Key=key, Body=data)
        return {"success": True, "etag": response.get('ETag')}
    
    async def _get_object_s3(self, bucket: str, key: str) -> Dict[str, Any]:
        """Get object from S3."""
        try:
            response = self._s3_client.get_object(Bucket=bucket, Key=key)
            return {"success": True, "data": response['Body'].read()}
        except self._s3_client.exceptions.NoSuchKey:
            return {"success": False, "error": "Object not found"}
    
    async def _delete_object_s3(self, bucket: str, key: str) -> Dict[str, Any]:
        """Delete object from S3."""
        self._s3_client.delete_object(Bucket=bucket, Key=key)
        return {"success": True}
    
    async def _list_objects_s3(self, bucket: str, prefix: str = "") -> Dict[str, Any]:
        """List objects in S3."""
        response = self._s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        objects = [obj['Key'] for obj in response.get('Contents', [])]
        return {"success": True, "objects": objects}
    
    # Local filesystem operations
    async def _put_object_local(self, bucket: str, key: str, data: bytes) -> Dict[str, Any]:
        """Put object to local storage."""
        bucket_path = self._local_storage_path / bucket
        bucket_path.mkdir(exist_ok=True)
        
        file_path = bucket_path / key
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(data)
        
        return {"success": True, "path": str(file_path)}
    
    async def _get_object_local(self, bucket: str, key: str) -> Dict[str, Any]:
        """Get object from local storage."""
        file_path = self._local_storage_path / bucket / key
        
        if file_path.exists():
            return {"success": True, "data": file_path.read_bytes()}
        else:
            return {"success": False, "error": "Object not found"}
    
    async def _delete_object_local(self, bucket: str, key: str) -> Dict[str, Any]:
        """Delete object from local storage."""
        file_path = self._local_storage_path / bucket / key
        
        if file_path.exists():
            file_path.unlink()
        
        return {"success": True}
    
    async def _list_objects_local(self, bucket: str, prefix: str = "") -> Dict[str, Any]:
        """List objects in local storage."""
        bucket_path = self._local_storage_path / bucket
        
        if not bucket_path.exists():
            return {"success": True, "objects": []}
        
        objects = []
        for file_path in bucket_path.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(bucket_path)
                if str(relative_path).startswith(prefix):
                    objects.append(str(relative_path))
        
        return {"success": True, "objects": objects}


class ComputeService(ServiceFacade):
    """
    Compute service facade supporting Lambda with local execution fallback.
    """
    
    def __init__(self, config: SDKConfig):
        super().__init__("compute", config)
        self._lambda_client = None
    
    async def _execute_aws_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute Lambda operation."""
        if not self._lambda_client:
            import boto3
            self._lambda_client = boto3.client(
                'lambda',
                region_name=self.config.services.aws_region
            )
        
        if operation == "invoke":
            return await self._invoke_lambda(*args, **kwargs)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _execute_local_fallback(self, operation: str, *args, **kwargs) -> Any:
        """Execute local compute operation."""
        if operation == "invoke":
            return await self._invoke_local(*args, **kwargs)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _check_aws_health(self) -> Dict[str, Any]:
        """Check Lambda health."""
        try:
            if not self._lambda_client:
                import boto3
                self._lambda_client = boto3.client(
                    'lambda',
                    region_name=self.config.services.aws_region
                )
            
            # Simple health check - list functions
            response = self._lambda_client.list_functions(MaxItems=1)
            return {"healthy": True, "lambda_accessible": True}
            
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    async def _check_local_health(self) -> Dict[str, Any]:
        """Check local compute health."""
        return {"healthy": True, "local_compute_available": True}
    
    async def _invoke_lambda(self, function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke Lambda function."""
        response = self._lambda_client.invoke(
            FunctionName=function_name,
            Payload=json.dumps(payload)
        )
        
        result = json.loads(response['Payload'].read())
        return {"success": True, "result": result}
    
    async def _invoke_local(self, function_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Invoke local function (simplified)."""
        # This is a simplified local execution
        # In a real implementation, you might have a local function registry
        return {
            "success": True,
            "result": {
                "message": f"Local execution of {function_name}",
                "payload": payload,
                "timestamp": datetime.now().isoformat()
            }
        }


class SearchService(ServiceFacade):
    """
    Search service facade supporting OpenSearch with local search fallback.
    """
    
    def __init__(self, config: SDKConfig):
        super().__init__("search", config)
        self._opensearch_client = None
        self._local_index = {}
    
    async def _execute_aws_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute OpenSearch operation."""
        # Placeholder for OpenSearch operations
        raise NotImplementedError("OpenSearch operations not implemented yet")
    
    async def _execute_local_fallback(self, operation: str, *args, **kwargs) -> Any:
        """Execute local search operation."""
        if operation == "index":
            return await self._index_local(*args, **kwargs)
        elif operation == "search":
            return await self._search_local(*args, **kwargs)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _check_aws_health(self) -> Dict[str, Any]:
        """Check OpenSearch health."""
        return {"healthy": False, "error": "OpenSearch not implemented"}
    
    async def _check_local_health(self) -> Dict[str, Any]:
        """Check local search health."""
        return {"healthy": True, "local_search_available": True}
    
    async def _index_local(self, index: str, doc_id: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """Index document locally."""
        if index not in self._local_index:
            self._local_index[index] = {}
        
        self._local_index[index][doc_id] = document
        return {"success": True, "indexed": True}
    
    async def _search_local(self, index: str, query: str) -> Dict[str, Any]:
        """Search documents locally."""
        if index not in self._local_index:
            return {"success": True, "results": []}
        
        # Simple text search
        results = []
        for doc_id, document in self._local_index[index].items():
            doc_text = json.dumps(document).lower()
            if query.lower() in doc_text:
                results.append({"id": doc_id, "document": document})
        
        return {"success": True, "results": results}


class MessagingService(ServiceFacade):
    """
    Messaging service facade supporting SQS/SNS with local queue fallback.
    """
    
    def __init__(self, config: SDKConfig):
        super().__init__("messaging", config)
        self._sqs_client = None
        self._sns_client = None
        self._local_queues = {}
    
    async def _execute_aws_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute SQS/SNS operation."""
        if operation.startswith("sqs_"):
            return await self._execute_sqs_operation(operation[4:], *args, **kwargs)
        elif operation.startswith("sns_"):
            return await self._execute_sns_operation(operation[4:], *args, **kwargs)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _execute_local_fallback(self, operation: str, *args, **kwargs) -> Any:
        """Execute local messaging operation."""
        if operation.startswith("sqs_"):
            return await self._execute_local_queue_operation(operation[4:], *args, **kwargs)
        elif operation.startswith("sns_"):
            return await self._execute_local_topic_operation(operation[4:], *args, **kwargs)
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def _check_aws_health(self) -> Dict[str, Any]:
        """Check SQS/SNS health."""
        try:
            if not self._sqs_client:
                import boto3
                self._sqs_client = boto3.client(
                    'sqs',
                    region_name=self.config.services.aws_region
                )
            
            # Simple health check
            response = self._sqs_client.list_queues()
            return {"healthy": True, "messaging_accessible": True}
            
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    async def _check_local_health(self) -> Dict[str, Any]:
        """Check local messaging health."""
        return {"healthy": True, "local_messaging_available": True}
    
    async def _execute_sqs_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute SQS operation."""
        if not self._sqs_client:
            import boto3
            self._sqs_client = boto3.client(
                'sqs',
                region_name=self.config.services.aws_region
            )
        
        if operation == "send_message":
            return await self._send_message_sqs(*args, **kwargs)
        elif operation == "receive_messages":
            return await self._receive_messages_sqs(*args, **kwargs)
        else:
            raise ValueError(f"Unknown SQS operation: {operation}")
    
    async def _execute_sns_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute SNS operation."""
        if not self._sns_client:
            import boto3
            self._sns_client = boto3.client(
                'sns',
                region_name=self.config.services.aws_region
            )
        
        if operation == "publish":
            return await self._publish_sns(*args, **kwargs)
        else:
            raise ValueError(f"Unknown SNS operation: {operation}")
    
    async def _execute_local_queue_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute local queue operation."""
        if operation == "send_message":
            return await self._send_message_local(*args, **kwargs)
        elif operation == "receive_messages":
            return await self._receive_messages_local(*args, **kwargs)
        else:
            raise ValueError(f"Unknown local queue operation: {operation}")
    
    async def _execute_local_topic_operation(self, operation: str, *args, **kwargs) -> Any:
        """Execute local topic operation."""
        if operation == "publish":
            return await self._publish_local(*args, **kwargs)
        else:
            raise ValueError(f"Unknown local topic operation: {operation}")
    
    # SQS operations
    async def _send_message_sqs(self, queue_url: str, message: str) -> Dict[str, Any]:
        """Send message to SQS."""
        response = self._sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message
        )
        return {"success": True, "message_id": response.get('MessageId')}
    
    async def _receive_messages_sqs(self, queue_url: str, max_messages: int = 1) -> Dict[str, Any]:
        """Receive messages from SQS."""
        response = self._sqs_client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages
        )
        messages = response.get('Messages', [])
        return {"success": True, "messages": messages}
    
    # SNS operations
    async def _publish_sns(self, topic_arn: str, message: str) -> Dict[str, Any]:
        """Publish message to SNS."""
        response = self._sns_client.publish(
            TopicArn=topic_arn,
            Message=message
        )
        return {"success": True, "message_id": response.get('MessageId')}
    
    # Local operations
    async def _send_message_local(self, queue_name: str, message: str) -> Dict[str, Any]:
        """Send message to local queue."""
        if queue_name not in self._local_queues:
            self._local_queues[queue_name] = []
        
        message_id = f"local_{len(self._local_queues[queue_name])}"
        self._local_queues[queue_name].append({
            "id": message_id,
            "body": message,
            "timestamp": datetime.now().isoformat()
        })
        
        return {"success": True, "message_id": message_id}
    
    async def _receive_messages_local(self, queue_name: str, max_messages: int = 1) -> Dict[str, Any]:
        """Receive messages from local queue."""
        if queue_name not in self._local_queues:
            return {"success": True, "messages": []}
        
        messages = self._local_queues[queue_name][:max_messages]
        self._local_queues[queue_name] = self._local_queues[queue_name][max_messages:]
        
        return {"success": True, "messages": messages}
    
    async def _publish_local(self, topic_name: str, message: str) -> Dict[str, Any]:
        """Publish message locally (simplified)."""
        message_id = f"local_topic_{datetime.now().timestamp()}"
        return {"success": True, "message_id": message_id}