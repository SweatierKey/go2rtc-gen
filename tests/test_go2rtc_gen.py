"""Tests for go2rtc-gen. Pure stdlib, no network."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "go2rtc-gen"


def _load_module():
    loader = SourceFileLoader("go2rtc_gen", str(SCRIPT))
    spec = importlib.util.spec_from_loader("go2rtc_gen", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


gg = _load_module()


def _run(args, stdin_text=None, timeout=10):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True,
        input=stdin_text, timeout=timeout,
    )


# ---------------------------------------------------------------------------
# Unit-level
# ---------------------------------------------------------------------------

class CollectUrlsTests(unittest.TestCase):
    def test_blank_lines_ignored(self):
        valid, dropped, saw = gg.collect_urls(
            ["", "  ", "rtsp://a/x", "\n", "rtsp://b/y"]
        )
        self.assertEqual(valid, ["rtsp://a/x", "rtsp://b/y"])
        self.assertEqual(dropped, [])
        self.assertTrue(saw)

    def test_non_rtsp_dropped(self):
        valid, dropped, saw = gg.collect_urls(
            ["rtsp://a/x", "http://b/y", "garbage"]
        )
        self.assertEqual(valid, ["rtsp://a/x"])
        self.assertEqual(dropped, ["http://b/y", "garbage"])
        self.assertTrue(saw)

    def test_completely_empty(self):
        valid, dropped, saw = gg.collect_urls([])
        self.assertEqual(valid, [])
        self.assertEqual(dropped, [])
        self.assertFalse(saw)

    def test_only_blank_lines(self):
        valid, dropped, saw = gg.collect_urls(["\n", "  ", ""])
        self.assertEqual(valid, [])
        self.assertEqual(dropped, [])
        self.assertFalse(saw)

    def test_case_insensitive_scheme(self):
        valid, _, _ = gg.collect_urls(["RTSP://a/x", "Rtsp://b/y"])
        self.assertEqual(valid, ["RTSP://a/x", "Rtsp://b/y"])


class RenderYamlTests(unittest.TestCase):
    def test_two_streams_default_prefix(self):
        out = gg.render_yaml(
            ["rtsp://1.1.1.1/a", "rtsp://2.2.2.2/b"],
            "cam", ":1984", ":8554",
        )
        self.assertEqual(
            out,
            'api:\n'
            '  listen: ":1984"\n'
            'rtsp:\n'
            '  listen: ":8554"\n'
            'streams:\n'
            '  cam1: rtsp://1.1.1.1/a\n'
            '  cam2: rtsp://2.2.2.2/b\n',
        )

    def test_listen_starting_with_colon_is_quoted(self):
        # Colon-leading scalars (like ":1984") must be quoted in YAML or the
        # parser splits them as key: value.
        out = gg.render_yaml([], "cam", ":1984", ":8554")
        self.assertIn('listen: ":1984"', out)

    def test_url_with_at_sign_is_quoted(self):
        # '@' is in our quoting set because YAML reserves it.
        out = gg.render_yaml(
            ["rtsp://u:p@host/x"], "cam", "0.0.0.0:1984", "0.0.0.0:8554",
        )
        self.assertIn('cam1: "rtsp://u:p@host/x"', out)

    def test_plain_listen_address_not_quoted(self):
        out = gg.render_yaml([], "cam", "0.0.0.0:1984", "127.0.0.1:8554")
        self.assertIn("listen: 0.0.0.0:1984", out)
        self.assertIn("listen: 127.0.0.1:8554", out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

class CliTests(unittest.TestCase):
    def test_two_valid_urls(self):
        r = _run([], stdin_text="rtsp://1.1.1.1/a\nrtsp://2.2.2.2/b\n")
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        self.assertIn("cam1: rtsp://1.1.1.1/a", r.stdout)
        self.assertIn("cam2: rtsp://2.2.2.2/b", r.stdout)
        self.assertEqual(r.stderr, "")

    def test_one_valid_one_invalid(self):
        r = _run([], stdin_text="rtsp://ok/a\nhttp://nope/b\n")
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        self.assertIn("cam1: rtsp://ok/a", r.stdout)
        self.assertNotIn("cam2", r.stdout)
        self.assertIn("skipped non-RTSP line: http://nope/b", r.stderr)

    def test_empty_stdin(self):
        r = _run([], stdin_text="")
        self.assertEqual(r.returncode, 4)
        self.assertIn("no RTSP URLs on stdin", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_only_invalid(self):
        r = _run([], stdin_text="http://x\nfoo\n")
        self.assertEqual(r.returncode, 4)
        self.assertIn("no valid RTSP URLs on stdin", r.stderr)

    def test_custom_prefix(self):
        r = _run(["--name-prefix", "recorder"],
                 stdin_text="rtsp://a\nrtsp://b\n")
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        self.assertIn("recorder1: rtsp://a", r.stdout)
        self.assertIn("recorder2: rtsp://b", r.stdout)

    def test_output_file(self):
        with tempfile.TemporaryDirectory() as d:
            target = os.path.join(d, "g.yaml")
            r = _run(["-o", target], stdin_text="rtsp://1.1.1.1/a\n")
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            self.assertEqual(r.stdout, "")
            with open(target) as f:
                content = f.read()
            self.assertIn("cam1: rtsp://1.1.1.1/a", content)
            self.assertTrue(content.startswith("api:\n"))

    def test_output_unwritable(self):
        r = _run(["-o", "/nonexistent-dir-xyz/g.yaml"],
                 stdin_text="rtsp://a\n")
        self.assertEqual(r.returncode, 1)
        self.assertIn("could not write", r.stderr)

    def test_custom_listen_addrs(self):
        r = _run(["--api-listen", "127.0.0.1:9000",
                  "--rtsp-listen", "0.0.0.0:9554"],
                 stdin_text="rtsp://a\n")
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        self.assertIn("listen: 127.0.0.1:9000", r.stdout)
        self.assertIn("listen: 0.0.0.0:9554", r.stdout)

    def test_order_preserved(self):
        urls = [f"rtsp://10.0.0.{i}/x" for i in (5, 1, 9, 2)]
        r = _run([], stdin_text="\n".join(urls) + "\n")
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        for i, url in enumerate(urls, start=1):
            self.assertIn(f"cam{i}: {url}", r.stdout)

    def test_yaml_is_parseable_when_pyyaml_present(self):
        try:
            import yaml  # type: ignore
        except ImportError:
            self.skipTest("pyyaml not installed")
        r = _run([], stdin_text=(
            "rtsp://anonymous/a\n"
            "rtsp://u:p@host:554/path?q=1\n"
        ))
        self.assertEqual(r.returncode, 0, msg=r.stderr)
        doc = yaml.safe_load(r.stdout)
        self.assertEqual(doc["api"]["listen"], ":1984")
        self.assertEqual(doc["rtsp"]["listen"], ":8554")
        self.assertEqual(
            doc["streams"],
            {"cam1": "rtsp://anonymous/a",
             "cam2": "rtsp://u:p@host:554/path?q=1"},
        )

    def test_version(self):
        r = _run(["-V"])
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), f"{gg.PROG} {gg.VERSION}")

    def test_help(self):
        r = _run(["-h"])
        self.assertEqual(r.returncode, 0)
        self.assertIn("go2rtc.yaml", r.stdout)
        self.assertEqual(r.stderr, "")


if __name__ == "__main__":
    unittest.main()
