"""
AWS OpenSearch service adapter with tenant isolation.
This adapter provides search capabilities using AWS OpenSearch Service.
"""

import json
import uuid
from typing import Any, Dict, List, Optional
from opensearchpy import OpenSearch, RequestsHttpConnection
from aws_requests_auth.aws_auth import AWSRequestsAuth
import boto3
from botocore.exceptions import ClientError, BotoCoreError

from backend.core.interfaces import SearchService


class AWSOpenSearchAdapter(SearchService):
    """AWS OpenSearch implementation with tenant isolation."""
    
    def __init__(self, endpoint: str, region_name: str = "us-east-1"):
        """Initialize AWS OpenSearch adapter."""
        self.endpoint = endpoint
        self.region_name = region_name
        
        # Set up AWS authentication
        credentials = boto3.Session().get_credentials()
        self.auth = AWSRequestsAuth(
            aws_access_key=credentials.access_key,
            aws_secret_access_key=credentials.secret_key,
            aws_token=credentials.token,
            aws_host=endpoint.replace('https://', ''),
            aws_region=region_name,
            aws_service='es'
        )
        
        # Initialize OpenSearch client
        self.client = OpenSearch(
            hosts=[{'host': endpoint.replace('https://', ''), 'port': 443}],
            http_auth=self.auth,
            use_ssl=True,
            verify_certs=True,
            connection_class=RequestsHttpConnection
        )
    
    def _get_index_name(self, tenant_id: str, index_name: str = None) -> str:
        """Generate tenant-isolated index name."""
        base_index = index_name or "documents"
        return f"{tenant_id}-{base_index}"
    
    def _ensure_index_exists(self, index_name: str) -> bool:
        """Ensure index exists with proper mapping."""
        try:
            if not self.client.indices.exists(index=index_name):
                # Create index with mapping for hybrid search
                mapping = {
                    "mappings": {
                        "properties": {
                            "content": {
                                "type": "text",
                                "analyzer": "standard"
                            },
                            "title": {
                                "type": "text",
                                "analyzer": "standard"
                            },
                            "vector": {
                                "type": "knn_vector",
                                "dimension": 768,
                                "method": {
                                    "name": "hnsw",
                                    "space_type": "cosinesimil",
                                    "engine": "nmslib"
                                }
                            },
                            "metadata": {
                                "type": "object",
                                "enabled": True
                            },
                            "tenant_id": {
                                "type": "keyword"
                            },
                            "created_at": {
                                "type": "date"
                            }
                        }
                    },
                    "settings": {
                        "index": {
                            "knn": True,
                            "knn.algo_param.ef_search": 100
                        }
                    }
                }
                
                self.client.indices.create(index=index_name, body=mapping)
            return True
            
        except Exception as e:
            print(f"Error ensuring index exists: {e}")
            return False
    
    async def index_document(self, doc: Dict[str, Any], tenant_id: str, index_name: str = None) -> str:
        """Index a document for search."""
        try:
            index = self._get_index_name(tenant_id, index_name)
            
            # Ensure index exists
            if not self._ensure_index_exists(index):
                raise Exception(f"Failed to create index: {index}")
            
            # Generate document ID if not provided
            doc_id = doc.get('id', str(uuid.uuid4()))
            
            # Add tenant isolation and metadata
            document = {
                **doc,
                'tenant_id': tenant_id,
                'created_at': doc.get('created_at', '2024-01-01T00:00:00Z'),
                'id': doc_id
            }
            
            # Index the document
            response = self.client.index(
                index=index,
                id=doc_id,
                body=document,
                refresh=True
            )
            
            return doc_id
            
        except Exception as e:
            print(f"Error indexing document: {e}")
            raise
    
    async def search(self, query: str, tenant_id: str, filters: Dict[str, Any] = None, 
                    index_name: str = None) -> List[Dict[str, Any]]:
        """Perform text search."""
        try:
            index = self._get_index_name(tenant_id, index_name)
            
            # Build search query
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title^2", "content"],
                                    "type": "best_fields"
                                }
                            },
                            {
                                "term": {
                                    "tenant_id": tenant_id
                                }
                            }
                        ]
                    }
                },
                "size": 20,
                "_source": {
                    "excludes": ["vector"]  # Exclude vector field for text search
                }
            }
            
            # Add filters if provided
            if filters:
                for key, value in filters.items():
                    if key != 'tenant_id':  # tenant_id already added
                        search_body["query"]["bool"]["must"].append({
                            "term": {f"metadata.{key}": value}
                        })
            
            response = self.client.search(index=index, body=search_body)
            
            # Extract and return results
            results = []
            for hit in response['hits']['hits']:
                result = hit['_source']
                result['_score'] = hit['_score']
                result['_id'] = hit['_id']
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Error performing search: {e}")
            return []
    
    async def hybrid_search(self, query: str, vector: List[float], tenant_id: str, 
                           filters: Dict[str, Any] = None, index_name: str = None) -> List[Dict[str, Any]]:
        """Perform hybrid text and vector search."""
        try:
            index = self._get_index_name(tenant_id, index_name)
            
            # Build hybrid search query
            search_body = {
                "query": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "tenant_id": tenant_id
                                }
                            }
                        ],
                        "should": [
                            {
                                "multi_match": {
                                    "query": query,
                                    "fields": ["title^2", "content"],
                                    "type": "best_fields"
                                }
                            },
                            {
                                "knn": {
                                    "vector": {
                                        "vector": vector,
                                        "k": 10
                                    }
                                }
                            }
                        ],
                        "minimum_should_match": 1
                    }
                },
                "size": 20
            }
            
            # Add filters if provided
            if filters:
                for key, value in filters.items():
                    if key != 'tenant_id':  # tenant_id already added
                        search_body["query"]["bool"]["must"].append({
                            "term": {f"metadata.{key}": value}
                        })
            
            response = self.client.search(index=index, body=search_body)
            
            # Extract and return results
            results = []
            for hit in response['hits']['hits']:
                result = hit['_source']
                result['_score'] = hit['_score']
                result['_id'] = hit['_id']
                # Remove vector from results to reduce payload size
                if 'vector' in result:
                    del result['vector']
                results.append(result)
            
            return results
            
        except Exception as e:
            print(f"Error performing hybrid search: {e}")
            return []
    
    async def delete_document(self, doc_id: str, tenant_id: str, index_name: str = None) -> bool:
        """Delete a document from search index."""
        try:
            index = self._get_index_name(tenant_id, index_name)
            
            # Verify document belongs to tenant before deletion
            doc_response = self.client.get(index=index, id=doc_id)
            if doc_response['_source'].get('tenant_id') != tenant_id:
                print(f"Document {doc_id} does not belong to tenant {tenant_id}")
                return False
            
            # Delete the document
            self.client.delete(index=index, id=doc_id, refresh=True)
            return True
            
        except Exception as e:
            print(f"Error deleting document: {e}")
            return False