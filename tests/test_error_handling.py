#!/usr/bin/env python3
"""
Error handling and edge case tests for meaningful coverage
"""

import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

# Add parent directory to path before local imports
sys.path.append(str(Path(__file__).parent.parent))

# Local imports after sys.path modification
from extract_claude_logs import (ClaudeConversationExtractor,  # noqa: E402
                                 launch_interactive, main)


def _fake_search_module(searcher):
    """Build a stand-in search_conversations module returning ``searcher``."""
    return Mock(ConversationSearcher=Mock(return_value=searcher))


class TestErrorHandling(unittest.TestCase):
    """Test error handling and edge cases"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_fallback_all_dirs_fail(self):
        """Test init when all directory creation attempts fail"""
        with patch("pathlib.Path.mkdir", side_effect=Exception("Permission denied")):
            with patch("pathlib.Path.touch", side_effect=Exception("No write access")):
                with patch("pathlib.Path.cwd", return_value=Path(self.temp_dir)):
                    with patch("builtins.print") as mock_print:
                        # Should still create extractor, falling back to cwd
                        extractor = ClaudeConversationExtractor(None)
                    self.assertEqual(
                        extractor.output_dir, Path(self.temp_dir) / "claude-logs"
                    )
                    # The failed fallback mkdir is reported, not raised
                    print_calls = [str(call) for call in mock_print.call_args_list]
                    self.assertTrue(
                        any("Could not create" in call for call in print_calls)
                    )

    def test_extract_conversation_permission_error(self):
        """Test extract_conversation with permission error"""
        test_file = Path(self.temp_dir) / "test.jsonl"
        test_file.write_text('{"type": "test"}', encoding="utf-8")

        extractor = ClaudeConversationExtractor(self.temp_dir)

        with patch("builtins.open", side_effect=PermissionError("Access denied")):
            with patch("builtins.print") as mock_print:
                result = extractor.extract_conversation(test_file)
                self.assertEqual(result, [])
                # Should print error message
                mock_print.assert_called()
                args = mock_print.call_args[0][0]
                self.assertIn("Error reading file", args)

    def test_save_as_markdown_write_error(self):
        """Test save_as_markdown with write error"""
        extractor = ClaudeConversationExtractor(self.temp_dir)
        conversation = [{"role": "user", "content": "Test", "timestamp": ""}]

        with patch("builtins.open", side_effect=IOError("Disk full")):
            with patch("builtins.print") as mock_print:
                # Should handle error gracefully and return None
                result = extractor.save_as_markdown(conversation, "test")
        self.assertIsNone(result)
        print_calls = [str(call) for call in mock_print.call_args_list]
        self.assertTrue(any("Disk full" in call for call in print_calls))

    def test_list_recent_sessions_no_sessions_messages(self):
        """Test list_recent_sessions prints correct messages when no sessions"""
        extractor = ClaudeConversationExtractor(self.temp_dir)

        with patch.object(extractor, "find_sessions", return_value=[]):
            with patch("builtins.print") as mock_print:
                _ = extractor.list_recent_sessions()

                # Check all expected messages are printed
                print_calls = [str(call) for call in mock_print.call_args_list]
                self.assertTrue(
                    any("No Claude sessions found" in str(call) for call in print_calls)
                )
                self.assertTrue(
                    any(
                        "Make sure you've used Claude Code" in str(call)
                        for call in print_calls
                    )
                )

    def test_extract_multiple_skip_message(self):
        """Test extract_multiple prints skip message for empty conversations"""
        extractor = ClaudeConversationExtractor(self.temp_dir)
        sessions = [Path("test.jsonl")]

        with patch.object(extractor, "extract_conversation", return_value=[]):
            with patch("builtins.print") as mock_print:
                success, total = extractor.extract_multiple(sessions, [0])

                # Should print skip message
                print_calls = [str(call) for call in mock_print.call_args_list]
                self.assertTrue(
                    any("Skipped session" in str(call) for call in print_calls)
                )
                self.assertEqual(success, 0)
                self.assertEqual(total, 1)


class TestMainFunctionErrorCases(unittest.TestCase):
    """Test main() function error handling"""

    def test_main_invalid_extract_number_handling(self):
        """Test main handles invalid extract numbers gracefully"""
        with patch("sys.argv", ["prog", "--extract", "abc,1,xyz"]):
            with patch.object(
                ClaudeConversationExtractor,
                "find_sessions",
                return_value=[Path("test.jsonl")],
            ):
                with patch.object(
                    ClaudeConversationExtractor,
                    "extract_multiple",
                    return_value=(1, 1),
                ) as mock_extract:
                    with patch("builtins.print") as mock_print:
                        main()

                        # Should skip invalid numbers but process valid ones
                        mock_extract.assert_called_once()
                        args = mock_extract.call_args[0]
                        self.assertEqual(args[1], [0])  # Only valid index

                        # Should print error messages
                        print_calls = [str(call) for call in mock_print.call_args_list]
                        self.assertTrue(
                            any(
                                "Invalid session number: abc" in str(call)
                                for call in print_calls
                            )
                        )
                        self.assertTrue(
                            any(
                                "Invalid session number: xyz" in str(call)
                                for call in print_calls
                            )
                        )

    def test_main_all_with_no_sessions(self):
        """Test --all command with no sessions found"""
        with patch("sys.argv", ["prog", "--all"]):
            with patch.object(
                ClaudeConversationExtractor, "find_sessions", return_value=[]
            ):
                with patch.object(
                    ClaudeConversationExtractor, "extract_multiple", return_value=(0, 0)
                ) as mock_extract:
                    with patch("builtins.print") as mock_print:
                        main()

                        # Should handle empty list gracefully
                        mock_extract.assert_called_once_with(
                            [], [], format="markdown", detailed=False, thinking=False, timestamps=False
                        )
                        print_calls = [str(call) for call in mock_print.call_args_list]
                        self.assertTrue(
                            any("Successfully extracted 0/0" in c for c in print_calls)
                        )

    def test_main_search_import_error(self):
        """Test main propagates a missing search module as ImportError"""
        with patch("sys.argv", ["prog", "--search", "test"]):
            # A None entry in sys.modules makes the import raise ImportError
            with patch.dict("sys.modules", {"search_conversations": None}):
                with patch("builtins.print"):
                    with self.assertRaises(ImportError):
                        main()

    def test_launch_interactive_import_error(self):
        """Test launch_interactive propagates a missing interactive_ui"""
        with patch("sys.argv", ["prog"]):
            with patch.dict("sys.modules", {"interactive_ui": None}):
                with patch("builtins.print"):
                    with self.assertRaises(ImportError):
                        launch_interactive()


class TestSearchFunctionality(unittest.TestCase):
    """Test search functionality in main()"""

    def test_main_search_basic(self):
        """Test basic search functionality"""
        with patch("sys.argv", ["prog", "--search", "test query"]):
            # Mock the entire search flow
            mock_searcher = Mock()
            mock_searcher.search.return_value = [
                Mock(
                    file_path=Path("project") / "test.jsonl",
                    conversation_id="123",
                    matched_content="test match",
                    speaker="human",
                    relevance_score=0.9,
                    timestamp=datetime(2024, 1, 1),
                )
            ]

            with patch.dict(
                "sys.modules", {"search_conversations": _fake_search_module(mock_searcher)}
            ):
                # Skip the "view a conversation?" prompt
                with patch("builtins.input", return_value="") as mock_input:
                    with patch("builtins.print") as mock_print:
                        main()

                        # Should call search in smart mode
                        mock_searcher.search.assert_called_once()
                        call_kwargs = mock_searcher.search.call_args[1]
                        self.assertEqual(call_kwargs["query"], "test query")
                        self.assertEqual(call_kwargs["mode"], "smart")
                        self.assertIsNone(call_kwargs["speaker_filter"])
                        mock_input.assert_called_once()

                        # Should print results
                        print_calls = [str(call) for call in mock_print.call_args_list]
                        self.assertTrue(
                            any("Found 1 matches" in str(call) for call in print_calls)
                        )
                        self.assertTrue(
                            any("test match" in str(call) for call in print_calls)
                        )

    def test_main_search_with_filters(self):
        """Test search with all filter options"""
        with patch(
            "sys.argv",
            [
                "prog",
                "--search-regex",
                "test.*",
                "--search-speaker",
                "human",
                "--search-date-from",
                "2024-01-01",
                "--search-date-to",
                "2024-12-31",
                "--case-sensitive",
            ],
        ):
            mock_searcher = Mock()
            mock_searcher.search.return_value = []

            with patch.dict(
                "sys.modules", {"search_conversations": _fake_search_module(mock_searcher)}
            ):
                with patch("builtins.input") as mock_input:
                    with patch("builtins.print") as mock_print:
                        main()

                        # Verify search was called with correct parameters
                        mock_searcher.search.assert_called_once()
                        call_kwargs = mock_searcher.search.call_args[1]
                        self.assertEqual(call_kwargs["query"], "test.*")
                        self.assertEqual(call_kwargs["mode"], "regex")
                        self.assertEqual(call_kwargs["speaker_filter"], "human")
                        self.assertTrue(call_kwargs["case_sensitive"])
                        self.assertEqual(call_kwargs["date_from"], datetime(2024, 1, 1))
                        self.assertEqual(call_kwargs["date_to"], datetime(2024, 12, 31))

                        # No results: no prompt, "No matches" message
                        mock_input.assert_not_called()
                        print_calls = [str(call) for call in mock_print.call_args_list]
                        self.assertTrue(
                            any("No matches found" in str(call) for call in print_calls)
                        )

    def test_main_search_invalid_date(self):
        """Test search rejects a malformed date filter without searching"""
        with patch("sys.argv", ["prog", "--search", "x", "--search-date-from", "bad"]):
            mock_searcher = Mock()
            with patch.dict(
                "sys.modules", {"search_conversations": _fake_search_module(mock_searcher)}
            ):
                with patch("builtins.print") as mock_print:
                    main()
                    mock_searcher.search.assert_not_called()
                    print_calls = [str(call) for call in mock_print.call_args_list]
                    self.assertTrue(
                        any("Invalid date format: bad" in c for c in print_calls)
                    )


class TestInteractiveMode(unittest.TestCase):
    """Test interactive mode functionality"""

    def _run_with_fake_ui(self, func, argv):
        mock_ui_main = Mock()
        with patch("sys.argv", argv):
            with patch.dict("sys.modules", {"interactive_ui": Mock(main=mock_ui_main)}):
                func()
        return mock_ui_main

    def test_main_interactive_flag_calls_launch(self):
        """Test --interactive flag launches the interactive UI"""
        with patch.object(ClaudeConversationExtractor, "__init__", return_value=None) as mock_init:
            mock_ui_main = self._run_with_fake_ui(main, ["prog", "--interactive"])
        mock_ui_main.assert_called_once()
        # Interactive mode returns before building a CLI extractor
        mock_init.assert_not_called()

    def test_main_export_flag_calls_interactive(self):
        """Test --export logs launches interactive mode"""
        mock_ui_main = self._run_with_fake_ui(main, ["prog", "--export", "logs"])
        mock_ui_main.assert_called_once()

    def test_main_no_args_lists_sessions(self):
        """Test main() with no arguments lists sessions instead of the UI"""
        with patch.object(
            ClaudeConversationExtractor, "list_recent_sessions", return_value=[]
        ) as mock_list:
            with patch("builtins.print"):
                mock_ui_main = self._run_with_fake_ui(main, ["prog"])
        mock_ui_main.assert_not_called()
        mock_list.assert_called_once_with(None)

    def test_launch_interactive_no_args_calls_interactive(self):
        """Test the console entry point with no arguments launches the UI"""
        mock_ui_main = self._run_with_fake_ui(launch_interactive, ["claude-start"])
        mock_ui_main.assert_called_once()


if __name__ == "__main__":
    unittest.main()
