#!/usr/bin/env python3
"""
Aligned tests for search_conversations.py with meaningful coverage
"""

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

# Add parent directory to path before local imports
sys.path.append(str(Path(__file__).parent.parent))

# Local imports after sys.path modification
from search_conversations import ConversationSearcher, SearchResult  # noqa: E402


class TestSearchResult(unittest.TestCase):
    """Test SearchResult dataclass"""

    def test_search_result_creation(self):
        """Test creating a SearchResult"""
        timestamp = datetime(2024, 1, 1, 10, 0)
        result = SearchResult(
            file_path=Path("/test/path.jsonl"),
            conversation_id="path",
            matched_content="Hello",
            context="Hello world",
            speaker="human",
            timestamp=timestamp,
            relevance_score=0.95,
            line_number=3,
        )

        self.assertEqual(result.file_path, Path("/test/path.jsonl"))
        self.assertEqual(result.conversation_id, "path")
        self.assertEqual(result.context, "Hello world")
        self.assertEqual(result.relevance_score, 0.95)
        self.assertEqual(result.speaker, "human")
        self.assertEqual(result.timestamp, timestamp)
        self.assertEqual(result.line_number, 3)

    def test_search_result_defaults(self):
        """Optional SearchResult fields have sensible defaults"""
        result = SearchResult(
            file_path=Path("/test/path.jsonl"),
            conversation_id="path",
            matched_content="Hello",
            context="Hello world",
            speaker="assistant",
        )

        self.assertIsNone(result.timestamp)
        self.assertEqual(result.relevance_score, 0.0)
        self.assertEqual(result.line_number, 0)

    def test_search_result_string_representation(self):
        """Test SearchResult string representation"""
        result = SearchResult(
            file_path=Path("/test/project/chat_123.jsonl"),
            conversation_id="chat_123",
            matched_content="Test",
            context="Test content",
            speaker="human",
            relevance_score=0.8,
        )

        str_repr = str(result)
        self.assertIn("chat_123.jsonl", str_repr)  # File name
        self.assertIn("Human", str_repr)  # Speaker in title case
        self.assertIn("80%", str_repr)  # Relevance score as percentage
        self.assertIn("Test content", str_repr)  # Context


