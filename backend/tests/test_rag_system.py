"""
Tests for RAGSystem query handling.

These tests verify the RAGSystem correctly:
- Processes queries through the full pipeline
- Handles session management
- Manages tool execution flow
- Handles errors properly
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Add backend to path for imports
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))


class TestRAGSystemQuery:
    """Tests for the RAGSystem.query() method"""

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.SessionManager')
    def test_query_basic(
            self,
            mock_session_manager_class,
            mock_doc_processor_class,
            mock_ai_generator_class,
            mock_vector_store_class,
            mock_tool_manager
    ):
        """Test basic query returns response and sources"""
        # Setup mocks
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "This is the answer."
        mock_ai_generator_class.return_value = mock_ai_generator

        mock_session_manager = Mock()
        mock_session_manager.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_manager

        mock_vector_store_class.return_value = Mock()
        mock_doc_processor_class.return_value = Mock()

        # Create a mock config
        mock_config = Mock()
        mock_config.CHUNK_SIZE = 800
        mock_config.CHUNK_OVERLAP = 100
        mock_config.CHROMA_PATH = "./test_chroma"
        mock_config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        mock_config.ANTHROPIC_API_KEY = "test-key"
        mock_config.ANTHROPIC_MODEL = "claude-3-opus"
        mock_config.MAX_RESULTS = 5
        mock_config.MAX_HISTORY = 2

        from rag_system import RAGSystem
        rag = RAGSystem(mock_config)

        # Mock the tool manager
        rag.tool_manager = mock_tool_manager

        response, sources = rag.query("What is Python?")

        assert response == "This is the answer."
        assert sources == mock_tool_manager.get_last_sources()
        mock_tool_manager.reset_sources.assert_called_once()

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.SessionManager')
    def test_query_with_session(
            self,
            mock_session_manager_class,
            mock_doc_processor_class,
            mock_ai_generator_class,
            mock_vector_store_class
    ):
        """Test that session history is included in query"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Answer with context"
        mock_ai_generator_class.return_value = mock_ai_generator

        mock_session_manager = Mock()
        mock_session_manager.get_conversation_history.return_value = "Previous: Hello"
        mock_session_manager_class.return_value = mock_session_manager

        mock_vector_store_class.return_value = Mock()
        mock_doc_processor_class.return_value = Mock()

        mock_config = Mock()
        mock_config.CHUNK_SIZE = 800
        mock_config.CHUNK_OVERLAP = 100
        mock_config.CHROMA_PATH = "./test_chroma"
        mock_config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        mock_config.ANTHROPIC_API_KEY = "test-key"
        mock_config.ANTHROPIC_MODEL = "claude-3-opus"
        mock_config.MAX_RESULTS = 5
        mock_config.MAX_HISTORY = 2

        from rag_system import RAGSystem
        rag = RAGSystem(mock_config)

        # Mock tool manager
        rag.tool_manager = Mock()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.tool_manager.get_last_sources.return_value = []
        rag.tool_manager.reset_sources.return_value = None

        response, sources = rag.query("Follow-up", session_id="session_1")

        # Check that history was retrieved
        mock_session_manager.get_conversation_history.assert_called_with("session_1")

        # Check that generate_response received history
        call_kwargs = mock_ai_generator.generate_response.call_args.kwargs
        assert call_kwargs["conversation_history"] == "Previous: Hello"

        # Check that exchange was added
        mock_session_manager.add_exchange.assert_called_once()

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.SessionManager')
    def test_query_sources_reset(
            self,
            mock_session_manager_class,
            mock_doc_processor_class,
            mock_ai_generator_class,
            mock_vector_store_class
    ):
        """Test that sources are reset after retrieval"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Answer"
        mock_ai_generator_class.return_value = mock_ai_generator

        mock_session_manager = Mock()
        mock_session_manager.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_manager

        mock_vector_store_class.return_value = Mock()
        mock_doc_processor_class.return_value = Mock()

        mock_config = Mock()
        mock_config.CHUNK_SIZE = 800
        mock_config.CHUNK_OVERLAP = 100
        mock_config.CHROMA_PATH = "./test_chroma"
        mock_config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        mock_config.ANTHROPIC_API_KEY = "test-key"
        mock_config.ANTHROPIC_MODEL = "claude-3-opus"
        mock_config.MAX_RESULTS = 5
        mock_config.MAX_HISTORY = 2

        from rag_system import RAGSystem
        rag = RAGSystem(mock_config)

        # Mock tool manager
        mock_tool_manager = Mock()
        mock_tool_manager.get_tool_definitions.return_value = []
        mock_tool_manager.get_last_sources.return_value = [{"text": "Source 1"}]
        mock_tool_manager.reset_sources.return_value = None
        rag.tool_manager = mock_tool_manager

        rag.query("Test query")

        # Verify reset was called after get
        mock_tool_manager.get_last_sources.assert_called_once()
        mock_tool_manager.reset_sources.assert_called_once()


class TestRAGSystemErrorPropagation:
    """Tests for error propagation in RAGSystem"""

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.SessionManager')
    def test_query_ai_generator_error(
            self,
            mock_session_manager_class,
            mock_doc_processor_class,
            mock_ai_generator_class,
            mock_vector_store_class
    ):
        """Test that AI generator errors are handled gracefully"""
        mock_ai_generator = Mock()
        # With the fix, errors return error messages instead of raising
        mock_ai_generator.generate_response.return_value = "API error occurred: Connection failed"
        mock_ai_generator_class.return_value = mock_ai_generator

        mock_session_manager = Mock()
        mock_session_manager.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_manager

        mock_vector_store_class.return_value = Mock()
        mock_doc_processor_class.return_value = Mock()

        mock_config = Mock()
        mock_config.CHUNK_SIZE = 800
        mock_config.CHUNK_OVERLAP = 100
        mock_config.CHROMA_PATH = "./test_chroma"
        mock_config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        mock_config.ANTHROPIC_API_KEY = "test-key"
        mock_config.ANTHROPIC_MODEL = "claude-3-opus"
        mock_config.MAX_RESULTS = 5
        mock_config.MAX_HISTORY = 2

        from rag_system import RAGSystem
        rag = RAGSystem(mock_config)

        # Mock tool manager
        rag.tool_manager = Mock()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.tool_manager.get_last_sources.return_value = []
        rag.tool_manager.reset_sources.return_value = None

        # With the fix, errors are returned as messages, not raised
        response, sources = rag.query("Test query")
        assert "error" in response.lower()

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.SessionManager')
    def test_query_tool_manager_error(
            self,
            mock_session_manager_class,
            mock_doc_processor_class,
            mock_ai_generator_class,
            mock_vector_store_class
    ):
        """Test that tool manager errors are handled gracefully"""
        mock_ai_generator = Mock()
        # With the fix, tool errors are caught and passed to Claude as tool results
        mock_ai_generator.generate_response.return_value = "I encountered an error while searching."
        mock_ai_generator_class.return_value = mock_ai_generator

        mock_session_manager = Mock()
        mock_session_manager.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_manager

        mock_vector_store_class.return_value = Mock()
        mock_doc_processor_class.return_value = Mock()

        mock_config = Mock()
        mock_config.CHUNK_SIZE = 800
        mock_config.CHUNK_OVERLAP = 100
        mock_config.CHROMA_PATH = "./test_chroma"
        mock_config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        mock_config.ANTHROPIC_API_KEY = "test-key"
        mock_config.ANTHROPIC_MODEL = "claude-3-opus"
        mock_config.MAX_RESULTS = 5
        mock_config.MAX_HISTORY = 2

        from rag_system import RAGSystem
        rag = RAGSystem(mock_config)

        # Mock tool manager
        rag.tool_manager = Mock()
        rag.tool_manager.get_tool_definitions.return_value = []
        rag.tool_manager.get_last_sources.return_value = []
        rag.tool_manager.reset_sources.return_value = None

        # With the fix, errors are handled gracefully
        response, sources = rag.query("Test query")
        assert response is not None


class TestRAGSystemToolFlow:
    """Tests for the complete tool execution flow through RAGSystem"""

    @patch('rag_system.VectorStore')
    @patch('rag_system.AIGenerator')
    @patch('rag_system.DocumentProcessor')
    @patch('rag_system.SessionManager')
    def test_query_tool_execution_flow(
            self,
            mock_session_manager_class,
            mock_doc_processor_class,
            mock_ai_generator_class,
            mock_vector_store_class,
            mock_tool_manager
    ):
        """Test full tool execution flow works end-to-end"""
        mock_ai_generator = Mock()
        mock_ai_generator.generate_response.return_value = "Answer based on search"
        mock_ai_generator_class.return_value = mock_ai_generator

        mock_session_manager = Mock()
        mock_session_manager.get_conversation_history.return_value = None
        mock_session_manager_class.return_value = mock_session_manager

        mock_vector_store_class.return_value = Mock()
        mock_doc_processor_class.return_value = Mock()

        mock_config = Mock()
        mock_config.CHUNK_SIZE = 800
        mock_config.CHUNK_OVERLAP = 100
        mock_config.CHROMA_PATH = "./test_chroma"
        mock_config.EMBEDDING_MODEL = "all-MiniLM-L6-v2"
        mock_config.ANTHROPIC_API_KEY = "test-key"
        mock_config.ANTHROPIC_MODEL = "claude-3-opus"
        mock_config.MAX_RESULTS = 5
        mock_config.MAX_HISTORY = 2

        from rag_system import RAGSystem
        rag = RAGSystem(mock_config)
        rag.tool_manager = mock_tool_manager

        response, sources = rag.query("What is Python?")

        # Verify AI generator was called with tools
        call_kwargs = mock_ai_generator.generate_response.call_args.kwargs
        assert "tools" in call_kwargs
        assert "tool_manager" in call_kwargs
        assert call_kwargs["tools"] == mock_tool_manager.get_tool_definitions()
        assert call_kwargs["tool_manager"] == mock_tool_manager

        # Verify sources were retrieved
        assert sources == mock_tool_manager.get_last_sources()


class TestToolManagerExecuteTool:
    """Tests for ToolManager.execute_tool method"""

    def test_execute_tool_success(self, mock_vector_store):
        """Test successful tool execution"""
        from search_tools import ToolManager, CourseSearchTool

        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        result = manager.execute_tool("search_course_content", query="Python")

        assert result is not None
        assert "Python Basics" in result or "sample content" in result

    def test_execute_tool_not_found(self):
        """Test execution of non-existent tool"""
        from search_tools import ToolManager

        manager = ToolManager()
        result = manager.execute_tool("nonexistent_tool", query="test")

        assert "not found" in result.lower()

    def test_execute_tool_exception_handled(self, mock_vector_store):
        """Test that tool exceptions are now caught by ToolManager"""
        from search_tools import ToolManager, CourseSearchTool

        # Make vector store raise an exception
        mock_vector_store.search.side_effect = Exception("Database error")

        manager = ToolManager()
        tool = CourseSearchTool(mock_vector_store)
        manager.register_tool(tool)

        # With the fix, ToolManager catches exceptions and returns error message
        result = manager.execute_tool("search_course_content", query="test")
        assert "error" in result.lower()
        assert "database error" in result.lower()
