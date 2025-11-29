"""Tests for retry_utils module."""

import pytest
from unittest.mock import MagicMock, patch
import time

# Import after setting up path
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from retry_utils import retry_on_failure, retry_call


class TestRetryOnFailure:
    """Tests for the retry_on_failure decorator."""
    
    def test_success_no_retry(self):
        """Test successful call without retries."""
        call_count = 0
        
        @retry_on_failure(max_retries=3)
        def succeed():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = succeed()
        assert result == "success"
        assert call_count == 1
    
    def test_retry_then_success(self):
        """Test retry after failure then success."""
        call_count = 0
        
        @retry_on_failure(max_retries=3, initial_delay=0.01)
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Failed")
            return "success"
        
        result = fail_then_succeed()
        assert result == "success"
        assert call_count == 3
    
    def test_all_retries_exhausted(self):
        """Test all retries exhausted raises exception."""
        call_count = 0
        
        @retry_on_failure(max_retries=2, initial_delay=0.01)
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError, match="Always fails"):
            always_fail()
        
        assert call_count == 3  # initial + 2 retries
    
    def test_specific_exception_type(self):
        """Test only catches specified exception types."""
        call_count = 0
        
        @retry_on_failure(max_retries=3, initial_delay=0.01, exceptions=(ConnectionError,))
        def raise_different_error():
            nonlocal call_count
            call_count += 1
            raise ValueError("Different error")
        
        with pytest.raises(ValueError):
            raise_different_error()
        
        # Should not retry for ValueError since we only specified ConnectionError
        assert call_count == 1


class TestRetryCall:
    """Tests for the retry_call function."""
    
    def test_success_no_retry(self):
        """Test successful call without retries."""
        mock_func = MagicMock(return_value="success")
        
        result = retry_call(mock_func, "arg1", kwarg1="value1")
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="value1")
    
    def test_retry_then_success(self):
        """Test retry after failure then success."""
        mock_func = MagicMock(side_effect=[ConnectionError(), ConnectionError(), "success"])
        
        result = retry_call(mock_func, max_retries=3, initial_delay=0.01)
        
        assert result == "success"
        assert mock_func.call_count == 3
    
    def test_all_retries_exhausted(self):
        """Test all retries exhausted raises exception."""
        mock_func = MagicMock(side_effect=TimeoutError("Timeout"))
        
        with pytest.raises(TimeoutError, match="Timeout"):
            retry_call(mock_func, max_retries=2, initial_delay=0.01)
        
        assert mock_func.call_count == 3  # initial + 2 retries
    
    def test_backoff_factor(self):
        """Test exponential backoff is applied."""
        mock_func = MagicMock(side_effect=[ConnectionError(), ConnectionError(), "success"])
        
        with patch('retry_utils.time.sleep') as mock_sleep:
            result = retry_call(
                mock_func,
                max_retries=3,
                initial_delay=1.0,
                backoff_factor=2.0,
            )
        
        assert result == "success"
        # Should have slept with delays 1.0 and 2.0
        assert mock_sleep.call_count == 2
        mock_sleep.assert_any_call(1.0)
        mock_sleep.assert_any_call(2.0)
