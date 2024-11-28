"""Tests for database decorators."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from core.db.base import BaseQueries
from core.db.decorators import with_queries
from sqlalchemy.ext.asyncio import AsyncSession


class _TestQueries(BaseQueries):
    """Test query class."""

    def __init__(self, session: AsyncSession):
        super().__init__(session)
        self.test_method = AsyncMock()
        self.test_method.return_value = None


@pytest.fixture
async def mock_session():
    """Create a mock session."""
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    yield session


@pytest.fixture
def mock_get_db(mock_session):
    """Create a mock get_db function."""

    @asynccontextmanager
    async def _mock_get_db():
        yield mock_session

    return _mock_get_db


@pytest.mark.asyncio
class TestWithQueries:
    """Test with_queries decorator."""

    async def test_class_method_decoration(self, mock_get_db, mock_session):
        """Test decorator on class method."""
        with patch("core.db.decorators.get_db", mock_get_db):
            test_value = "test"

            class TestClass:
                @with_queries(_TestQueries)
                async def test_method(self, queries: _TestQueries, value: str) -> str:
                    await queries.test_method(value)
                    return value

            test_obj = TestClass()
            result = await test_obj.test_method(value=test_value)
            assert result == test_value

    async def test_function_decoration(self, mock_get_db, mock_session):
        """Test decorator on standalone function."""
        with patch("core.db.decorators.get_db", mock_get_db):
            test_value = "test"

            @with_queries(_TestQueries)
            async def test_function(queries: _TestQueries, value: str) -> str:
                await queries.test_method(value)
                return value

            result = await test_function(value=test_value)
            assert result == test_value

    async def test_raw_session_function(self, mock_get_db, mock_session):
        """Test decorator with raw session."""
        with patch("core.db.decorators.get_db", mock_get_db):
            test_value = "test"

            @with_queries
            async def test_raw_session(session: AsyncSession, value: str) -> str:
                return value

            result = await test_raw_session(session=mock_session, value=test_value)
            assert result == test_value

    async def test_session_management(self, mock_session):
        """Test session is properly managed."""
        test_value = "test"

        @with_queries(_TestQueries)
        async def test_function(queries: _TestQueries, value: str) -> str:
            await queries.test_method(value)
            return value

        result = await test_function(value=test_value, session=mock_session)
        assert result == test_value
        # Session should not be committed when passed externally
        assert not mock_session.commit.called

    async def test_auto_session_management(self, mock_get_db, mock_session):
        """Test automatic session management."""
        with patch("core.db.decorators.get_db", mock_get_db):
            test_value = "test"

            @with_queries(_TestQueries)
            async def test_function(queries: _TestQueries, value: str) -> str:
                await queries.test_method(value)
                return value

            result = await test_function(value=test_value)
            assert result == test_value
            # Session should be committed when created internally
            assert mock_session.commit.called

    async def test_exception_handling(self, mock_get_db, mock_session):
        """Test exception handling in decorated function."""
        test_value = "test"
        test_exception = ValueError("Test error")

        # Make the test method raise an exception
        mock_session.commit.side_effect = test_exception

        @with_queries(_TestQueries)
        async def test_function(queries: _TestQueries, value: str) -> str:
            await queries.test_method(value)
            return value

        with (
            patch("core.db.decorators.get_db", mock_get_db),
            pytest.raises(ValueError, match="Test error"),
        ):
            await test_function(value=test_value)
            # Session should be rolled back on error
            assert mock_session.rollback.called
