#!/usr/bin/env python3
"""
Comprehensive tests for extract_claude_logs.py to achieve 100% coverage
"""

import json
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path before local imports
sys.path.append(str(Path(__file__).parent.parent))

# Local imports after sys.path modification
from extract_claude_logs import (  # noqa: E402
    ClaudeConversationExtractor,
    launch_interactive,
    main,
)


def _no_prompt(*args, **kwargs):
    raise AssertionError("unexpected input() prompt")


class TestClaudeConversationExtractorComprehensive(unittest.TestCase):
    """Comprehensive tests for ClaudeConversationExtractor"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()

        # Create test Claude directory structure
        self.claude_dir = Path(self.temp_dir) / ".claude" / "projects"
        self.claude_dir.mkdir(parents=True)

        # Build the extractor with home pointed at temp_dir so its claude_dir
        # is the directory created above.
        with patch("extract_claude_logs.Path.home", return_value=Path(self.temp_dir)):
            self.extractor = ClaudeConversationExtractor(self.temp_dir)
        self.assertEqual(self.extractor.claude_dir, self.claude_dir)

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_init_with_custom_output(self):
        """Test initialization with custom output directory"""
        custom_dir = Path(self.temp_dir) / "custom"
        extractor = ClaudeConversationExtractor(str(custom_dir))
        self.assertEqual(extractor.output_dir, custom_dir)
        self.assertTrue(custom_dir.is_dir())

    def test_init_with_none_output(self):
        """Test initialization with None output directory"""
        with patch("extract_claude_logs.Path.home", return_value=Path(self.temp_dir)):
            extractor = ClaudeConversationExtractor(None)
        # First writable candidate is ~/Desktop/Claude logs
        self.assertEqual(
            extractor.output_dir, Path(self.temp_dir) / "Desktop" / "Claude logs"
        )

    def test_find_sessions_empty(self):
        """Test finding sessions when none exist"""
        sessions = self.extractor.find_sessions()
        self.assertEqual(sessions, [])

    def test_find_sessions_with_files(self):
        """Test finding sessions with JSONL files"""
        # Create test JSONL files
        project_dir = self.claude_dir / "test_project"
        project_dir.mkdir()

        chat_file1 = project_dir / "chat_123.jsonl"
        chat_file2 = project_dir / "chat_456.jsonl"
        chat_file1.write_text("{}", encoding="utf-8")
        chat_file2.write_text("{}", encoding="utf-8")

        sessions = self.extractor.find_sessions()
        self.assertEqual(sorted(sessions), sorted([chat_file1, chat_file2]))

    def test_extract_text_content_string(self):
        """Test extracting text from string content"""
        content = "Simple text content"
        result = self.extractor._extract_text_content(content)
        self.assertEqual(result, content)

    def test_extract_text_content_list(self):
        """Test extracting text from list content"""
        content = [
            {"type": "text", "text": "Part 1"},
            {"type": "text", "text": "Part 2"},
            {"type": "image", "data": "..."},  # Should be ignored
        ]
        result = self.extractor._extract_text_content(content)
        self.assertEqual(result, "Part 1\nPart 2")

    def test_extract_text_content_empty(self):
        """Test extracting text from empty content"""
        self.assertEqual(self.extractor._extract_text_content([]), "")
        self.assertEqual(self.extractor._extract_text_content(""), "")
        self.assertEqual(self.extractor._extract_text_content(None), "")

    def test_save_as_markdown_basic(self):
        """Test saving conversation as markdown"""
        conversation = [
            {"role": "user", "content": "Hello", "timestamp": "2024-01-01T10:00:00Z"},
            {
                "role": "assistant",
                "content": "Hi there!",
                "timestamp": "2024-01-01T10:01:00Z",
            },
        ]

        output_path = self.extractor.save_as_markdown(conversation, "test_session")

        self.assertTrue(output_path.exists())
        content = output_path.read_text(encoding="utf-8")
        self.assertIn("Hello", content)
        self.assertIn("Hi there!", content)
        self.assertIn("## 👤 User", content)
        self.assertIn("## 🤖 Claude", content)

    def test_save_as_markdown_with_code(self):
        """Test saving conversation with code blocks"""
        conversation = [
            {"role": "user", "content": "Write Python hello world", "timestamp": ""},
            {
                "role": "assistant",
                "content": "```python\nprint('Hello, World!')\n```",
                "timestamp": "",
            },
        ]

        output_path = self.extractor.save_as_markdown(conversation, "code_session")
        content = output_path.read_text(encoding="utf-8")

        # Should preserve code blocks
        self.assertIn("```python", content)
        self.assertIn("print('Hello, World!')", content)

    def test_list_sessions(self):
        """Test listing sessions with details (list_recent_sessions)"""
        # Create test file
        project_dir = self.claude_dir / "test_project"
        project_dir.mkdir()
        chat_file = project_dir / "chat_test.jsonl"
        chat_file.write_text('{"type": "test"}', encoding="utf-8")

        with patch("builtins.print") as mock_print:
            sessions = self.extractor.list_recent_sessions(limit=5)

        # Should print session details
        self.assertTrue(
            any("test_project" in str(call) for call in mock_print.call_args_list)
        )
        self.assertEqual(sessions, [chat_file])

    def test_extract_multiple_success(self):
        """Test extracting multiple sessions"""
        # Create test sessions
        sessions = [
            Path(self.temp_dir) / "session1.jsonl",
            Path(self.temp_dir) / "session2.jsonl",
        ]

        for session in sessions:
            session.write_text(
                json.dumps(
                    {
                        "type": "user",
                        "message": {"role": "user", "content": "Test"},
                        "timestamp": "2024-01-01T10:00:00Z",
                    }
                ),
                encoding="utf-8",
            )

        with patch("builtins.print"):
            success, total = self.extractor.extract_multiple(sessions, [0, 1])

        self.assertEqual(success, 2)
        self.assertEqual(total, 2)

    def test_extract_multiple_with_invalid_index(self):
        """Test extracting with invalid indices"""
        sessions = [Path(self.temp_dir) / "session.jsonl"]

        with patch("builtins.print"):
            success, total = self.extractor.extract_multiple(
                sessions, [5]
            )  # Invalid index

        self.assertEqual(success, 0)
        self.assertEqual(total, 1)

    # --- CLI (main) -------------------------------------------------------

    def _run_main(self, argv, sessions=None, extract_result=(0, 0)):
        """Run main() with argv and stubbed find_sessions / extract_multiple."""
        sessions = sessions if sessions is not None else []
        with patch("sys.argv", ["extract_claude_logs.py"] + argv), patch.object(
            ClaudeConversationExtractor, "find_sessions", return_value=sessions
        ), patch.object(
            ClaudeConversationExtractor,
            "extract_multiple",
            return_value=extract_result,
        ) as mock_extract, patch("builtins.input", side_effect=_no_prompt), patch(
            "builtins.print"
        ):
            main()
        return mock_extract

    def test_extract_recent(self):
        """--recent N is capped at the number of available sessions"""
        mock_sessions = [Path(self.temp_dir) / f"session{i}.jsonl" for i in range(3)]

        mock_extract = self._run_main(
            ["--recent", "10"], sessions=mock_sessions, extract_result=(3, 3)
        )

        mock_extract.assert_called_once_with(
            mock_sessions, [0, 1, 2], format="markdown", detailed=False, thinking=False, timestamps=False
        )

    def test_extract_all(self):
        """--all extracts every session, passing format and detailed through"""
        mock_sessions = [Path(self.temp_dir) / f"session{i}.jsonl" for i in range(5)]

        mock_extract = self._run_main(
            ["--all", "--format", "json", "--detailed"],
            sessions=mock_sessions,
            extract_result=(5, 5),
        )

        mock_extract.assert_called_once_with(
            mock_sessions, list(range(5)), format="json", detailed=True, thinking=False, timestamps=False
        )

    def test_extract_with_thinking_and_timestamps(self):
        """--thinking and --timestamps are opt-in flags passed through to extraction"""
        mock_sessions = [Path(self.temp_dir) / f"session{i}.jsonl" for i in range(3)]

        mock_extract = self._run_main(
            ["--all", "--thinking", "--timestamps"],
            sessions=mock_sessions,
            extract_result=(3, 3),
        )

        mock_extract.assert_called_once_with(
            mock_sessions, list(range(3)), format="markdown", detailed=False, thinking=True, timestamps=True
        )

    def test_main_list_command(self):
        """Test main function with --list"""
        with patch("sys.argv", ["extract_claude_logs.py", "--list", "--limit", "3"]):
            with patch.object(
                ClaudeConversationExtractor, "list_recent_sessions", return_value=[]
            ) as mock_list, patch.object(
                ClaudeConversationExtractor, "extract_multiple"
            ) as mock_extract, patch("builtins.print"):
                main()
        mock_list.assert_called_once_with(3)
        mock_extract.assert_not_called()

    def test_main_extract_single(self):
        """Test main function with --extract"""
        sessions = [Path("test.jsonl")]
        mock_extract = self._run_main(
            ["--extract", "1"], sessions=sessions, extract_result=(1, 1)
        )
        mock_extract.assert_called_once_with(
            sessions, [0], format="markdown", detailed=False, thinking=False, timestamps=False
        )

    def test_main_extract_multiple_comma(self):
        """Test main function with comma-separated indices"""
        sessions = [Path(f"test{i}.jsonl") for i in range(5)]
        mock_extract = self._run_main(
            ["--extract", "1,2,3"], sessions=sessions, extract_result=(3, 3)
        )
        # Should extract indices 0, 1, 2 (1-based to 0-based)
        args = mock_extract.call_args[0]
        self.assertEqual(args[1], [0, 1, 2])

    def test_main_extract_skips_invalid_numbers(self):
        """Non-numeric entries in --extract are skipped, valid ones kept"""
        sessions = [Path(f"test{i}.jsonl") for i in range(5)]
        mock_extract = self._run_main(
            ["--extract", "2,abc,4"], sessions=sessions, extract_result=(2, 2)
        )
        self.assertEqual(mock_extract.call_args[0][1], [1, 3])

    def test_main_recent(self):
        """Test main function with --recent"""
        sessions = [Path(self.temp_dir) / f"session{i}.jsonl" for i in range(10)]
        mock_extract = self._run_main(
            ["--recent", "5"], sessions=sessions, extract_result=(5, 5)
        )
        mock_extract.assert_called_once_with(
            sessions, [0, 1, 2, 3, 4], format="markdown", detailed=False, thinking=False, timestamps=False
        )

    def test_main_all(self):
        """Test main function with --all"""
        sessions = [Path(self.temp_dir) / f"session{i}.jsonl" for i in range(4)]
        mock_extract = self._run_main(
            ["--all"], sessions=sessions, extract_result=(4, 4)
        )
        mock_extract.assert_called_once_with(
            sessions, [0, 1, 2, 3], format="markdown", detailed=False, thinking=False, timestamps=False
        )

    def test_main_interactive(self):
        """Test main function with --interactive launches the interactive UI"""
        with patch("sys.argv", ["extract_claude_logs.py", "--interactive"]):
            with patch("interactive_ui.main") as mock_ui_main, patch.object(
                ClaudeConversationExtractor, "list_recent_sessions"
            ) as mock_list:
                main()
        mock_ui_main.assert_called_once_with()
        # Interactive mode returns before any CLI action runs
        mock_list.assert_not_called()

    def test_main_export(self):
        """Test main function with --export logs launches the interactive UI"""
        with patch("sys.argv", ["extract_claude_logs.py", "--export", "logs"]):
            with patch("interactive_ui.main") as mock_ui_main:
                main()
        mock_ui_main.assert_called_once_with()

    def test_main_search(self):
        """Test main function with --search"""
        with patch("sys.argv", ["extract_claude_logs.py", "--search", "test query"]):
            with patch("search_conversations.ConversationSearcher") as mock_searcher:
                mock_searcher.return_value.search.return_value = []
                with patch("builtins.print"), patch(
                    "builtins.input", side_effect=_no_prompt
                ):
                    main()
        mock_searcher.return_value.search.assert_called_once()
        kwargs = mock_searcher.return_value.search.call_args[1]
        self.assertEqual(kwargs["query"], "test query")
        self.assertEqual(kwargs["mode"], "smart")
        self.assertIsNone(kwargs["speaker_filter"])
        self.assertFalse(kwargs["case_sensitive"])

    def test_main_search_with_filters(self):
        """Test main function with search filters"""
        with patch(
            "sys.argv",
            [
                "extract_claude_logs.py",
                "--search-regex",
                "imp.*rt",
                "--search-speaker",
                "human",
                "--search-date-from",
                "2024-01-01",
                "--search-date-to",
                "2024-02-01",
                "--case-sensitive",
            ],
        ):
            with patch("search_conversations.ConversationSearcher") as mock_searcher:
                mock_searcher.return_value.search.return_value = []
                with patch("builtins.print"), patch(
                    "builtins.input", side_effect=_no_prompt
                ):
                    main()

        # Check search was called with correct parameters
        search_call = mock_searcher.return_value.search.call_args
        self.assertEqual(search_call[1]["query"], "imp.*rt")
        self.assertEqual(search_call[1]["mode"], "regex")
        self.assertEqual(search_call[1]["speaker_filter"], "human")
        self.assertEqual(search_call[1]["date_from"], datetime(2024, 1, 1))
        self.assertEqual(search_call[1]["date_to"], datetime(2024, 2, 1))
        self.assertTrue(search_call[1]["case_sensitive"])

    def test_main_search_invalid_date(self):
        """An invalid --search-date-from aborts before searching"""
        with patch(
            "sys.argv",
            ["extract_claude_logs.py", "--search", "x", "--search-date-from", "bad"],
        ):
            with patch("search_conversations.ConversationSearcher") as mock_searcher:
                with patch("builtins.print") as mock_print:
                    main()
        mock_searcher.return_value.search.assert_not_called()
        self.assertTrue(
            any("Invalid date format" in str(c) for c in mock_print.call_args_list)
        )

    def test_main_no_args(self):
        """With no arguments main() lists sessions (the default action)"""
        with patch("sys.argv", ["extract_claude_logs.py"]):
            with patch.object(
                ClaudeConversationExtractor, "list_recent_sessions", return_value=[]
            ) as mock_list, patch.object(
                ClaudeConversationExtractor, "extract_multiple"
            ) as mock_extract, patch("interactive_ui.main") as mock_ui_main, patch(
                "builtins.print"
            ):
                main()
        mock_list.assert_called_once_with(None)
        mock_extract.assert_not_called()
        mock_ui_main.assert_not_called()

    def test_launch_interactive_no_args(self):
        """The no-args entry point (launch_interactive) opens the interactive UI"""
        with patch("sys.argv", ["claude-extract"]):
            with patch("interactive_ui.main") as mock_ui_main, patch(
                "extract_claude_logs.main"
            ) as mock_cli_main:
                launch_interactive()
        mock_ui_main.assert_called_once_with()
        mock_cli_main.assert_not_called()

    def test_launch_interactive_with_args_runs_cli(self):
        """launch_interactive defers to main() when CLI arguments are given"""
        with patch("sys.argv", ["claude-extract", "--list"]):
            with patch("interactive_ui.main") as mock_ui_main, patch(
                "extract_claude_logs.main"
            ) as mock_cli_main:
                launch_interactive()
        mock_cli_main.assert_called_once_with()
        mock_ui_main.assert_not_called()

    def test_extract_conversation_with_errors(self):
        """Test extract_conversation with file read errors"""
        bad_file = Path(self.temp_dir) / "bad.jsonl"
        bad_file.write_text("not json\n{bad json}\n", encoding="utf-8")

        with patch("builtins.print"):
            conversation = self.extractor.extract_conversation(bad_file)
            # Should return empty conversation on error
            self.assertEqual(conversation, [])

    def test_output_dir_fallback(self):
        """Output dir falls back to ./claude-logs when no home dir is writable"""
        # A regular file as "home" makes every home-based mkdir fail on all OSes.
        fake_home = Path(self.temp_dir) / "not_a_dir"
        fake_home.write_text("", encoding="utf-8")
        cwd = Path(self.temp_dir) / "cwd"
        cwd.mkdir()

        with patch("extract_claude_logs.Path.home", return_value=fake_home), patch(
            "extract_claude_logs.Path.cwd", return_value=cwd
        ):
            extractor = ClaudeConversationExtractor(None)

        self.assertEqual(extractor.output_dir, cwd / "claude-logs")
        self.assertTrue(extractor.output_dir.is_dir())


if __name__ == "__main__":
    unittest.main()
