# unit tests for remap_engine's pure logic. apply_remaps() normally
# installs real windows-wide keyboard/mouse hooks, so keyboard/mouse/
# mouse_hook are mocked out here rather than actually hooking anything.

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import remap_engine


class LoadSaveRemapsTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        patcher = patch.object(
            remap_engine, "REMAPS_FILE", Path(self.tmpdir.name) / "remaps.json"
        )
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_load_missing_file_returns_empty_list(self):
        self.assertEqual(remap_engine.load_remaps(), [])

    def test_save_then_load_round_trips(self):
        remaps = [
            {"from_type": "key", "from": "a", "to_type": "key", "to": "b", "enabled": True}
        ]
        remap_engine.save_remaps(remaps)
        self.assertEqual(remap_engine.load_remaps(), remaps)

    def test_load_corrupt_file_returns_empty_list(self):
        remap_engine.REMAPS_FILE.write_text("not json", encoding="utf-8")
        self.assertEqual(remap_engine.load_remaps(), [])


class ApplyRemapsTests(unittest.TestCase):
    def setUp(self):
        for name in ("keyboard", "mouse", "mouse_hook"):
            patcher = patch.object(remap_engine, name, MagicMock())
            setattr(self, name, patcher.start())
            self.addCleanup(patcher.stop)

    def test_key_to_key_uses_remap_key(self):
        remap_engine.apply_remaps(
            [{"from_type": "key", "from": "caps lock", "to_type": "key", "to": "esc", "enabled": True}]
        )
        self.keyboard.unhook_all.assert_called_once()
        self.keyboard.remap_key.assert_called_once_with("caps lock", "esc")

    def test_key_to_mouse_uses_suppressed_hook(self):
        remap_engine.apply_remaps(
            [{"from_type": "key", "from": "f1", "to_type": "mouse", "to": "middle", "enabled": True}]
        )
        self.keyboard.hook_key.assert_called_once()
        args, kwargs = self.keyboard.hook_key.call_args
        self.assertEqual(args[0], "f1")
        self.assertTrue(kwargs.get("suppress"))

    def test_mouse_source_goes_into_mouse_hook_map(self):
        remap_engine.apply_remaps(
            [{"from_type": "mouse", "from": "x", "to_type": "key", "to": "space", "enabled": True}]
        )
        self.mouse_hook.set_active_map.assert_called_once_with({"x": ("key", "space")})
        self.mouse_hook.start.assert_called_once()

    def test_left_click_source_is_ignored(self):
        remap_engine.apply_remaps(
            [{"from_type": "mouse", "from": "left", "to_type": "key", "to": "space", "enabled": True}]
        )
        self.mouse_hook.set_active_map.assert_called_once_with({})

    def test_disabled_remap_is_skipped(self):
        remap_engine.apply_remaps(
            [{"from_type": "key", "from": "a", "to_type": "key", "to": "b", "enabled": False}]
        )
        self.keyboard.remap_key.assert_not_called()


class ValidateRemapTests(unittest.TestCase):
    def test_left_click_source_rejected(self):
        self.assertIsNotNone(remap_engine.validate_remap([], "mouse", "left", "key", "a"))

    def test_self_remap_rejected(self):
        self.assertIsNotNone(remap_engine.validate_remap([], "key", "a", "key", "a"))

    def test_duplicate_source_rejected(self):
        existing = [{"from_type": "key", "from": "a", "to_type": "key", "to": "b"}]
        self.assertIsNotNone(remap_engine.validate_remap(existing, "key", "a", "key", "c"))

    def test_editing_excludes_itself_from_duplicate_check(self):
        existing_remap = {"from_type": "key", "from": "a", "to_type": "key", "to": "b"}
        error = remap_engine.validate_remap(
            [existing_remap], "key", "a", "key", "c", editing=existing_remap
        )
        self.assertIsNone(error)

    def test_valid_remap_returns_none(self):
        self.assertIsNone(remap_engine.validate_remap([], "key", "a", "key", "b"))


if __name__ == "__main__":
    unittest.main()
