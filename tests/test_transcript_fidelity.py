"""Tests for the parts of the JSONL format that were being dropped.

Each test here covers one shape that exists in real Claude Code logs and
that `extract_conversation()` used to discard: a message queued while a
turn was running, a tool result, and an extended thinking block.
"""

import json
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from extract_claude_logs import ClaudeConversationExtractor


def _user(text, timestamp="2025-01-01T10:00:00Z"):
    return {
        "type": "user",
        "message": {"role": "user", "content": text},
        "timestamp": timestamp,
    }


def _assistant(blocks, timestamp="2025-01-01T10:00:01Z"):
    return {
        "type": "assistant",
        "message": {"role": "assistant", "content": blocks},
        "timestamp": timestamp,
    }


def _queued(prompt, kind="human", timestamp="2025-01-01T10:00:02Z"):
    attachment = {
        "type": "queued_command",
        "prompt": prompt,
        "timestamp": timestamp,
    }
    if kind is not None:
        attachment["origin"] = {"kind": kind}
    return {"type": "attachment", "attachment": attachment, "timestamp": timestamp}


class TestTranscriptFidelity(unittest.TestCase):
    """Extraction of content that the walk used to skip."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.extractor = ClaudeConversationExtractor(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write(self, entries):
        path = Path(self.temp_dir) / "session.jsonl"
        path.write_text(
            "\n".join(json.dumps(e) for e in entries), encoding="utf-8"
        )
        return path

    def test_queued_human_message_is_extracted(self):
        """A message typed mid-turn is recovered as a user message"""
        path = self._write([_user("first"), _queued("sent while busy")])
        conversation = self.extractor.extract_conversation(path)

        self.assertEqual(len(conversation), 2)
        self.assertEqual(conversation[1]["role"], "user")
        self.assertEqual(conversation[1]["content"], "sent while busy")
        self.assertEqual(conversation[1]["timestamp"], "2025-01-01T10:00:02Z")

    def test_queued_message_with_content_blocks(self):
        """A queued message whose prompt is a block list is flattened"""
        prompt = [
            {"type": "image", "source": {"type": "base64", "data": "..."}},
            {"type": "text", "text": "look at this"},
        ]
        path = self._write([_queued(prompt)])
        conversation = self.extractor.extract_conversation(path)

        self.assertEqual(len(conversation), 1)
        self.assertEqual(conversation[0]["content"], "look at this")

    def test_queued_non_human_commands_are_ignored(self):
        """Commands queued by the tool itself are not user messages"""
        entries = [
            _queued("task finished", kind="task-notification"),
            _queued("from another session", kind="peer"),
            _queued("no origin at all", kind=None),
            {"type": "attachment", "attachment": {"type": "environment"}},
            {"type": "attachment", "attachment": "not a dict"},
        ]
        conversation = self.extractor.extract_conversation(self._write(entries))

        self.assertEqual(conversation, [])

    def test_tool_results_are_extracted_in_detailed_mode(self):
        """tool_result blocks inside a user entry are not dropped"""
        entries = [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [
                        {"type": "tool_result", "content": "plain output"},
                        {
                            "type": "tool_result",
                            "content": [{"type": "text", "text": "block output"}],
                        },
                        {
                            "type": "tool_result",
                            "content": "it broke",
                            "is_error": True,
                        },
                    ],
                },
                "timestamp": "2025-01-01T10:00:03Z",
            }
        ]
        path = self._write(entries)

        self.assertEqual(self.extractor.extract_conversation(path), [])

        conversation = self.extractor.extract_conversation(path, detailed=True)
        self.assertEqual(len(conversation), 3)
        self.assertEqual([m["role"] for m in conversation], ["tool_result"] * 3)
        self.assertIn("plain output", conversation[0]["content"])
        self.assertIn("block output", conversation[1]["content"])
        self.assertIn("[error]", conversation[2]["content"])
        self.assertEqual(conversation[0]["timestamp"], "2025-01-01T10:00:03Z")

    def test_thinking_is_hidden_by_default(self):
        """Thinking is opt-in: without thinking=True only the answer is kept"""
        blocks = [
            {"type": "thinking", "thinking": "weighing it up", "signature": "x"},
            {"type": "text", "text": "here is the answer"},
        ]
        path = self._write([_assistant(blocks), _assistant([blocks[0]])])
        conversation = self.extractor.extract_conversation(path)

        # The thinking-only entry is dropped and no thinking text leaks in.
        self.assertEqual(len(conversation), 1)
        self.assertEqual(conversation[0]["content"], "here is the answer")

    def test_thinking_blocks_are_kept_when_requested(self):
        """With thinking=True, extended thinking reaches the output, marked as thinking"""
        blocks = [
            {"type": "thinking", "thinking": "weighing it up", "signature": "x"},
            {"type": "text", "text": "here is the answer"},
        ]
        conversation = self.extractor.extract_conversation(
            self._write([_assistant(blocks)]), thinking=True
        )

        self.assertEqual(len(conversation), 1)
        self.assertIn("🧠 Thinking:", conversation[0]["content"])
        self.assertIn("weighing it up", conversation[0]["content"])
        self.assertIn("here is the answer", conversation[0]["content"])

    def test_thinking_block_without_text_is_skipped(self):
        """A thinking block that stored no text produces no output"""
        blocks = [
            {"type": "thinking", "thinking": "", "signature": "x"},
            {"type": "text", "text": "answer"},
        ]
        conversation = self.extractor.extract_conversation(
            self._write([_assistant(blocks)]), thinking=True
        )

        self.assertEqual(len(conversation), 1)
        self.assertNotIn("Thinking", conversation[0]["content"])


class TestPerMessageTimestamps(unittest.TestCase):
    """Per-message times in markdown/html are opt-in and shown in local time."""

    CONVERSATION = [
        {"role": "user", "content": "hi", "timestamp": "2025-01-01T10:00:00Z"},
        {"role": "assistant", "content": "hello", "timestamp": "2025-01-01T10:05:00Z"},
        {"role": "user", "content": "no stamp", "timestamp": ""},
    ]

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.extractor = ClaudeConversationExtractor(self.temp_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @staticmethod
    def _local(iso):
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

    def test_markdown_has_no_message_timestamps_by_default(self):
        text = self.extractor.save_as_markdown(self.CONVERSATION, "s").read_text(encoding="utf-8")
        self.assertIn("## 👤 User\n", text)
        self.assertIn("## 🤖 Claude\n", text)
        self.assertNotIn(f"[{self._local('2025-01-01T10:05:00Z')}]", text)

    def test_markdown_carries_local_timestamps_when_requested(self):
        text = self.extractor.save_as_markdown(
            self.CONVERSATION, "s", timestamps=True
        ).read_text(encoding="utf-8")
        self.assertIn(f"## 👤 User [{self._local('2025-01-01T10:00:00Z')}]", text)
        self.assertIn(f"## 🤖 Claude [{self._local('2025-01-01T10:05:00Z')}]", text)
        # An item with no timestamp keeps the old heading exactly
        self.assertIn("## 👤 User\n", text)

    def test_html_timestamps_are_opt_in(self):
        plain = self.extractor.save_as_html(self.CONVERSATION, "a").read_text(encoding="utf-8")
        stamped = self.extractor.save_as_html(
            self.CONVERSATION, "b", timestamps=True
        ).read_text(encoding="utf-8")
        when = self._local("2025-01-01T10:05:00Z")
        self.assertNotIn('<span class="ts">', plain)
        self.assertIn(f'🤖 Claude<span class="ts">{when}</span>', stamped)

    def test_save_conversation_passes_timestamps_through(self):
        out = self.extractor.save_conversation(
            self.CONVERSATION, "c", format="markdown", timestamps=True
        )
        self.assertIn(self._local("2025-01-01T10:00:00Z"), out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
