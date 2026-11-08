#!/usr/bin/env python3
"""
Tests for threading and UI components of realtime search
These tests are designed to avoid infinite loops by using proper mocking
"""

import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path before local imports
sys.path.append(str(Path(__file__).parent.parent))

# Local imports after sys.path modification
from realtime_search import RealTimeSearch  # noqa: E402


class TestRealTimeSearchThreading(unittest.TestCase):
    """Test threading behavior without hanging"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_searcher = Mock()
        self.mock_extractor = Mock()
        self.rts = RealTimeSearch(self.mock_searcher, self.mock_extractor)

    def test_process_search_request_no_search(self):
        """Test when no search is pending"""
        self.rts.state.is_searching = False

        result = self.rts._process_search_request()

        self.assertFalse(result)
        self.mock_searcher.search.assert_not_called()

    def test_process_search_request_debounce(self):
        """Test debounce prevents immediate search"""
        self.rts.state.is_searching = True
        self.rts.state.query = "test"
        self.rts.state.last_update = time.time()  # Just updated

        result = self.rts._process_search_request()

        self.assertFalse(result)  # Should not process due to debounce
        self.mock_searcher.search.assert_not_called()

    def test_process_search_request_empty_query(self):
        """Test empty query clears results"""
        self.rts.state.is_searching = True
        self.rts.state.query = ""
        self.rts.state.last_update = time.time() - 1  # Old enough
        self.rts.state.results = [Mock()]  # Has existing results

        result = self.rts._process_search_request()

        self.assertTrue(result)
        self.assertEqual(self.rts.state.results, [])
        self.mock_searcher.search.assert_not_called()

    def test_process_search_request_cached(self):
        """Test cached results are used"""
        cached_results = [Mock()]
        self.rts.results_cache["cached"] = cached_results
        self.rts.state.is_searching = True
        self.rts.state.query = "cached"
        self.rts.state.last_update = time.time() - 1

        result = self.rts._process_search_request()

        self.assertTrue(result)
        self.assertEqual(self.rts.state.results, cached_results)
        self.mock_searcher.search.assert_not_called()

    def test_process_search_request_new_search(self):
        """Test new search is performed"""
        search_results = [Mock()]
        self.mock_searcher.search.return_value = search_results
        self.rts.state.is_searching = True
        self.rts.state.query = "new query"
        self.rts.state.last_update = time.time() - 1

        result = self.rts._process_search_request()

        self.assertTrue(result)
        self.assertEqual(self.rts.state.results, search_results)
        self.mock_searcher.search.assert_called_once_with(
            query="new query", mode="smart", max_results=20, case_sensitive=False
        )
        self.assertIn("new query", self.rts.results_cache)

    def test_process_search_request_error(self):
        """Test search error handling"""
        self.mock_searcher.search.side_effect = Exception("Search failed")
        self.rts.state.is_searching = True
        self.rts.state.query = "error query"
        self.rts.state.last_update = time.time() - 1

        result = self.rts._process_search_request()

        self.assertTrue(result)
        self.assertEqual(self.rts.state.results, [])

    def test_thread_lifecycle(self):
        """Test thread starts and stops properly"""
        # Start thread
        thread = threading.Thread(target=self.rts.search_worker, daemon=True)
        thread.start()

        # Verify thread is running
        self.assertTrue(thread.is_alive())

        # stop() signals the worker and joins it
        self.rts.search_thread = thread
        self.rts.stop()
        self.assertFalse(thread.is_alive())


class TestRealTimeSearchUI(unittest.TestCase):
    """Test UI components with proper mocking"""

    def setUp(self):
        """Set up test fixtures"""
        self.mock_searcher = Mock()
        self.mock_extractor = Mock()
        # RealTimeSearch builds its TerminalDisplay in __init__, so patch the
        # class before constructing it
        patcher = patch("realtime_search.TerminalDisplay")
        mock_display_class = patcher.start()
        self.addCleanup(patcher.stop)
        self.rts = RealTimeSearch(self.mock_searcher, self.mock_extractor)
        self.mock_display = mock_display_class.return_value
        self.assertIs(self.rts.display, self.mock_display)

    @patch("realtime_search.threading.Thread")
    @patch("realtime_search.KeyboardHandler")
    def test_run_exit_key(self, mock_keyboard_class, mock_thread_class):
        """Test run exits on ESC key"""
        # Set up mocks
        mock_keyboard = Mock()
        mock_keyboard_class.return_value.__enter__.return_value = mock_keyboard
        mock_keyboard.get_key.side_effect = ["a", "b", "c", "ESC"]  # Type abc then ESC

        # Mock thread to prevent actual thread start
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        # Run should exit on ESC
        result = self.rts.run()

        self.assertIsNone(result)
        self.assertEqual(self.rts.state.query, "abc")
        mock_thread.start.assert_called_once()
        self.mock_display.clear_screen.assert_called()

    @patch("realtime_search.threading.Thread")
    @patch("realtime_search.KeyboardHandler")
    def test_run_select_result(self, mock_keyboard_class, mock_thread_class):
        """Test run returns selected file path"""
        mock_keyboard = Mock()
        mock_keyboard_class.return_value.__enter__.return_value = mock_keyboard

        # Set up results
        test_path = Path("/test/file.jsonl")
        mock_result = Mock(file_path=test_path)
        self.rts.state.results = [mock_result]
        self.rts.state.selected_index = 0

        # Simulate typing and selecting
        mock_keyboard.get_key.side_effect = ["t", "e", "s", "t", "ENTER"]

        # Mock thread
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        # Run should return selected path
        result = self.rts.run()

        self.assertEqual(result, test_path)
        self.assertEqual(self.rts.state.query, "test")
        # Each typed key triggered a redraw of the results
        self.assertGreaterEqual(self.mock_display.draw_results.call_count, 5)

    @patch("realtime_search.threading.Thread")
    @patch("realtime_search.KeyboardHandler")
    def test_run_keyboard_interrupt(self, mock_keyboard_class, mock_thread_class):
        """Test run handles KeyboardInterrupt"""
        # Set up mocks
        mock_keyboard = Mock()
        mock_keyboard_class.return_value.__enter__.return_value = mock_keyboard
        mock_keyboard.get_key.side_effect = KeyboardInterrupt()

        # Mock thread
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        # Should handle interrupt gracefully
        result = self.rts.run()

        self.assertIsNone(result)
        self.mock_display.clear_screen.assert_called()
        mock_thread.join.assert_called_once()

    @patch("realtime_search.threading.Thread")
    @patch("realtime_search.KeyboardHandler")
    def test_run_exception_cleanup(self, mock_keyboard_class, mock_thread_class):
        """Test run cleans up on exception"""
        # Set up mocks
        mock_keyboard = Mock()
        mock_keyboard_class.return_value.__enter__.return_value = mock_keyboard
        mock_keyboard.get_key.side_effect = Exception("Test error")

        # Mock thread
        mock_thread = Mock()
        mock_thread_class.return_value = mock_thread

        # Non-KeyboardInterrupt errors propagate out of run()...
        with self.assertRaisesRegex(Exception, "Test error"):
            self.rts.run()

        # ...but the finally-block cleanup still happens
        self.assertEqual(self.mock_display.clear_screen.call_count, 2)
        self.assertTrue(self.rts.stop_event.is_set())
        mock_thread.join.assert_called_once()
        mock_keyboard_class.return_value.__exit__.assert_called_once()


if __name__ == "__main__":
    unittest.main()