class TestConversationSearcher(unittest.TestCase):
    """Test ConversationSearcher functionality"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.searcher = ConversationSearcher()

        # Create test conversation files
        self.create_test_conversations()

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def create_test_conversations(self):
        """Create test conversation files"""
        # Project 1: Python discussion
        project1 = Path(self.temp_dir) / ".claude" / "projects" / "python_project"
        project1.mkdir(parents=True)

        conv1 = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "How do I use Python decorators?",
                },
                "timestamp": "2024-01-01T10:00:00Z",
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "Python decorators are a way to modify functions.",
                        }
                    ],
                },
                "timestamp": "2024-01-01T10:01:00Z",
            },
        ]

        self.python_file = project1 / "chat_001.jsonl"
        with open(self.python_file, "w", encoding="utf-8") as f:
            for msg in conv1:
                f.write(json.dumps(msg) + "\n")

        # Project 2: JavaScript discussion
        project2 = Path(self.temp_dir) / ".claude" / "projects" / "js_project"
        project2.mkdir(parents=True)

        conv2 = [
            {
                "type": "user",
                "message": {"role": "user", "content": "Explain JavaScript promises"},
                "timestamp": "2024-01-02T10:00:00Z",
            }
        ]

        self.js_file = project2 / "chat_002.jsonl"
        with open(self.js_file, "w", encoding="utf-8") as f:
            for msg in conv2:
                f.write(json.dumps(msg) + "\n")

    def test_search_exact_match(self):
        """Test exact string matching"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            results = self.searcher.search("Python decorators", mode="exact")

            # Both the question and the answer contain the exact phrase
            self.assertEqual(len(results), 2)
            for result in results:
                self.assertIn("python decorators", result.matched_content.lower())
                self.assertIn("**PYTHON DECORATORS**", result.context)
                self.assertEqual(result.file_path, self.python_file)

    def test_search_case_insensitive(self):
        """Test case-insensitive search"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            results1 = self.searcher.search("python", case_sensitive=False)
            results2 = self.searcher.search("PYTHON", case_sensitive=False)

            # Should find same results regardless of case
            self.assertEqual(len(results1), len(results2))

    def test_search_case_sensitive(self):
        """Test case-sensitive search"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            results1 = self.searcher.search("Python", case_sensitive=True)
            results2 = self.searcher.search("python", case_sensitive=True)

            # May find different results based on case
            self.assertIsNotNone(results1)
            self.assertIsNotNone(results2)

    def test_search_regex_mode(self):
        """Test regex pattern matching"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            results = self.searcher.search(r"Python|JavaScript", mode="regex")

            # Should find both Python and JavaScript mentions
            self.assertEqual(len(results), 3)
            matched = {r.matched_content for r in results}
            self.assertEqual(matched, {"Python", "JavaScript"})
            self.assertEqual(
                {r.file_path for r in results}, {self.python_file, self.js_file}
            )

    def test_search_smart_mode(self):
        """Test smart search mode"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            results = self.searcher.search("programming language", mode="smart")

            # Should find relevant results even without exact match
            self.assertIsNotNone(results)

    def test_search_speaker_filter(self):
        """Test filtering by speaker"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            human_results = self.searcher.search("How", speaker_filter="human")
            assistant_results = self.searcher.search(
                "way to", speaker_filter="assistant"
            )

            # Check speaker filtering
            self.assertGreater(len(human_results), 0)
            for result in human_results:
                self.assertEqual(result.speaker, "human")

            self.assertGreater(len(assistant_results), 0)
            for result in assistant_results:
                self.assertEqual(result.speaker, "assistant")

    def test_search_date_filter(self):
        """Test date range filtering"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            # Date filtering uses file modification time, so align it with
            # the conversation timestamps
            py_time = datetime(2024, 1, 1, 10, 0).timestamp()
            js_time = datetime(2024, 1, 2, 10, 0).timestamp()
            os.utime(self.python_file, (py_time, py_time))
            os.utime(self.js_file, (js_time, js_time))

            # Search only for conversations after 2024-01-01 15:00
            date_from = datetime(2024, 1, 1, 15, 0)
            results = self.searcher.search(
                "Python|JavaScript", mode="regex", date_from=date_from
            )

            # Should only find JavaScript conversation (2024-01-02)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].file_path, self.js_file)
            self.assertIn("JavaScript", results[0].matched_content)

    def test_search_max_results(self):
        """Test limiting number of results"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            # The regex matches three messages across both projects
            all_results = self.searcher.search("Python|JavaScript", mode="regex")
            limited = self.searcher.search(
                "Python|JavaScript", mode="regex", max_results=1
            )

            self.assertEqual(len(all_results), 3)
            self.assertEqual(len(limited), 1)

    def test_search_empty_query(self):
        """Test searching with empty query"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            # Empty or whitespace-only queries return no results
            self.assertEqual(self.searcher.search(""), [])
            self.assertEqual(self.searcher.search("   "), [])

    def test_search_no_matches(self):
        """Test search with no matches"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            results = self.searcher.search("nonexistent12345query")

            self.assertEqual(len(results), 0)

    def test_search_with_context(self):
        """Test that search results include context"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            results = self.searcher.search("decorators", mode="exact")

            self.assertGreater(len(results), 0)
            for result in results:
                # Context is the text around the match, with the match highlighted
                self.assertIn("**DECORATORS**", result.context)

    def test_semantic_search_without_spacy(self):
        """Test semantic search falls back when spaCy not available"""
        # Without an NLP pipeline, semantic mode falls back to smart search
        self.searcher.nlp = None
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            semantic = self.searcher.search("Python decorators", mode="semantic")
            smart = self.searcher.search("Python decorators", mode="smart")

            self.assertGreater(len(semantic), 0)
            self.assertEqual(
                [(r.file_path, r.line_number, r.relevance_score) for r in semantic],
                [(r.file_path, r.line_number, r.relevance_score) for r in smart],
            )

    def test_semantic_search_with_spacy(self):
        """Test semantic search with spaCy available"""
        if self.searcher.nlp is None:
            self.skipTest("spaCy or the en_core_web_sm model is not installed")

        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            # "decorator" only matches "decorators" through lemmatisation
            results = self.searcher.search("decorator", mode="semantic")

            self.assertGreater(len(results), 0)
            for result in results:
                self.assertEqual(result.file_path, self.python_file)
                self.assertGreater(result.relevance_score, 0.3)

    def test_search_corrupted_jsonl(self):
        """Test search handles corrupted JSONL files gracefully"""
        # Create corrupted file
        bad_project = Path(self.temp_dir) / ".claude" / "projects" / "bad_project"
        bad_project.mkdir(parents=True)

        with open(bad_project / "chat_bad.jsonl", "w", encoding="utf-8") as f:
            f.write("not json\n")
            f.write('{"invalid": json}\n')
            f.write('{"type": "user", "message": {"content": "Valid message"}}\n')

        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            # Should not crash, just skip bad lines
            results = self.searcher.search("Valid")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].matched_content, "Valid message")
            self.assertEqual(results[0].line_number, 3)

    def test_results_ranked_by_relevance(self):
        """search() returns results sorted by relevance (descending)"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            results = self.searcher.search("Python decorators", mode="smart")

            self.assertEqual(len(results), 2)
            scores = [r.relevance_score for r in results]
            self.assertEqual(scores, sorted(scores, reverse=True))
            # The answer matches the phrase and every query token exactly, so it
            # outranks the question (whose "decorators?" token has punctuation)
            self.assertEqual(results[0].speaker, "assistant")
            self.assertEqual(results[1].speaker, "human")
            self.assertGreater(results[0].relevance_score, results[1].relevance_score)

    def test_extract_content(self):
        """Test content extraction from different entry formats"""
        # Plain string content at the top level
        content = self.searcher._extract_content(
            {"type": "user", "content": "Simple string"}
        )
        self.assertEqual(content, "Simple string")

        # String message content (Claude log format)
        content = self.searcher._extract_content(
            {"type": "user", "message": {"role": "user", "content": "Hi there"}}
        )
        self.assertEqual(content, "Hi there")

        # List message content: text parts are joined, other parts ignored
        content = self.searcher._extract_content(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Part 1"},
                        {"type": "tool_use", "name": "Bash"},
                        {"type": "text", "text": "Part 2"},
                    ]
                },
            }
        )
        self.assertEqual(content, "Part 1 Part 2")

        # Unknown formats yield no content
        content = self.searcher._extract_content({"unknown": "format"})
        self.assertEqual(content, "")

    def test_smart_search_matches_tokens_out_of_order(self):
        """Smart search matches on query tokens, not only the exact phrase"""
        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            # Reordered words: no exact substring match anywhere
            results = self.searcher.search("decorators python", mode="smart")
            self.assertEqual(len(results), 2)
            for result in results:
                self.assertEqual(result.file_path, self.python_file)

            # Exact mode does not match the reordered phrase
            self.assertEqual(
                self.searcher.search("decorators python", mode="exact"), []
            )

            # Unrelated tokens match nothing
            self.assertEqual(self.searcher.search("xyz", mode="smart"), [])


class TestSearchIntegration(unittest.TestCase):
    """Integration tests for search functionality"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.searcher = ConversationSearcher()

    def tearDown(self):
        """Clean up test environment"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_end_to_end_search_workflow(self):
        """Test complete search workflow"""
        # Create realistic conversation
        project = Path(self.temp_dir) / ".claude" / "projects" / "test_project"
        project.mkdir(parents=True)

        conversation = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": "How do I handle errors in Python?",
                },
                "timestamp": datetime.now().isoformat(),
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": "You can use try-except blocks for error handling.",
                        }
                    ],
                },
                "timestamp": datetime.now().isoformat(),
            },
            {
                "type": "user",
                "message": {"role": "user", "content": "Can you show an example?"},
                "timestamp": datetime.now().isoformat(),
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "try:\n    risky_operation()\n"
                                "except Exception as e:\n    print(f'Error: {e}')"
                            ),
                        }
                    ],
                },
                "timestamp": datetime.now().isoformat(),
            },
        ]

        chat_file = project / "chat_test.jsonl"
        with open(chat_file, "w", encoding="utf-8") as f:
            for msg in conversation:
                f.write(json.dumps(msg) + "\n")

        with patch("pathlib.Path.home", return_value=Path(self.temp_dir)):
            # Search for error handling
            results = self.searcher.search("error handling", mode="smart")

            self.assertGreater(len(results), 0)

            # Verify results have expected structure
            first = results[0]
            self.assertEqual(first.file_path, chat_file)
            self.assertEqual(first.conversation_id, "chat_test")
            self.assertGreater(first.relevance_score, 0)
            # Only the answer contains the exact phrase "error handling"
            self.assertEqual(first.speaker, "assistant")
            self.assertEqual(first.line_number, 2)
            self.assertIn("**ERROR HANDLING**", first.context)
            self.assertIsInstance(first.timestamp, datetime)


if __name__ == "__main__":
    unittest.main()
