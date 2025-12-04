# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime
import logging
import time
import zipfile
import tarfile
import tempfile
import shutil
from pathlib import Path

from db.database import get_db
from models.core import ContextDocument, DocumentType, IndexingStatus, SearchHistory
from services.context_retrieval import context_retriever
from services.token_counter import get_token_counter

router = APIRouter(prefix="/api/rag", tags=["rag"])
logger = logging.getLogger(__name__)


# Pydantic Schemas
class DocumentUploadResponse(BaseModel):
    id: int
    name: str
    document_type: DocumentType
    size: int
    status: IndexingStatus
    message: str


class DocumentResponse(BaseModel):
    id: int
    project_id: int
    filename: str
    original_filename: str
    document_type: DocumentType
    file_size: int
    mime_type: Optional[str]
    indexing_status: IndexingStatus
    indexed_chunks_count: Optional[int]
    created_at: datetime
    indexed_at: Optional[datetime]

    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    query: str
    project_id: int
    top_k: int = 5
    use_hyde: bool = False


class SearchResult(BaseModel):
    document_id: int
    document_name: str
    chunk_text: str
    similarity_score: float
    metadata: Optional[dict]

    # NEW: Measured facts about this chunk
    chunk_id: Optional[str] = None
    chunk_index: Optional[int] = None
    total_chunks_in_doc: Optional[int] = None
    chunk_token_count: int = 0  # Measured token count
    chunk_char_count: int = 0   # Character count
    source_location: Optional[str] = None  # Lines, pages, etc.
    retrieval_rank: int = 0  # Position in results (1-based)


class SearchMetrics(BaseModel):
    """Measured metrics from search execution - factual data only"""
    query: str
    use_hyde: bool
    hyde_auto_detected: bool  # Was HyDE auto-detected?
    use_toon: bool
    top_k: int

    # Measured timing (milliseconds)
    retrieval_duration_ms: float

    # Measured token counts (actual, not estimated)
    query_tokens: int
    total_context_tokens: int  # Sum of all retrieved chunks

    # Measured similarity scores
    results_count: int
    avg_similarity_score: float
    max_similarity_score: float
    min_similarity_score: float


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total_results: int

    # NEW: Real measured metrics
    metrics: Optional[SearchMetrics] = None


async def index_document_background(document_id: int):
    """Background task to index a document with embeddings"""
    from db.database import SessionLocal
    from services.context_document_indexer import context_document_indexer

    db = SessionLocal()
    try:
        doc = db.query(ContextDocument).filter(ContextDocument.id == document_id).first()
        if not doc:
            logger.error(f"Document {document_id} not found for indexing")
            return

        if not doc.file_path:
            logger.error(f"Document {document_id} has no file_path")
            doc.indexing_status = IndexingStatus.FAILED
            db.commit()
            return

        # Update status to indexing
        doc.indexing_status = IndexingStatus.INDEXING
        file_path = doc.file_path  # Save for later use
        db.commit()
        db.close()

        # Index the document (outside of db session)
        result = await context_document_indexer.index_document(
            document_id=document_id,
            file_path=file_path
        )

        # Update status to ready with new session
        db = SessionLocal()
        doc = db.query(ContextDocument).filter(ContextDocument.id == document_id).first()
        if doc:
            doc.indexing_status = IndexingStatus.READY
            doc.indexed_at = datetime.utcnow()
            doc.indexed_chunks_count = result.get("embeddings_stored", 0)
            db.commit()
        db.close()

        logger.info(f"Document {document_id} indexed successfully")

    except Exception as e:
        logger.error(f"Failed to index document {document_id}: {e}", exc_info=True)
        # Create fresh session for error handling
        try:
            db.close()
        except:
            pass

        db = SessionLocal()
        try:
            doc = db.query(ContextDocument).filter(ContextDocument.id == document_id).first()
            if doc:
                doc.indexing_status = IndexingStatus.FAILED
                db.commit()
        finally:
            db.close()


