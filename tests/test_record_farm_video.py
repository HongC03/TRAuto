import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from threading import Event

from event_script.record_farm_video import (
    create_video_writer,
    parse_args,
    video_path,
)


class FakeWriter:
    def __init__(self):
        self.released = False

    def isOpened(self):
        return True

    def release(self):
        self.released = True


class FakeCV2:
    VideoWriter_fourcc = staticmethod(lambda *parts: "codec")

    def __init__(self):
        self.writer = FakeWriter()

    def VideoWriter(self, path, codec, fps, size):
        self.arguments = (path, codec, fps, size)
        return self.writer


class RecordFarmVideoTests(unittest.TestCase):
    def test_video_path_is_timestamped_mp4(self):
        with tempfile.TemporaryDirectory() as directory:
            path = video_path(
                directory,
                recorded_at=datetime(2026, 8, 7, 22, 0, 1, 123456),
            )

            self.assertEqual(path.suffix, ".mp4")
            self.assertEqual(path.name, "farm_screen_20260807_220001_123456.mp4")
            self.assertTrue(path.parent.is_dir())

    def test_create_video_writer_uses_screen_dimensions_and_fps(self):
        backend = FakeCV2()
        writer = create_video_writer(Path("capture.mp4"), (1280, 720), 10, backend)

        self.assertIs(writer, backend.writer)
        self.assertEqual(
            backend.arguments,
            ("capture.mp4", "codec", 10, (1280, 720)),
        )

    def test_parse_args_accepts_video_options(self):
        args = parse_args(
            [
                "--output-dir",
                "/tmp/farm-video",
                "--fps",
                "15",
                "--finish-key",
                "f8",
                "--cancel-key",
                "esc",
            ]
        )

        self.assertEqual(args.output_dir, Path("/tmp/farm-video"))
        self.assertEqual(args.fps, 15)
        self.assertEqual(args.finish_key, "f8")
        self.assertEqual(args.cancel_key, "esc")


if __name__ == "__main__":
    unittest.main()
