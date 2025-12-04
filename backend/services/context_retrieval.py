# Copyright (c) 2025 Cade Russell (Ghost Peony)
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

"""
DNA-Augmented HyDE Context Retrieval Service

This service implements intelligent context retrieval using LlamaIndex's Query Engine
with HyDE (Hypothetical Document Embeddings) augmented with Project DNA for enhanced
accuracy and project-specific contextual understanding.
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timezone
from pathlib import Path

from llama_index.core import Settings, PromptTemplate
from llama_index.core.indices.query.query_transform import HyDEQueryTransform
from llama_index.core.schema import NodeWithScore, TextNode
from llama_index.core.retrievers import BaseRetriever, VectorIndexRetriever
from llama_index.core.indices import VectorStoreIndex

from config import settings
from db.database import SessionLocal
from models.core import Project, IndexingStatus
from services.llama_config import get_vector_store, ensure_initialized

logger = logging.getLogger(__name__)

# DNA-Augmented HyDE Prompt Template
HYDE_AUGMENTED_PROMPT_STR = """
Please write a hypothetical code implementation to answer the question.
CRITICAL: Utilize the PROJECT DNA SUMMARY to align your hypothesis with the project's unique structures, signatures, and import patterns.

--- PROJECT DNA SUMMARY ---
{project_dna}
--- END OF SUMMARY ---

Question: {query_str}

Instructions:
1. Study the Project DNA to understand the existing codebase structure
2. Use the same naming conventions, patterns, and architectural styles shown in the DNA
3. Reference existing functions, classes, and modules when appropriate
4. Follow the import patterns and dependencies shown in the DNA
5. Write realistic code that would fit naturally into this project

Hypothetical Implementation (Raw code only):
"""

HYDE_AUGMENTED_PROMPT = PromptTemplate(HYDE_AUGMENTED_PROMPT_STR)

# Fallback prompt when DNA is not available
HYDE_BASIC_PROMPT_STR = """
Please write a hypothetical code implementation to answer the question.

Question: {query_str}