# Endpoints
@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    project_id: int,
    file: UploadFile = File(None),
    metadata: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Upload a document for RAG indexing"""
    from services.file_storage import file_storage
    import json

    logger.info(f"Upload request - project_id={project_id}, file={file.filename if file else 'None'}, metadata={metadata}")

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Parse metadata if provided
    doc_metadata = {}
    if metadata:
        try:
            doc_metadata = json.loads(metadata)
        except json.JSONDecodeError:
            logger.warning(f"Invalid metadata JSON: {metadata}")

    # Save file to disk
    file_path = file_storage.save_file(project_id, file.filename, content)

    # Determine document type from file extension (expanded support)
    file_ext = file.filename.split('.')[-1].lower()
    doc_type_map = {
        'txt': DocumentType.TEXT,
        'md': DocumentType.MARKDOWN,
        'pdf': DocumentType.PDF,
        'json': DocumentType.JSON,
        'py': DocumentType.CODE,
        'js': DocumentType.CODE,
        'ts': DocumentType.CODE,
        'tsx': DocumentType.CODE,
        'jsx': DocumentType.CODE,
        'java': DocumentType.CODE,
        'c': DocumentType.CODE,
        'cpp': DocumentType.CODE,
        'h': DocumentType.CODE,
        'hpp': DocumentType.CODE,
        'cs': DocumentType.CODE,
        'rb': DocumentType.CODE,
        'go': DocumentType.CODE,
        'rs': DocumentType.CODE,
        'php': DocumentType.CODE,
        'swift': DocumentType.CODE,
        'kt': DocumentType.CODE,
        'scala': DocumentType.CODE,
        'r': DocumentType.CODE,
        'sql': DocumentType.CODE,
        'sh': DocumentType.CODE,
        'bash': DocumentType.CODE,
        'html': DocumentType.HTML,
        'htm': DocumentType.HTML,
        'xml': DocumentType.XML,
        'csv': DocumentType.CSV,
        'yaml': DocumentType.YAML,
        'yml': DocumentType.YAML,
        'doc': DocumentType.DOCX,
        'docx': DocumentType.DOCX,
        'rtf': DocumentType.TEXT,
        'odt': DocumentType.TEXT,
        'epub': DocumentType.TEXT,
        'ppt': DocumentType.TEXT,
        'pptx': DocumentType.TEXT,
        'xls': DocumentType.CSV,
        'xlsx': DocumentType.CSV,
        'png': DocumentType.IMAGE,
        'jpg': DocumentType.IMAGE,
        'jpeg': DocumentType.IMAGE,
        'gif': DocumentType.IMAGE,
        'bmp': DocumentType.IMAGE,
        'tiff': DocumentType.IMAGE,
        'webp': DocumentType.IMAGE,
    }
    document_type = doc_type_map.get(file_ext, DocumentType.TEXT)

    # Create document record with correct schema
    # Build name, tags and description from metadata
    custom_name = doc_metadata.get("name") if isinstance(doc_metadata, dict) else None
    description = doc_metadata.get("description") if isinstance(doc_metadata, dict) else None
    tags = doc_metadata.get("tags") if isinstance(doc_metadata, dict) else None

    doc = ContextDocument(
        project_id=project_id,
        filename=custom_name or file.filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        document_type=document_type,
        indexing_status=IndexingStatus.NOT_INDEXED,
        description=description,
        tags=tags or []
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Queue document for embedding generation and indexing
    background_tasks.add_task(index_document_background, doc.id)

    return DocumentUploadResponse(
        id=doc.id,
        name=doc.filename,
        document_type=doc.document_type,
        size=doc.file_size,
        status=doc.indexing_status,
        message="Document uploaded successfully. Indexing queued."
    )


async def _process_single_file_for_bulk(
    background_tasks: BackgroundTasks,
    project_id: int,
    file: UploadFile,
    metadata: dict,
    db: Session
) -> DocumentUploadResponse:
    """Helper function to process a single file during bulk upload"""
    from services.file_storage import file_storage

    # Read file content
    content = await file.read()
    file_size = len(content)

    # Save file to disk
    file_path = file_storage.save_file(project_id, file.filename, content)

    # Determine document type from file extension (expanded support)
    file_ext = file.filename.split('.')[-1].lower()
    doc_type_map = {
        'txt': DocumentType.TEXT,
        'md': DocumentType.MARKDOWN,
        'pdf': DocumentType.PDF,
        'json': DocumentType.JSON,
        'py': DocumentType.CODE,
        'js': DocumentType.CODE,
        'ts': DocumentType.CODE,
        'tsx': DocumentType.CODE,
        'jsx': DocumentType.CODE,
        'java': DocumentType.CODE,
        'c': DocumentType.CODE,
        'cpp': DocumentType.CODE,
        'h': DocumentType.CODE,
        'hpp': DocumentType.CODE,
        'cs': DocumentType.CODE,
        'rb': DocumentType.CODE,
        'go': DocumentType.CODE,
        'rs': DocumentType.CODE,
        'php': DocumentType.CODE,
        'swift': DocumentType.CODE,
        'kt': DocumentType.CODE,
        'scala': DocumentType.CODE,
        'r': DocumentType.CODE,
        'sql': DocumentType.CODE,
        'sh': DocumentType.CODE,
        'bash': DocumentType.CODE,
        'html': DocumentType.HTML,
        'htm': DocumentType.HTML,
        'xml': DocumentType.XML,
        'csv': DocumentType.CSV,
        'yaml': DocumentType.YAML,
        'yml': DocumentType.YAML,
        'doc': DocumentType.DOCX,
        'docx': DocumentType.DOCX,
        'rtf': DocumentType.TEXT,
        'odt': DocumentType.TEXT,
        'epub': DocumentType.TEXT,
        'ppt': DocumentType.TEXT,
        'pptx': DocumentType.TEXT,
        'xls': DocumentType.CSV,
        'xlsx': DocumentType.CSV,
        'png': DocumentType.IMAGE,
        'jpg': DocumentType.IMAGE,
        'jpeg': DocumentType.IMAGE,
        'gif': DocumentType.IMAGE,
        'bmp': DocumentType.IMAGE,
        'tiff': DocumentType.IMAGE,
        'webp': DocumentType.IMAGE,
    }
    document_type = doc_type_map.get(file_ext, DocumentType.TEXT)

    # Build metadata
    custom_name = metadata.get("name") if isinstance(metadata, dict) else None
    description = metadata.get("description") if isinstance(metadata, dict) else None
    tags = metadata.get("tags") if isinstance(metadata, dict) else None

    # Create document record
    doc = ContextDocument(
        project_id=project_id,
        filename=custom_name or file.filename,
        original_filename=file.filename,
        file_path=file_path,
        file_size=file_size,
        mime_type=file.content_type,
        document_type=document_type,
        indexing_status=IndexingStatus.NOT_INDEXED,
        description=description,
        tags=tags or []
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    # Queue for indexing
    background_tasks.add_task(index_document_background, doc.id)

    return DocumentUploadResponse(
        id=doc.id,
        name=doc.filename,
        document_type=doc.document_type,
        size=doc.file_size,
        status=doc.indexing_status,
        message="Document uploaded successfully. Indexing queued."
    )


@router.post("/upload-bulk", response_model=List[DocumentUploadResponse])
async def upload_documents_bulk(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    project_id: int = Form(...),
    extract_archives: bool = Form(True),
    metadata: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """
    Upload multiple documents or archives for RAG indexing.

    Supports:
    - Multiple file uploads
    - Archive extraction (.zip, .tar, .tar.gz, .tgz)
    - Folder structures (preserves paths as metadata)

    Note: Files should be sent as multipart/form-data with field name 'files'
    """
    import json

    try:
        logger.info(f"Bulk upload request received - project_id={project_id}, extract_archives={extract_archives}")
        logger.info(f"Number of files received: {len(files) if files else 0}")

        if not files or len(files) == 0:
            raise HTTPException(status_code=400, detail="No files provided")

        # Parse metadata if provided
        doc_metadata = {}
        if metadata:
            try:
                doc_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                logger.warning(f"Invalid metadata JSON: {metadata}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in bulk upload validation: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Invalid request: {str(e)}")

    uploaded_docs = []

    # Process each file
    for file in files:
        try:
            logger.info(f"Processing file: {file.filename}")

            # Check if it's an archive
            file_ext = file.filename.split('.')[-1].lower()
            is_archive = file_ext in ['zip', 'tar', 'gz', 'tgz']

            if is_archive and extract_archives:
                # For archives with extraction, process extracted files
                logger.info(f"Extracting archive: {file.filename}")
                content = await file.read()

                # Create temporary directory for extraction
                with tempfile.TemporaryDirectory() as temp_dir:
                    temp_path = Path(temp_dir)
                    archive_path = temp_path / file.filename

                    # Save archive to temp location
                    archive_path.write_bytes(content)

                    # Extract based on type
                    try:
                        if file_ext == 'zip':
                            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                                zip_ref.extractall(temp_path)
                        elif file_ext in ['tar', 'gz', 'tgz']:
                            with tarfile.open(archive_path, 'r:*') as tar_ref:
                                tar_ref.extractall(temp_path)

                        # Process all extracted files
                        for extracted_file in temp_path.rglob('*'):
                            if extracted_file.is_file() and extracted_file != archive_path:
                                # Get relative path from archive root
                                relative_path = str(extracted_file.relative_to(temp_path))
                                logger.info(f"Processing extracted file: {relative_path}")

                                # Read file and create mock UploadFile
                                file_content = extracted_file.read_bytes()

                                class MockUploadFile:
                                    def __init__(self, filename, content, content_type='application/octet-stream'):
                                        self.filename = filename
                                        self.content = content
                                        self.content_type = content_type

                                    async def read(self):
                                        return self.content

                                mock_file = MockUploadFile(extracted_file.name, file_content)
                                result = await _process_single_file_for_bulk(
                                    background_tasks, project_id, mock_file, doc_metadata, db
                                )
                                uploaded_docs.append(result)

                    except Exception as e:
                        logger.error(f"Failed to extract archive {file.filename}: {e}")
                        # Upload archive as-is if extraction fails
                        await file.seek(0)
                        result = await _process_single_file_for_bulk(
                            background_tasks, project_id, file, doc_metadata, db
                        )
                        uploaded_docs.append(result)
            else:
                # Regular file upload (no extraction)
                result = await _process_single_file_for_bulk(
                    background_tasks, project_id, file, doc_metadata, db
                )
                uploaded_docs.append(result)

        except Exception as e:
            logger.error(f"Failed to process file {file.filename}: {e}", exc_info=True)
            # Continue with other files
            continue

    logger.info(f"Bulk upload completed: {len(uploaded_docs)} documents uploaded")
    return uploaded_docs


@router.get("/documents", response_model=List[DocumentResponse])
async def list_documents(
    project_id: int,
    skip: int = 0,
    limit: int = 50,
    status: Optional[IndexingStatus] = None,
    db: Session = Depends(get_db)
):
    """List documents for a project"""
    query = db.query(ContextDocument).filter(ContextDocument.project_id == project_id)

    if status:
        query = query.filter(ContextDocument.indexing_status == status)

    documents = query.offset(skip).limit(limit).all()
    return documents


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific document by ID"""
    doc = db.query(ContextDocument).filter(ContextDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc


@router.delete("/documents/{document_id}", status_code=204)
async def delete_document(
    document_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a document and its associated vector embeddings.

    This operation:
    1. Finds the document in PostgreSQL
    2. Deletes associated vector embeddings from pgvector table
    3. Deletes the document file from disk
    4. Deletes the document record from PostgreSQL
    """
    from services.file_storage import file_storage

    doc = db.query(ContextDocument).filter(ContextDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    project_id = doc.project_id
    file_path = doc.file_path

    try:
        # Delete associated embeddings from vector database
        if project_id:
            from services.llama_config import get_vector_store

            logger.info(f"Deleting vector embeddings for document {document_id} in project {project_id}")

            try:
                # Check if table exists first to avoid transaction errors
                from sqlalchemy import text
                table_name = f"data_project_index_{project_id}"

                check_query = text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = :table_name
                    )
                """)

                table_exists = db.execute(check_query, {"table_name": table_name}).scalar()

                if table_exists:
                    vector_store = get_vector_store(project_id)

                    # Delete vectors where metadata contains this document's filename
                    delete_query = text(f"""
                        DELETE FROM {table_name}
                        WHERE metadata_->>'filename' = :filename
                    """)

                    result = db.execute(delete_query, {"filename": doc.filename})
                    deleted_count = result.rowcount
                    logger.info(f"Deleted {deleted_count} vector embeddings for document {document_id}")
                else:
                    logger.info(f"Vector table {table_name} does not exist yet (document may be pending), skipping vector deletion")

            except Exception as e:
                logger.warning(f"Failed to delete vector embeddings: {e}")
                db.rollback()  # Rollback failed vector deletion to allow document deletion
                # Continue with document deletion even if vector cleanup fails

        # Delete file from disk
        if file_path:
            try:
                file_storage.delete_file(file_path)
            except Exception as e:
                logger.warning(f"Failed to delete file {file_path}: {e}")

        # Delete the document record
        db.delete(doc)
        db.commit()

        logger.info(f"Successfully deleted document {document_id}")
        return None

    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete document {document_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


@router.post("/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Search documents using DNA-augmented HyDE vector similarity.

    This endpoint leverages the existing ContextRetriever service with:
    - Conditional HyDE for code generation queries
    - Project DNA augmentation for context-aware retrieval
    - PostgreSQL + pgvector for semantic search
    - Real-time metrics measurement (tokens, latency, similarity)
    """

    try:
        # Check if project exists and is indexed
        from models.core import Project
        project = db.query(Project).filter(Project.id == request.project_id).first()

        if not project:
            raise HTTPException(status_code=404, detail=f"Project {request.project_id} not found")

        if project.indexing_status != IndexingStatus.READY:
            return SearchResponse(
                query=request.query,
                results=[],
                total_results=0
            )

        # Use the context retriever to perform intelligent search
        logger.info(f"Searching project {request.project_id}: '{request.query}' (hyde={request.use_hyde}, top_k={request.top_k})")

        # START TIMING MEASUREMENT
        start_time = time.time()

        # Determine if HyDE will be auto-detected
        hyde_setting = request.use_hyde
        if hyde_setting is None:
            # HyDE will be auto-detected by context_retriever
            from services.context_retrieval import ContextRetriever
            cr = ContextRetriever()
            hyde_auto_detected = cr.is_code_generation_query(request.query)
        else:
            hyde_auto_detected = hyde_setting

        context_package = await context_retriever.retrieve_context(
            project_id=request.project_id,
            task_description=request.query,
            similarity_top_k=request.top_k,
            include_dna_in_context=False,  # Don't include DNA in API response
            use_hyde=hyde_setting  # Respect user's HyDE preference
        )

        # END TIMING MEASUREMENT
        end_time = time.time()
        retrieval_duration_ms = (end_time - start_time) * 1000  # Convert to milliseconds

        # Extract code chunks from context package
        code_chunks = context_package.get('components', {}).get('code_chunks', [])

        # Get token counter for measuring actual token counts
        token_counter = get_token_counter()

        # Measure query tokens
        query_tokens = token_counter.count_tokens(request.query)

        # Transform to SearchResult format and measure metrics
        results = []
        total_context_tokens = 0
        similarity_scores = []

        for i, chunk in enumerate(code_chunks):
            # Extract metadata from chunk content (formatted by context retriever)
            content = chunk.get('content', '')
            score = chunk.get('score', 0.0)
            if score:
                similarity_scores.append(score)

            # Parse document name from content header
            # Format: "File: path/to/file.py | ..."
            doc_name = "unknown"
            if content.startswith("File: "):
                header_line = content.split('\n')[0]
                parts = header_line.split('|')
                if parts:
                    doc_name = parts[0].replace("File: ", "").strip()

            # MEASURE TOKEN COUNTS (factual data)
            chunk_token_count = token_counter.count_tokens(content)
            chunk_char_count = len(content)
            total_context_tokens += chunk_token_count

            results.append(SearchResult(
                document_id=i + 1,  # Placeholder ID (LlamaIndex nodes don't map directly to doc IDs)
                document_name=doc_name,
                chunk_text=content,
                similarity_score=score or 0.0,
                metadata=context_package.get('metadata', {}),
                # NEW: Real measured metrics
                chunk_id=chunk.get('node_id', None),
                chunk_index=i,
                chunk_token_count=chunk_token_count,
                chunk_char_count=chunk_char_count,
                retrieval_rank=i + 1
            ))

        # Calculate aggregate similarity metrics
        avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 0.0
        max_similarity = max(similarity_scores) if similarity_scores else 0.0
        min_similarity = min(similarity_scores) if similarity_scores else 0.0

        # Build metrics object with all measured facts
        metrics = SearchMetrics(
            query=request.query,
            use_hyde=bool(hyde_setting),
            hyde_auto_detected=hyde_auto_detected,
            use_toon=False,  # Default to False for now
            top_k=request.top_k,
            retrieval_duration_ms=retrieval_duration_ms,
            query_tokens=query_tokens,
            total_context_tokens=total_context_tokens,
            results_count=len(results),
            avg_similarity_score=avg_similarity,
            max_similarity_score=max_similarity,
            min_similarity_score=min_similarity
        )

        # Store search in history for analysis
        search_history = SearchHistory(
            project_id=request.project_id,
            query=request.query,
            use_hyde=bool(hyde_setting),
            hyde_auto_detected=hyde_auto_detected,
            use_toon=False,  # Default to False for now
            top_k=request.top_k,
            results_count=len(results),
            retrieval_duration_ms=retrieval_duration_ms,
            query_tokens=query_tokens,
            total_context_tokens=total_context_tokens,
            avg_similarity=avg_similarity,
            max_similarity=max_similarity,
            min_similarity=min_similarity,
            results_data={
                "query": request.query,
                "results_count": len(results),
                "metrics": metrics.dict()
            }
        )
        db.add(search_history)
        db.commit()

        logger.info(f"Search completed: {len(results)} results, {retrieval_duration_ms:.1f}ms, {total_context_tokens} tokens")

        return SearchResponse(
            query=request.query,
            results=results,
            total_results=len(results),
            metrics=metrics
        )

    except ValueError as e:
        # Project not ready or not found
        logger.warning(f"Search failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/index/{document_id}")
async def index_document(
    document_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Manually trigger indexing for a specific document"""
    doc = db.query(ContextDocument).filter(ContextDocument.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Update status and queue background task
    doc.indexing_status = IndexingStatus.INDEXING
    db.commit()

    # Queue document for embedding generation and indexing
    background_tasks.add_task(index_document_background, doc.id)

    return {
        "message": "Document indexing started",
        "document_id": document_id,
        "status": IndexingStatus.INDEXING
    }


# Pydantic schema for search history
class SearchHistoryResponse(BaseModel):
    id: int
    project_id: int
    query: str
    use_hyde: bool
    hyde_auto_detected: bool
    use_toon: bool
    top_k: int
    results_count: int
    retrieval_duration_ms: float
    query_tokens: int
    total_context_tokens: int
    avg_similarity: Optional[float]
    max_similarity: Optional[float]
    min_similarity: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/search-history", response_model=List[SearchHistoryResponse])
async def get_search_history(
    project_id: int,
    limit: int = 50,
    skip: int = 0,
    db: Session = Depends(get_db)
):
    """
    Get search history for a project with real measured metrics.
    Returns paginated list of past searches with all factual data.
    """
    history = (
        db.query(SearchHistory)
        .filter(SearchHistory.project_id == project_id)
        .order_by(SearchHistory.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return history


@router.get("/projects/{project_id}/storage-stats")
async def get_project_storage_stats(
    project_id: int,
    db: Session = Depends(get_db)
):
    """
    Get storage statistics for a project. RELOAD_MARKER_2025

    Returns both estimated and actual storage measurements:
    - Actual: Measured PostgreSQL table size
    - Estimated: Calculated from storage formulas (when tracking enabled)
    - Configuration: Current chunk size, embedding dimensions
    - Breakdown: Vector store vs document store

    This gives users visibility into storage costs and helps with capacity planning.
    """
    from services.storage_estimator import storage_estimator
    from models.core import Project

    try:
        # Get project
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            raise HTTPException(status_code=404, detail=f"Project {project_id} not found")

        # Measure actual storage from PostgreSQL
        actual_storage = storage_estimator.measure_actual_storage(project_id)

        # Get configuration
        chunk_size = project.configuration.get("chunk_size_config", 1024) if project.configuration else 1024
        chunk_overlap = project.configuration.get("chunk_overlap_config", 20) if project.configuration else 20
        embedding_dimensions = project.embedding_dimension or 384

        response = {
            "project_id": project_id,
            "project_name": project.name,
            "indexing_status": project.indexing_status.value if project.indexing_status else "not_indexed",
            "last_indexed_at": project.last_indexed_at.isoformat() if project.last_indexed_at else None,
            "actual_storage": actual_storage,
            "configuration": {
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "embedding_dimensions": embedding_dimensions,
                "indexed_nodes_count": project.indexed_nodes_count or 0
            },
            "storage_per_document_gb": round(
                actual_storage["total_bytes"] / (1024**3) / max(1, len(project.documents))
            , 3) if project.documents else 0,
            "message": "Actual storage measured from PostgreSQL system catalog"
        }

        logger.info(f"Storage stats for project {project_id}: {actual_storage['total_gb']} GB")
        return response

    except Exception as e:
        logger.error(f"Failed to get storage stats for project {project_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get storage stats: {str(e)}")
