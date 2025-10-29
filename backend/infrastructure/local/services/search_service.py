"""
Local search service implementation as fallback for AWS OpenSearch.
Provides BM25 text search and FAISS vector search with tenant isolation.
"""

import asyncio
import json
import math
import logging
import numpy as np
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from collections import defaultdict, Counter
import threading
import re

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("FAISS not available. Vector search will be disabled.")

from ....core.interfaces import SearchService
from ....core.settings import get_settings


logger = logging.getLogger(__name__)


@dataclass
class SearchDocument:
    """Document stored in the search index."""
    doc_id: str
    tenant_id: str
    index_name: str
    content: Dict[str, Any]
    text_fields: List[str]  # Fields to index for text search
    vector_field: Optional[str] = None  # Field containing vector data
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class BM25Scorer:
    """BM25 scoring algorithm implementation."""
    
    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b
        
        # Document statistics
        self.doc_frequencies: Dict[str, int] = defaultdict(int)  # Term -> doc count
        self.doc_lengths: Dict[str, int] = {}  # Doc ID -> length
        self.total_docs = 0
        self.avg_doc_length = 0.0
        
        # Inverted index: term -> {doc_id: term_frequency}
        self.inverted_index: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    
    def add_document(self, doc_id: str, text: str):
        """Add a document to the BM25 index."""
        terms = self._tokenize(text)
        term_counts = Counter(terms)
        
        # Update document length
        self.doc_lengths[doc_id] = len(terms)
        
        # Update inverted index and document frequencies
        for term, count in term_counts.items():
            if doc_id not in self.inverted_index[term]:
                self.doc_frequencies[term] += 1
            self.inverted_index[term][doc_id] = count
        
        self.total_docs += 1
        self._update_avg_doc_length()
    
    def remove_document(self, doc_id: str):
        """Remove a document from the BM25 index."""
        if doc_id not in self.doc_lengths:
            return
        
        # Remove from inverted index and update document frequencies
        for term in list(self.inverted_index.keys()):
            if doc_id in self.inverted_index[term]:
                del self.inverted_index[term][doc_id]
                self.doc_frequencies[term] -= 1
                
                # Clean up empty term entries
                if self.doc_frequencies[term] == 0:
                    del self.doc_frequencies[term]
                    del self.inverted_index[term]
        
        del self.doc_lengths[doc_id]
        self.total_docs -= 1
        self._update_avg_doc_length()
    
    def search(self, query: str, limit: int = 10) -> List[Tuple[str, float]]:
        """Search for documents using BM25 scoring."""
        if self.total_docs == 0:
            return []
        
        query_terms = self._tokenize(query)
        if not query_terms:
            return []
        
        # Calculate BM25 scores for all documents
        doc_scores: Dict[str, float] = defaultdict(float)
        
        for term in query_terms:
            if term not in self.inverted_index:
                continue
            
            # Calculate IDF
            df = self.doc_frequencies[term]
            idf = math.log((self.total_docs - df + 0.5) / (df + 0.5))
            
            # Calculate BM25 score for each document containing this term
            for doc_id, tf in self.inverted_index[term].items():
                doc_length = self.doc_lengths[doc_id]
                
                # BM25 formula
                score = idf * (tf * (self.k1 + 1)) / (
                    tf + self.k1 * (1 - self.b + self.b * (doc_length / self.avg_doc_length))
                )
                doc_scores[doc_id] += score
        
        # Sort by score and return top results
        sorted_results = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:limit]
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms."""
        # Simple tokenization - convert to lowercase and split on non-alphanumeric
        text = text.lower()
        terms = re.findall(r'\b\w+\b', text)
        return terms
    
    def _update_avg_doc_length(self):
        """Update average document length."""
        if self.total_docs > 0:
            self.avg_doc_length = sum(self.doc_lengths.values()) / self.total_docs
        else:
            self.avg_doc_length = 0.0


class VectorIndex:
    """FAISS-based vector index for similarity search."""
    
    def __init__(self, dimension: int = 1536):
        self.dimension = dimension
        self.index = None
        self.doc_ids: List[str] = []
        
        if FAISS_AVAILABLE:
            # Use HNSW index for better performance
            self.index = faiss.IndexHNSWFlat(dimension, 32)
            self.index.hnsw.efConstruction = 40
            self.index.hnsw.efSearch = 16
        else:
            logger.warning("FAISS not available. Vector search disabled.")
    
    def add_vectors(self, doc_ids: List[str], vectors: np.ndarray):
        """Add vectors to the index."""
        if not FAISS_AVAILABLE or self.index is None:
            return
        
        if vectors.shape[1] != self.dimension:
            raise ValueError(f"Vector dimension {vectors.shape[1]} doesn't match index dimension {self.dimension}")
        
        # Normalize vectors for cosine similarity
        faiss.normalize_L2(vectors)
        
        self.index.add(vectors)
        self.doc_ids.extend(doc_ids)
    
    def remove_vectors(self, doc_ids_to_remove: Set[str]):
        """Remove vectors from the index (requires rebuilding)."""
        if not FAISS_AVAILABLE or self.index is None:
            return
        
        # Find indices to keep
        keep_indices = []
        new_doc_ids = []
        
        for i, doc_id in enumerate(self.doc_ids):
            if doc_id not in doc_ids_to_remove:
                keep_indices.append(i)
                new_doc_ids.append(doc_id)
        
        if not keep_indices:
            # No vectors to keep, reset index
            self.index.reset()
            self.doc_ids = []
            return
        
        # Rebuild index with remaining vectors
        if len(keep_indices) < len(self.doc_ids):
            # Get vectors for documents to keep
            vectors = np.zeros((len(keep_indices), self.dimension), dtype=np.float32)
            for new_idx, old_idx in enumerate(keep_indices):
                self.index.reconstruct(old_idx, vectors[new_idx])
            
            # Reset and rebuild index
            self.index.reset()
            self.index.add(vectors)
            self.doc_ids = new_doc_ids
    
    def search(self, query_vector: np.ndarray, k: int = 10) -> List[Tuple[str, float]]:
        """Search for similar vectors."""
        if not FAISS_AVAILABLE or self.index is None or self.index.ntotal == 0:
            return []
        
        if query_vector.shape[0] != self.dimension:
            raise ValueError(f"Query vector dimension {query_vector.shape[0]} doesn't match index dimension {self.dimension}")
        
        # Normalize query vector
        query_vector = query_vector.reshape(1, -1).astype(np.float32)
        faiss.normalize_L2(query_vector)
        
        # Search
        scores, indices = self.index.search(query_vector, min(k, self.index.ntotal))
        
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx >= 0 and idx < len(self.doc_ids):
                results.append((self.doc_ids[idx], float(score)))
        
        return results


class LocalSearchService(SearchService):
    """
    Local search service providing BM25 text search and FAISS vector search.
    Supports tenant isolation and multiple indices.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Storage
        self.data_directory = Path(self.settings.local.data_directory)
        self.data_directory.mkdir(parents=True, exist_ok=True)
        
        # Document storage: {tenant_id: {index_name: {doc_id: SearchDocument}}}
        self.documents: Dict[str, Dict[str, Dict[str, SearchDocument]]] = defaultdict(lambda: defaultdict(dict))
        
        # BM25 indices: {tenant_id: {index_name: BM25Scorer}}
        self.bm25_indices: Dict[str, Dict[str, BM25Scorer]] = defaultdict(lambda: defaultdict(BM25Scorer))
        
        # Vector indices: {tenant_id: {index_name: VectorIndex}}
        self.vector_indices: Dict[str, Dict[str, VectorIndex]] = defaultdict(
            lambda: defaultdict(lambda: VectorIndex(self.settings.local.vector_dimensions))
        )
        
        # Thread safety
        self._lock = threading.RLock()
        
        # Load persisted data
        self._load_persisted_data()
        
        # Background persistence task
        self._persistence_task: Optional[asyncio.Task] = None
        asyncio.create_task(self._start_background_tasks())
        
        logger.info("Local search service initialized")
    
    async def _start_background_tasks(self):
        """Start background persistence task."""
        self._persistence_task = asyncio.create_task(self._periodic_persistence())
    
    def _get_default_index_name(self, tenant_id: str) -> str:
        """Get default index name for a tenant."""
        return f"{tenant_id}-default"
    
    def _validate_tenant_access(self, tenant_id: str, index_name: str) -> str:
        """Validate tenant access and return normalized index name."""
        if not tenant_id:
            raise ValueError("Tenant ID is required")
        
        if not index_name:
            index_name = self._get_default_index_name(tenant_id)
        
        # Ensure index name starts with tenant ID for isolation
        if not index_name.startswith(f"{tenant_id}-"):
            index_name = f"{tenant_id}-{index_name}"
        
        return index_name
    
    async def index_document(self, doc: Dict[str, Any], tenant_id: str, index_name: str = None) -> str:
        """Index a document for search."""
        try:
            index_name = self._validate_tenant_access(tenant_id, index_name)
            
            # Generate document ID if not provided
            doc_id = doc.get('id') or doc.get('_id') or f"doc_{int(datetime.now().timestamp() * 1000)}"
            
            # Determine text fields to index
            text_fields = []
            vector_field = None
            
            for key, value in doc.items():
                if isinstance(value, str) and len(value.strip()) > 0:
                    text_fields.append(key)
                elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], (int, float)):
                    # Assume this is a vector field
                    if vector_field is None:
                        vector_field = key
            
            with self._lock:
                # Create search document
                search_doc = SearchDocument(
                    doc_id=doc_id,
                    tenant_id=tenant_id,
                    index_name=index_name,
                    content=doc,
                    text_fields=text_fields,
                    vector_field=vector_field,
                    updated_at=datetime.now()
                )
                
                # Remove existing document if it exists
                if doc_id in self.documents[tenant_id][index_name]:
                    await self._remove_document_from_indices(tenant_id, index_name, doc_id)
                
                # Store document
                self.documents[tenant_id][index_name][doc_id] = search_doc
                
                # Index text content
                if text_fields:
                    text_content = " ".join([str(doc.get(field, "")) for field in text_fields])
                    self.bm25_indices[tenant_id][index_name].add_document(doc_id, text_content)
                
                # Index vector content
                if vector_field and vector_field in doc:
                    vector_data = np.array([doc[vector_field]], dtype=np.float32)
                    self.vector_indices[tenant_id][index_name].add_vectors([doc_id], vector_data)
                
                logger.debug(f"Indexed document {doc_id} in {index_name}")
                return doc_id
                
        except Exception as e:
            logger.error(f"Error indexing document in {index_name} for tenant {tenant_id}: {e}")
            raise
    
    async def search(self, query: str, tenant_id: str, filters: Dict[str, Any] = None, 
                    index_name: str = None) -> List[Dict[str, Any]]:
        """Perform text search using BM25."""
        try:
            index_name = self._validate_tenant_access(tenant_id, index_name)
            
            with self._lock:
                if tenant_id not in self.bm25_indices or index_name not in self.bm25_indices[tenant_id]:
                    return []
                
                # Perform BM25 search
                bm25_results = self.bm25_indices[tenant_id][index_name].search(query, limit=50)
                
                # Get documents and apply filters
                results = []
                for doc_id, score in bm25_results:
                    if doc_id in self.documents[tenant_id][index_name]:
                        doc = self.documents[tenant_id][index_name][doc_id]
                        
                        # Apply filters
                        if self._apply_filters(doc.content, filters):
                            result = doc.content.copy()
                            result['_score'] = score
                            result['_id'] = doc_id
                            results.append(result)
                
                logger.debug(f"Text search returned {len(results)} results for query: {query}")
                return results
                
        except Exception as e:
            logger.error(f"Error performing text search in {index_name} for tenant {tenant_id}: {e}")
            return []
    
    async def hybrid_search(self, query: str, vector: List[float], tenant_id: str, 
                           filters: Dict[str, Any] = None, index_name: str = None) -> List[Dict[str, Any]]:
        """Perform hybrid text and vector search."""
        try:
            index_name = self._validate_tenant_access(tenant_id, index_name)
            
            # Perform text search
            text_results = await self.search(query, tenant_id, filters, index_name)
            text_scores = {result['_id']: result['_score'] for result in text_results}
            
            # Perform vector search
            vector_results = []
            if FAISS_AVAILABLE:
                with self._lock:
                    if (tenant_id in self.vector_indices and 
                        index_name in self.vector_indices[tenant_id]):
                        
                        query_vector = np.array(vector, dtype=np.float32)
                        vector_search_results = self.vector_indices[tenant_id][index_name].search(
                            query_vector, k=50
                        )
                        
                        for doc_id, similarity in vector_search_results:
                            if doc_id in self.documents[tenant_id][index_name]:
                                doc = self.documents[tenant_id][index_name][doc_id]
                                
                                # Apply filters
                                if self._apply_filters(doc.content, filters):
                                    result = doc.content.copy()
                                    result['_vector_score'] = similarity
                                    result['_id'] = doc_id
                                    vector_results.append(result)
            
            # Combine results with hybrid scoring
            combined_results = self._combine_hybrid_results(text_results, vector_results, text_scores)
            
            logger.debug(f"Hybrid search returned {len(combined_results)} results")
            return combined_results
            
        except Exception as e:
            logger.error(f"Error performing hybrid search in {index_name} for tenant {tenant_id}: {e}")
            return []
    
    def _combine_hybrid_results(self, text_results: List[Dict], vector_results: List[Dict], 
                               text_scores: Dict[str, float]) -> List[Dict[str, Any]]:
        """Combine text and vector search results with hybrid scoring."""
        # Normalize scores
        max_text_score = max(text_scores.values()) if text_scores else 1.0
        max_vector_score = max([r.get('_vector_score', 0) for r in vector_results]) if vector_results else 1.0
        
        # Combine results
        combined = {}
        
        # Add text results
        for result in text_results:
            doc_id = result['_id']
            normalized_text_score = result['_score'] / max_text_score if max_text_score > 0 else 0
            
            combined[doc_id] = result.copy()
            combined[doc_id]['_text_score'] = normalized_text_score
            combined[doc_id]['_vector_score'] = 0.0
            combined[doc_id]['_hybrid_score'] = normalized_text_score * 0.7  # 70% weight for text
        
        # Add/update with vector results
        for result in vector_results:
            doc_id = result['_id']
            normalized_vector_score = result['_vector_score'] / max_vector_score if max_vector_score > 0 else 0
            
            if doc_id in combined:
                # Update existing result
                combined[doc_id]['_vector_score'] = normalized_vector_score
                combined[doc_id]['_hybrid_score'] = (
                    combined[doc_id]['_text_score'] * 0.7 + normalized_vector_score * 0.3
                )
            else:
                # Add new result
                combined[doc_id] = result.copy()
                combined[doc_id]['_text_score'] = 0.0
                combined[doc_id]['_vector_score'] = normalized_vector_score
                combined[doc_id]['_hybrid_score'] = normalized_vector_score * 0.3  # 30% weight for vector
        
        # Sort by hybrid score and return
        sorted_results = sorted(combined.values(), key=lambda x: x['_hybrid_score'], reverse=True)
        return sorted_results
    
    def _apply_filters(self, doc_content: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Apply filters to a document."""
        if not filters:
            return True
        
        for field, expected_value in filters.items():
            doc_value = doc_content.get(field)
            
            if isinstance(expected_value, list):
                if doc_value not in expected_value:
                    return False
            elif isinstance(expected_value, dict):
                # Range filters
                if 'gte' in expected_value and doc_value < expected_value['gte']:
                    return False
                if 'lte' in expected_value and doc_value > expected_value['lte']:
                    return False
                if 'gt' in expected_value and doc_value <= expected_value['gt']:
                    return False
                if 'lt' in expected_value and doc_value >= expected_value['lt']:
                    return False
            else:
                if doc_value != expected_value:
                    return False
        
        return True
    
    async def delete_document(self, doc_id: str, tenant_id: str, index_name: str = None) -> bool:
        """Delete a document from search index."""
        try:
            index_name = self._validate_tenant_access(tenant_id, index_name)
            
            with self._lock:
                if (tenant_id in self.documents and 
                    index_name in self.documents[tenant_id] and 
                    doc_id in self.documents[tenant_id][index_name]):
                    
                    # Remove from indices
                    await self._remove_document_from_indices(tenant_id, index_name, doc_id)
                    
                    # Remove document
                    del self.documents[tenant_id][index_name][doc_id]
                    
                    logger.debug(f"Deleted document {doc_id} from {index_name}")
                    return True
                
                return False
                
        except Exception as e:
            logger.error(f"Error deleting document {doc_id} from {index_name} for tenant {tenant_id}: {e}")
            return False
    
    async def _remove_document_from_indices(self, tenant_id: str, index_name: str, doc_id: str):
        """Remove document from BM25 and vector indices."""
        # Remove from BM25 index
        if tenant_id in self.bm25_indices and index_name in self.bm25_indices[tenant_id]:
            self.bm25_indices[tenant_id][index_name].remove_document(doc_id)
        
        # Remove from vector index
        if tenant_id in self.vector_indices and index_name in self.vector_indices[tenant_id]:
            self.vector_indices[tenant_id][index_name].remove_vectors({doc_id})
    
    def _load_persisted_data(self):
        """Load persisted search data from disk."""
        try:
            index_file = self.data_directory / "search_indices.json"
            if index_file.exists():
                with open(index_file, 'r') as f:
                    data = json.load(f)
                
                # Rebuild indices from persisted documents
                for tenant_id, tenant_data in data.items():
                    for index_name, docs in tenant_data.items():
                        for doc_id, doc_data in docs.items():
                            # Convert datetime strings back to datetime objects
                            doc_data['created_at'] = datetime.fromisoformat(doc_data['created_at'])
                            doc_data['updated_at'] = datetime.fromisoformat(doc_data['updated_at'])
                            
                            search_doc = SearchDocument(**doc_data)
                            self.documents[tenant_id][index_name][doc_id] = search_doc
                            
                            # Rebuild BM25 index
                            if search_doc.text_fields:
                                text_content = " ".join([
                                    str(search_doc.content.get(field, "")) 
                                    for field in search_doc.text_fields
                                ])
                                self.bm25_indices[tenant_id][index_name].add_document(doc_id, text_content)
                            
                            # Rebuild vector index
                            if search_doc.vector_field and search_doc.vector_field in search_doc.content:
                                vector_data = np.array([search_doc.content[search_doc.vector_field]], dtype=np.float32)
                                self.vector_indices[tenant_id][index_name].add_vectors([doc_id], vector_data)
                
                total_docs = sum(
                    len(docs) for tenant_data in data.values() 
                    for docs in tenant_data.values()
                )
                logger.info(f"Loaded {total_docs} documents from persistence")
                
        except Exception as e:
            logger.error(f"Error loading persisted search data: {e}")
    
    async def _periodic_persistence(self):
        """Background task to periodically persist data to disk."""
        persistence_interval = 300  # 5 minutes
        
        while True:
            try:
                await asyncio.sleep(persistence_interval)
                await self.persist_data()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in search persistence task: {e}")
    
    async def persist_data(self):
        """Persist search data to disk."""
        try:
            with self._lock:
                # Prepare data for persistence
                persist_data = {}
                
                for tenant_id, tenant_indices in self.documents.items():
                    persist_data[tenant_id] = {}
                    
                    for index_name, docs in tenant_indices.items():
                        persist_data[tenant_id][index_name] = {}
                        
                        for doc_id, search_doc in docs.items():
                            doc_dict = asdict(search_doc)
                            # Convert datetime objects to ISO strings
                            doc_dict['created_at'] = search_doc.created_at.isoformat()
                            doc_dict['updated_at'] = search_doc.updated_at.isoformat()
                            
                            persist_data[tenant_id][index_name][doc_id] = doc_dict
                
                # Write to file
                index_file = self.data_directory / "search_indices.json"
                with open(index_file, 'w') as f:
                    json.dump(persist_data, f, indent=2)
                
                logger.debug("Persisted search data to disk")
                
        except Exception as e:
            logger.error(f"Error persisting search data: {e}")
    
    def get_search_stats(self) -> Dict[str, Any]:
        """Get search service statistics."""
        with self._lock:
            total_docs = 0
            total_indices = 0
            tenant_stats = {}
            
            for tenant_id, tenant_indices in self.documents.items():
                tenant_doc_count = 0
                tenant_index_count = len(tenant_indices)
                
                for index_name, docs in tenant_indices.items():
                    tenant_doc_count += len(docs)
                
                tenant_stats[tenant_id] = {
                    "indices": tenant_index_count,
                    "documents": tenant_doc_count
                }
                
                total_docs += tenant_doc_count
                total_indices += tenant_index_count
            
            return {
                "total_documents": total_docs,
                "total_indices": total_indices,
                "tenant_stats": tenant_stats,
                "faiss_available": FAISS_AVAILABLE,
                "vector_dimension": self.settings.local.vector_dimensions
            }
    
    async def shutdown(self):
        """Shutdown the search service and persist data."""
        logger.info("Shutting down local search service")
        
        # Cancel background task
        if self._persistence_task:
            self._persistence_task.cancel()
            await asyncio.gather(self._persistence_task, return_exceptions=True)
        
        # Final persistence
        await self.persist_data()
        
        logger.info("Local search service shutdown complete")