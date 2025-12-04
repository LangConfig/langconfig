# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
Storage Estimation Service

Implements the mathematical formulas from the LlamaIndex analysis document
to estimate and measure vector storage requirements.

Formulas:
- VectorStore Size: N × D × P × O
  - N = num_vectors (chunks)
  - D = embedding_dimensions
  - P = bytes_per_dimension (4 for float32)
  - O = overhead_factor (1.2 for HNSW)

- DocumentStore Size: (Raw × Overlap + Metadata) × Serialization
  - Overlap factor = 1 + (chunk_overlap / (chunk_size - chunk_overlap))
  - Serialization factor = 1.2 (JSON overhead)

- Num Vectors: total_tokens / (chunk_size - chunk_overlap)
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from db.database import SessionLocal
from models.core import Project
from services.llama_config import get_table_name

logger = logging.getLogger(__name__)


class StorageEstimator:
    """Estimate and measure vector storage requirements"""
    
    def __init__(self):
        """Initialize storage estimator with default parameters"""
        self.bytes_per_dimension = 4  # float32
        self.hnsw_overhead_factor = 1.2
        self.serialization_factor = 1.2
        self.metadata_bytes_per_chunk = 500  # Estimated metadata overhead
    
    def estimate_vector_store_size(
        self,
        num_vectors: int,
        embedding_dimensions: int,
        bytes_per_dimension: Optional[int] = None,
        overhead_factor: Optional[float] = None
    ) -> int:
        """
        Calculate vector store size: N × D × P × O
        
        Args:
            num_vectors: Total number of chunks/vectors
            embedding_dimensions: Dimension of embedding model
            bytes_per_dimension: Bytes per float (default: 4 for float32)
            overhead_factor: HNSW index overhead (default: 1.2)
        
        Returns:
            Estimated size in bytes
        """
        bytes_per_dim = bytes_per_dimension or self.bytes_per_dimension
        overhead = overhead_factor or self.hnsw_overhead_factor
        
        # Formula: N × D × P × O
        raw_vector_size = num_vectors * embedding_dimensions * bytes_per_dim
        total_size = int(raw_vector_size * overhead)
        
        logger.debug(
            f"Vector store estimate: {num_vectors} vectors × {embedding_dimensions}D "
            f"× {bytes_per_dim}B × {overhead} overhead = {total_size:,} bytes "
            f"({total_size / (1024**3):.2f} GB)"
        )
        
        return total_size
    
    def estimate_document_store_size(
        self,
        raw_data_size_bytes: int,
        chunk_size: int,
        chunk_overlap: int,
        metadata_overhead_bytes: Optional[int] = None,
        serialization_factor: Optional[float] = None
    ) -> int:
        """
        Calculate document store size: (Raw × Overlap + Metadata) × Serialization
        
        Args:
            raw_data_size_bytes: Original document size in bytes
            chunk_size: Chunk size in tokens
            chunk_overlap: Overlap size in tokens
            metadata_overhead_bytes: Metadata per chunk (default: 500 bytes)
            serialization_factor: JSON overhead (default: 1.2)
        
        Returns:
            Estimated size in bytes
        """
        metadata_bytes = metadata_overhead_bytes or self.metadata_bytes_per_chunk
        serialization = serialization_factor or self.serialization_factor
        
        # Calculate overlap factor
        stride = chunk_size - chunk_overlap
        overlap_factor = 1.0 + (chunk_overlap / stride) if stride > 0 else 1.0
        
        # Calculate number of chunks to estimate metadata overhead
        num_chunks = self.calculate_num_vectors(
            total_tokens=raw_data_size_bytes // 4,  # Rough estimate: 4 chars per token
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Formula: (Raw × Overlap + Metadata) × Serialization
        text_with_overlap = raw_data_size_bytes * overlap_factor
        total_metadata = num_chunks * metadata_bytes
        total_size = int((text_with_overlap + total_metadata) * serialization)
        
        logger.debug(
            f"Document store estimate: {raw_data_size_bytes:,} bytes × {overlap_factor:.2f} overlap "
            f"+ {total_metadata:,} metadata × {serialization} serialization = {total_size:,} bytes "
            f"({total_size / (1024**3):.2f} GB)"
        )
        
        return total_size
    
    def calculate_num_vectors(
        self,
        total_tokens: int,
        chunk_size: int,
        chunk_overlap: int
    ) -> int:
        """
        Calculate number of vectors/chunks: total_tokens / (chunk_size - chunk_overlap)
        
        Args:
            total_tokens: Total tokens in corpus
            chunk_size: Chunk size in tokens
            chunk_overlap: Overlap size in tokens
        
        Returns:
            Number of chunks that will be created
        """
        stride = chunk_size - chunk_overlap
        if stride <= 0:
            raise ValueError(f"Invalid chunking: chunk_size ({chunk_size}) must be > chunk_overlap ({chunk_overlap})")
        
        num_vectors = max(1, total_tokens // stride)
        
        logger.debug(
            f"Num vectors: {total_tokens:,} tokens / {stride} stride = {num_vectors:,} chunks"
        )
        
        return num_vectors
    
    def estimate_total_storage(
        self,
        raw_data_size_bytes: int,
        total_tokens: int,
        chunk_size: int,
        chunk_overlap: int,
        embedding_dimensions: int
    ) -> Dict[str, Any]:
        """
        Calculate complete storage estimate for a corpus
        
        Args:
            raw_data_size_bytes: Original data size
            total_tokens: Total tokens in corpus
            chunk_size: Chunk size in tokens
            chunk_overlap: Overlap in tokens
            embedding_dimensions: Embedding model dimensions
        
        Returns:
            Dictionary with storage breakdown and estimates
        """
        # Calculate number of vectors
        num_vectors = self.calculate_num_vectors(total_tokens, chunk_size, chunk_overlap)
        
        # Estimate vector store
        vector_store_bytes = self.estimate_vector_store_size(
            num_vectors=num_vectors,
            embedding_dimensions=embedding_dimensions
        )
        
        # Estimate document store
        document_store_bytes = self.estimate_document_store_size(
            raw_data_size_bytes=raw_data_size_bytes,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # Total
        total_bytes = vector_store_bytes + document_store_bytes
        
        return {
            "num_vectors": num_vectors,
            "vector_store_bytes": vector_store_bytes,
            "vector_store_gb": round(vector_store_bytes / (1024**3), 3),
            "document_store_bytes": document_store_bytes,
            "document_store_gb": round(document_store_bytes / (1024**3), 3),
            "total_storage_bytes": total_bytes,
            "total_storage_gb": round(total_bytes / (1024**3), 3),
            "configuration": {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "embedding_dimensions": embedding_dimensions,
                "total_tokens": total_tokens,
                "raw_data_size_bytes": raw_data_size_bytes
            }
        }
    
    def measure_actual_storage(self, project_id: int) -> Dict[str, int]:
        """
        Query PostgreSQL for actual disk usage of vector table
        
        Args:
            project_id: Project ID
        
        Returns:
            Dictionary with actual storage measurements
        """
        table_name = get_table_name(project_id)
        
        try:
            session = SessionLocal()
            try:
                # First check if table exists to avoid PostgreSQL errors
                check_query = text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = :table_name
                    )
                """)

                table_exists = session.execute(
                    check_query,
                    {"table_name": table_name}
                ).scalar()

                if not table_exists:
                    logger.info(f"Table {table_name} does not exist yet (no documents indexed)")
                    return {
                        "exists": False,
                        "total_bytes": 0,
                        "table_bytes": 0,
                        "index_bytes": 0,
                        "total_gb": 0.0
                    }

                # Table exists - now query its size
                # pg_total_relation_size includes table data, indexes, and TOAST
                size_query = text("""
                    SELECT
                        pg_total_relation_size(:table_name) as total_bytes,
                        pg_relation_size(:table_name) as table_bytes,
                        pg_indexes_size(:table_name) as index_bytes
                """)

                result = session.execute(
                    size_query,
                    {"table_name": table_name}
                )
                row = result.fetchone()

                return {
                    "exists": True,
                    "total_bytes": row.total_bytes or 0,
                    "table_bytes": row.table_bytes or 0,
                    "index_bytes": row.index_bytes or 0,
                    "total_gb": round((row.total_bytes or 0) / (1024**3), 3)
                }
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Failed to measure storage for project {project_id}: {e}")
            return {
                "exists": False,
                "error": str(e),
                "total_bytes": 0,
                "table_bytes": 0,
                "index_bytes": 0,
                "total_gb": 0.0
            }
    
    def compare_estimate_vs_actual(
        self,
        project_id: int,
        db: Session
    ) -> Dict[str, Any]:
        """
        Compare estimated storage vs actual PostgreSQL usage
        
        Args:
            project_id: Project ID
            db: Database session
        
        Returns:
            Comparison report with accuracy metrics
        """
        # Get project configuration
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        # Get actual storage
        actual = self.measure_actual_storage(project_id)
        
        if not actual["exists"]:
            return {
                "error": "Project not indexed yet",
                "actual_storage": actual
            }
        
        # Calculate estimate based on project data
        # Note: We'd need to track raw_data_size and total_tokens in Project model
        # For now, return what we can measure
        
        return {
            "project_id": project_id,
            "actual_storage": actual,
            "indexed_nodes_count": project.indexed_nodes_count,
            "embedding_dimension": project.embedding_dimension,
            "message": "To enable estimates, ensure chunk_size_config and total tokens are tracked in Project model"
        }


# Global instance
storage_estimator = StorageEstimator()


# Convenience functions
async def estimate_storage(
    raw_data_size_bytes: int,
    total_tokens: int,
    chunk_size: int = 1024,
    chunk_overlap: int = 20,
    embedding_dimensions: int = 384
) -> Dict[str, Any]:
    """
    Convenience function to estimate storage requirements
    
    Example:
        >>> estimate = await estimate_storage(
        ...     raw_data_size_bytes=100 * 1024**3,  # 100 GB
        ...     total_tokens=26_843_545_600,        # ~26B tokens
        ...     chunk_size=1024,
        ...     chunk_overlap=20,
        ...     embedding_dimensions=384
        ... )
        >>> print(f"Estimated storage: {estimate['total_storage_gb']} GB")
    """
    return storage_estimator.estimate_total_storage(
        raw_data_size_bytes=raw_data_size_bytes,
        total_tokens=total_tokens,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        embedding_dimensions=embedding_dimensions
    )


def measure_project_storage(project_id: int) -> Dict[str, Any]:
    """
    Convenience function to measure actual storage for a project
    
    Example:
        >>> actual = measure_project_storage(project_id=1)
        >>> print(f"Actual storage: {actual['total_gb']} GB")
    """
    return storage_estimator.measure_actual_storage(project_id)