Hypothetical Implementation (Raw code only):
"""

HYDE_BASIC_PROMPT = PromptTemplate(HYDE_BASIC_PROMPT_STR)


class ContextRetriever:
    """
    DNA-Augmented HyDE Context Retrieval System.

    This class provides intelligent context retrieval by combining:
    1. Project DNA for understanding codebase structure
    2. HyDE for generating hypothetical implementations
    3. Semantic similarity search in project embeddings
    4. Intelligent context packaging with token management
    """

    # Keywords that indicate code generation intent
    CODE_GENERATION_KEYWORDS = {
        'implement', 'code', 'write', 'create', 'generate', 'build',
        'develop', 'add', 'how to', 'example', 'function', 'class',
        'method', 'api', 'endpoint', 'component', 'feature', 'module',
        'script', 'program', 'application', 'service'
    }

    def __init__(self, max_context_tokens: int = 8000):
        """
        Initialize the context retriever.

        Args:
            max_context_tokens: Maximum tokens allowed in final context package
        """
        self.max_context_tokens = max_context_tokens
        ensure_initialized()

    @staticmethod
    def is_code_generation_query(query: str) -> bool:
        """
        Detect if a query is asking for code generation/implementation.

        Uses keyword matching to identify queries that would benefit from HyDE.
        This avoids adding LLM latency for intent classification.

        Args:
            query: User's search query

        Returns:
            True if query appears to be asking for code generation
        """
        query_lower = query.lower()

        # Check for code generation keywords
        for keyword in ContextRetriever.CODE_GENERATION_KEYWORDS:
            if keyword in query_lower:
                logger.debug(f"Code generation intent detected (keyword: '{keyword}')")
                return True

        # Check for question patterns that typically ask for implementation
        implementation_patterns = [
            r'how (do|can|to|would)\s+(i|you|we)',  # "how do I...", "how to..."
            r'what(\'s| is) the (way|best way|correct way) to',
            r'show me',
            r'give me',
            r'need (a|an|to)',
        ]

        for pattern in implementation_patterns:
            if re.search(pattern, query_lower):
                logger.debug(f"Code generation intent detected (pattern: '{pattern}')")
                return True

        logger.debug("No code generation intent detected - using direct semantic search")
        return False
    
    async def get_project_retriever(self, project_id: int, similarity_top_k: int = 8) -> BaseRetriever:
        """
        Initialize and return a project-specific retriever.
        
        Args:
            project_id: Project identifier
            similarity_top_k: Number of similar chunks to retrieve
            
        Returns:
            BaseRetriever: Configured retriever for the project
            
        Raises:
            ValueError: If project not found or not indexed
            RuntimeError: If retriever initialization fails
        """
        logger.info(f"Initializing retriever for project {project_id}")
        
        try:
            # Check project indexing status
            async with SessionLocal() as session:
                project = await session.get(Project, project_id)
                if not project:
                    raise ValueError(f"Project {project_id} not found")
                
                if project.indexing_status != IndexingStatus.READY:
                    raise ValueError(
                        f"Project {project_id} is not ready for retrieval. "
                        f"Status: {project.indexing_status.value if project.indexing_status else 'not_indexed'}"
                    )
            
            # Initialize vector store and retriever
            vector_store = get_vector_store(project_id)
            
            # Create a VectorStoreIndex from the vector store
            index = VectorStoreIndex.from_vector_store(vector_store)
            
            # Create retriever from the index
            retriever = VectorIndexRetriever(
                index=index,
                similarity_top_k=similarity_top_k,
            )
            
            logger.info(f"Successfully initialized retriever for project {project_id}")
            return retriever
            
        except Exception as e:
            logger.error(f"Failed to initialize retriever for project {project_id}: {e}")
            raise RuntimeError(f"Retriever initialization failed: {e}")
    
    async def get_project_dna(self, project_id: int) -> Optional[str]:
        """
        Fetch Project DNA summary from database.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Project DNA summary string, or None if not available
        """
        try:
            async with SessionLocal() as session:
                project = await session.get(Project, project_id)
                if project and project.dna_summary:
                    logger.debug(f"Retrieved DNA summary for project {project_id} ({len(project.dna_summary)} chars)")
                    return project.dna_summary
                else:
                    logger.warning(f"No DNA summary available for project {project_id}")
                    return None
                    
        except Exception as e:
            logger.error(f"Failed to fetch DNA for project {project_id}: {e}")
            return None
    
    def create_hyde_transform(self, project_dna: Optional[str] = None) -> HyDEQueryTransform:
        """
        Create HyDE query transformer with appropriate prompt template.

        Args:
            project_dna: Project DNA summary (if available)

        Returns:
            Configured HyDEQueryTransform instance
        """
        if project_dna:
            logger.debug("Creating DNA-augmented HyDE transformer")
            # Inject DNA into the prompt template
            dna_prompt_str = HYDE_AUGMENTED_PROMPT_STR.replace("{project_dna}", project_dna)
            hyde_prompt = PromptTemplate(dna_prompt_str)
        else:
            logger.debug("Creating basic HyDE transformer (no DNA)")
            hyde_prompt = HYDE_BASIC_PROMPT

        return HyDEQueryTransform(
            llm=Settings.llm,
            hyde_prompt=hyde_prompt,
            include_original=False  # Use only the hypothesis for retrieval
        )
    
    async def retrieve_context(
        self,
        project_id: int,
        task_description: str,
        similarity_top_k: int = 8,
        include_dna_in_context: bool = True,
        use_hyde: Optional[bool] = None,  # None = auto-detect, True = force, False = disable
        tracker=None,  # Optional ContextUsageTracker
        session_id: Optional[str] = None  # NEW: Filter by session for session-scoped docs
    ) -> Dict[str, Any]:
        """
        Main context retrieval function with conditional DNA-augmented HyDE.

        This function orchestrates the complete retrieval process:
        1. Fetch Project DNA from database
        2. Detect query intent (code generation vs general search)
        3. Conditionally use HyDE for code generation queries
        4. Retrieve semantically similar chunks
        5. Assemble comprehensive context package

        Args:
            project_id: Project identifier
            task_description: User's task or question
            similarity_top_k: Number of chunks to retrieve
            include_dna_in_context: Whether to include DNA in final context
            use_hyde: Whether to use HyDE (None=auto-detect, True=force, False=disable)
            tracker: Optional ContextUsageTracker
            session_id: Optional session ID to filter for session-scoped documents

        Returns:
            Dictionary containing formatted context and metadata

        Raises:
            ValueError: If project not ready for retrieval
            RuntimeError: If retrieval process fails
        """
        logger.info(f"Starting context retrieval for project {project_id}")
        start_time = datetime.now(timezone.utc)

        # Start tracking query if tracker provided
        query_id = None
        if tracker:
            query_id = tracker.start_query(
                query_text=task_description,
                strategy="semantic"
            )

        try:
            # Step 1: Fetch Project DNA
            project_dna = await self.get_project_dna(project_id)

            # Step 2: Initialize retriever
            retriever = await self.get_project_retriever(project_id, similarity_top_k)

            # Step 3: Determine whether to use HyDE
            if use_hyde is None:
                # Auto-detect based on query intent
                should_use_hyde = self.is_code_generation_query(task_description)
            else:
                # Use manual override
                should_use_hyde = use_hyde

            # Step 4: Execute retrieval (with or without HyDE)
            if should_use_hyde:
                logger.info("Using HyDE-augmented retrieval for code generation query")

                # Create HyDE transformer with DNA augmentation
                hyde_transform = self.create_hyde_transform(project_dna)

                # Generate hypothetical implementation using HyDE
                logger.info("Generating HyDE hypothesis for semantic search")
                hyde_result = hyde_transform(task_description)

                # Extract query string from QueryBundle
                if hasattr(hyde_result, 'query_str'):
                    search_query = hyde_result.query_str
                else:
                    search_query = str(hyde_result)

                logger.debug(f"HyDE query generated ({len(search_query)} chars)")
                retrieval_method = 'hyde_augmented' if project_dna else 'hyde_basic'
            else:
                logger.info("Using direct semantic search (no HyDE)")
                search_query = task_description
                retrieval_method = 'direct_semantic'

            # Step 5: Execute retrieval (with optional session filtering)
            logger.debug(f"Executing retrieval with method: {retrieval_method}")

            # If session_id is provided, we need to filter results for session-scoped documents
            if session_id:
                logger.info(f"Filtering retrieval for session: {session_id}")
                # Note: LlamaIndex retrievers don't directly support metadata filtering in aretrieve
                # We need to filter after retrieval or use vector store directly
                # For now, we'll retrieve and then filter
                all_nodes = await retriever.aretrieve(search_query)

                # Filter for session documents only
                nodes = [
                    node for node in all_nodes
                    if node.node.metadata.get('session_id') == session_id and
                       node.node.metadata.get('doc_type') == 'session_document'
                ]
                logger.info(f"Filtered to {len(nodes)} session-specific nodes (from {len(all_nodes)} total)")
            else:
                # Normal retrieval (project documents only)
                nodes = await retriever.aretrieve(search_query)
                logger.info(f"Retrieved {len(nodes)} context nodes")
            
            # Complete query tracking if tracker provided
            if tracker and query_id:
                # Extract results for tracking
                results = [
                    {
                        "document_id": getattr(node.node, 'node_id', 'unknown'),
                        "filename": node.node.metadata.get('relative_path', 'unknown'),
                        "similarity": node.score or 0.0
                    }
                    for node in nodes
                ]
                avg_similarity = sum(r['similarity'] for r in results) / len(results) if results else 0.0
                tracker.complete_query(query_id, results, avg_similarity)

            # Step 6: Assemble context package
            context_package = await self.assemble_context_package(
                nodes=nodes,
                project_dna=project_dna if include_dna_in_context else None,
                task_description=task_description,
                hyde_query=search_query,  # Use the search query (HyDE or original)
                project_id=project_id
            )

            # Calculate retrieval duration
            end_time = datetime.now(timezone.utc)
            duration = (end_time - start_time).total_seconds()

            # Add metadata
            context_package['metadata'].update({
                'retrieval_duration_seconds': duration,
                'nodes_retrieved': len(nodes),
                'hyde_query_generated': should_use_hyde,  # Indicates if HyDE was used
                'dna_available': bool(project_dna),
                'dna_included_in_context': include_dna_in_context,
                'retrieval_method': retrieval_method,
                'use_hyde_override': use_hyde,  # Show if manual override was used
            })
            
            logger.info(f"Context retrieval completed in {duration:.2f}s")
            return context_package
            
        except Exception as e:
            logger.error(f"Context retrieval failed for project {project_id}: {e}")
            raise RuntimeError(f"Context retrieval failed: {e}")
    
    async def assemble_context_package(
        self,
        nodes: List[NodeWithScore],
        project_dna: Optional[str],
        task_description: str,
        hyde_query: str,
        project_id: int
    ) -> Dict[str, Any]:
        """
        Assemble the final context package with intelligent formatting and token management.
        
        Args:
            nodes: Retrieved context nodes with scores
            project_dna: Project DNA summary
            task_description: Original task description
            hyde_query: Generated HyDE query
            project_id: Project identifier
            
        Returns:
            Formatted context package dictionary
        """
        logger.debug("Assembling context package")
        
        # Initialize context components
        context_parts = []
        token_count = 0
        
        # Add Project DNA if available and within token limit
        if project_dna:
            dna_tokens = self.estimate_tokens(project_dna)
            if token_count + dna_tokens < self.max_context_tokens * 0.3:  # Reserve 30% for DNA
                context_parts.append({
                    'type': 'project_dna',
                    'title': 'PROJECT DNA SUMMARY',
                    'content': project_dna,
                    'tokens': dna_tokens,
                    'priority': 1
                })
                token_count += dna_tokens
                logger.debug(f"Added DNA to context ({dna_tokens} tokens)")
        
        # Add retrieved code chunks
        chunks_added = 0
        remaining_tokens = self.max_context_tokens - token_count - 500  # Reserve for formatting
        
        for node_with_score in nodes:
            node = node_with_score.node
            score = node_with_score.score
            
            # Format chunk with metadata
            chunk_content = self.format_code_chunk(node, score)
            chunk_tokens = self.estimate_tokens(chunk_content)
            
            # Check token limit
            if token_count + chunk_tokens > remaining_tokens:
                logger.debug(f"Token limit reached, stopping at {chunks_added} chunks")
                break
            
            context_parts.append({
                'type': 'code_chunk',
                'title': f"RELEVANT CODE CHUNK {chunks_added + 1}",
                'content': chunk_content,
                'tokens': chunk_tokens,
                'score': score,
                'priority': 2
            })
            
            token_count += chunk_tokens
            chunks_added += 1
        
        # Sort context parts by priority and score
        context_parts.sort(key=lambda x: (x['priority'], -x.get('score', 0)))
        
        # Generate final context string
        context_sections = []
        for part in context_parts:
            section = f"=== {part['title']} ===\\n{part['content']}\\n"
            context_sections.append(section)
        
        final_context = "\\n".join(context_sections)
        
        # Create comprehensive context package
        return {
            'context': final_context,
            'metadata': {
                'project_id': project_id,
                'task_description': task_description,
                'hyde_query': hyde_query,
                'total_tokens': token_count,
                'max_tokens': self.max_context_tokens,
                'context_parts': len(context_parts),
                'chunks_included': chunks_added,
                'dna_included': bool(project_dna),
                'timestamp': datetime.now(timezone.utc).isoformat(),
            },
            'components': {
                'project_dna': project_dna,
                'code_chunks': [
                    {
                        'content': part['content'],
                        'score': part.get('score'),
                        'tokens': part['tokens']
                    }
                    for part in context_parts if part['type'] == 'code_chunk'
                ]
            }
        }
    
    def format_code_chunk(self, node: TextNode, score: float) -> str:
        """
        Format a code chunk with relevant metadata.
        
        Args:
            node: Text node containing code chunk
            score: Similarity score
            
        Returns:
            Formatted code chunk string
        """
        metadata = node.metadata or {}
        
        # Extract key metadata
        file_path = metadata.get('relative_path', metadata.get('file_path', 'unknown'))
        language = metadata.get('language', 'unknown')
        chunk_type = metadata.get('chunk_type', 'code')
        chunk_name = metadata.get('chunk_name', 'unnamed')
        start_line = metadata.get('start_line')
        
        # Create header
        header_parts = [f"File: {file_path}"]
        if language != 'unknown':
            header_parts.append(f"Language: {language}")
        if chunk_type and chunk_name:
            header_parts.append(f"{chunk_type}: {chunk_name}")
        if start_line:
            header_parts.append(f"Line: {start_line}")
        header_parts.append(f"Similarity: {score:.3f}")
        
        header = " | ".join(header_parts)
        
        # Format content
        content = node.text.strip()
        
        return f"{header}\\n\\n```{language}\\n{content}\\n```"
    
    def estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token ≈ 4 characters
        # This is a simplification but works for most use cases
        return max(1, len(text) // 4)
    
    def truncate_to_token_limit(self, text: str, max_tokens: int) -> str:
        """
        Truncate text to stay within token limit.
        
        Args:
            text: Input text
            max_tokens: Maximum allowed tokens
            
        Returns:
            Truncated text
        """
        estimated_tokens = self.estimate_tokens(text)
        if estimated_tokens <= max_tokens:
            return text
        
        # Calculate truncation ratio
        ratio = max_tokens / estimated_tokens
        target_chars = int(len(text) * ratio * 0.9)  # 90% to be safe
        
        truncated = text[:target_chars]
        return truncated + "\\n\\n[... content truncated to stay within token limit ...]"


# Global context retriever instance
context_retriever = ContextRetriever()


# Convenience functions for external use
async def retrieve_project_context(
    project_id: int,
    task_description: str,
    similarity_top_k: int = 8,
    include_dna: bool = True,
    use_hyde: Optional[bool] = None,
    max_context_tokens: int = 8000,
    tracker=None  # Optional ContextUsageTracker
) -> Dict[str, Any]:
    """
    Retrieve contextually relevant information for a project task.

    This function combines Project DNA and conditional HyDE to provide intelligent
    context retrieval that understands the project's unique structure.

    Args:
        project_id: Project identifier
        task_description: User's task or question
        similarity_top_k: Number of similar chunks to retrieve
        include_dna: Whether to include DNA in final context
        use_hyde: Whether to use HyDE (None=auto-detect, True=force, False=disable)
        max_context_tokens: Maximum tokens in context package

    Returns:
        Context package with retrieved information

    Raises:
        ValueError: If project not ready for retrieval
        RuntimeError: If retrieval fails
    """
    retriever = ContextRetriever(max_context_tokens=max_context_tokens)
    return await retriever.retrieve_context(
        project_id=project_id,
        task_description=task_description,
        similarity_top_k=similarity_top_k,
        include_dna_in_context=include_dna,
        use_hyde=use_hyde,
        tracker=tracker
    )


async def get_project_context_summary(project_id: int) -> Dict[str, Any]:
    """
    Get a summary of available context for a project.
    
    Args:
        project_id: Project identifier
        
    Returns:
        Dictionary with context availability information
    """
    try:
        # Get project and indexing status
        async with SessionLocal() as session:
            project = await session.get(Project, project_id)
            if not project:
                raise ValueError(f"Project {project_id} not found")
            
            # Get DNA availability
            retriever = ContextRetriever()
            dna = await retriever.get_project_dna(project_id)
            
            # Extract last indexed timestamp from configuration
            last_indexed_at = None
            if project.configuration and "last_indexed_at" in project.configuration:
                last_indexed_at = project.configuration["last_indexed_at"]
            
            return {
                'project_id': project_id,
                'indexing_status': project.indexing_status.value if project.indexing_status else 'not_indexed',
                'indexed_nodes_count': project.indexed_nodes_count or 0,
                'last_indexed_at': last_indexed_at,
                'dna_available': bool(dna),
                'dna_length': len(dna) if dna else 0,
                'ready_for_retrieval': project.indexing_status == IndexingStatus.READY,
                'embedding_dimension': 384,  # Default embedding dimension
            }
        
    except Exception as e:
        logger.error(f"Failed to get context summary for project {project_id}: {e}")
        return {
            'project_id': project_id,
            'error': str(e),
            'ready_for_retrieval': False,
        }


# =============================================================================
# RLM-RAG Hybrid Retriever
# =============================================================================

class RLMRAGHybridRetriever:
    """
    RLM + RAG Hybrid for maximum scalability and dynamic context refinement.
    
    This class combines:
    1. Vector search (RAG) for initial context filtering
    2. RLM for recursive analysis of retrieved chunks
    3. Dynamic RAG refinement (agent can trigger new searches mid-analysis)
    
    Features:
    - Handles unlimited context sizes
    - Pre-filters with semantic search
    - Enables iterative search refinement
    - Supports HyDE + DNA augmentation
    - Provides audit trails
    """
    
    def __init__(self, max_context_tokens: int = 50000):
        """Initialize hybrid retriever."""
        self.context_retriever = ContextRetriever(max_context_tokens=max_context_tokens)
        self.max_context_tokens = max_context_tokens
        logger.info("Initialized RLM-RAG Hybrid Retriever")
    
    async def retrieve_and_analyze(
        self,
        query: str,
        project_id: int,
        rlm_config: Dict[str, Any],
        workspace: Path
    ) -> Dict[str, Any]:
        """
        Execute hybrid RAG + RLM workflow.
        
        Flow:
        1. Initial RAG retrieval (top-k chunks)
        2. Load chunks into RLM REPL
        3. Register dynamic refinement function
        4. RLM analyzes with ability to trigger new searches
        5. Return synthesized result with audit trail
        
        Args:
            query: User query
            project_id: Project ID
            rlm_config: RLM configuration dict
            workspace: Workspace directory for RLM
        
        Returns:
            Dict with analysis result and audit trail
        """
        from services.rlm_repl_environment import RLMREPLEnvironment
        from core.agents.factory import AgentFactory
        
        logger.info(f"Starting RLM-RAG hybrid retrieval for project {project_id}")
        start_time = datetime.now(timezone.utc)
        
        # Track search history for audit trail
        search_history = []
        
        # 1. Initial RAG retrieval
        top_k = rlm_config.get("rag_top_k", 50)
        logger.info(f"Initial RAG retrieval: top_k={top_k}")
        
        initial_context = await self.context_retriever.retrieve_context(
            project_id=project_id,
            task_description=query,
            similarity_top_k=top_k,
            include_dna_in_context=rlm_config.get("enable_dna_augmentation", True),
            use_hyde=rlm_config.get("enable_hyde", True)
        )
        
        search_history.append({
            'query': query,
            'method': 'initial_retrieval',
            'results_count': initial_context['metadata'].get('nodes_retrieved', 0),
            'timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        # 2. Create RLM environment
        workspace.mkdir(parents=True, exist_ok=True)
        
        repl = RLMREPLEnvironment(
            workspace=workspace,
            max_recursion_depth=rlm_config.get("max_recursion_depth", 2),
            current_depth=0
        )
        
        # 3. Load chunks into REPL
        chunks_text = [chunk['content'] for chunk in initial_context.get('code_chunks', [])]
        chunks_metadata = [chunk['metadata'] for chunk in initial_context.get('code_chunks', [])]
        
        repl.set_context("chunks", chunks_text)
        repl.set_context("chunks_metadata", chunks_metadata)
        repl.set_context("query", query)
        
        # Load DNA if available
        if 'dna_summary' in initial_context:
            repl.set_context("project_dna", initial_context['dna_summary'])
        
        # 4. Register dynamic RAG refinement function
        async def refine_search(refined_query: str, additional_top_k: int = 20) -> Dict[str, Any]:
            """
            Allow RLM to trigger new RAG queries for context refinement.
            
            This enables dynamic, iterative search where the agent can:
            - Realize initial context is insufficient
            - Generate more specific queries
            - Retrieve additional relevant chunks
            """
            logger.info(f"Dynamic RAG refinement triggered: '{refined_query}'")
            
            refined_context = await self.context_retriever.retrieve_context(
                project_id=project_id,
                task_description=refined_query,
                similarity_top_k=additional_top_k,
                include_dna_in_context=False,  # DNA already loaded
                use_hyde=False  # Direct search for refinement
            )
            
            search_history.append({
                'query': refined_query,
                'method': 'dynamic_refinement',
                'results_count': refined_context['metadata'].get('nodes_retrieved', 0),
                'timestamp': datetime.now(timezone.utc).isoformat()
            })
            
            # Return refined chunks
            refined_chunks = [chunk['content'] for chunk in refined_context.get('code_chunks', [])]
            return {
                'chunks': refined_chunks,
                'count': len(refined_chunks)
            }
        
        # Register refinement function in REPL
        repl.register_dynamic_function("refine_search", refine_search)
        
        logger.info("Registered dynamic RAG refinement function")
        
        # 5. Execute RLM analysis
        # Note: This would call AgentFactory.create_rlm_agent()
        # For now, placeholder
        try:
            # TODO: Implement full RLM execution via AgentFactory
            result = {
                'success': True,
                'output': '[RLM-RAG PLACEHOLDER] Full execution pending AgentFactory.create_rlm_agent()',
                'audit_trail': repl.generate_audit_trail(),
                'search_history': search_history,
                'initial_chunks': len(chunks_text),
                'execution_time': (datetime.now(timezone.utc) - start_time).total_seconds()
            }
            
            logger.info(
                f"RLM-RAG hybrid completed: "
                f"{len(search_history)} searches, {result['initial_chunks']} initial chunks"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"RLM-RAG hybrid failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'audit_trail': repl.generate_audit_trail(),
                'search_history': search_history
            }
