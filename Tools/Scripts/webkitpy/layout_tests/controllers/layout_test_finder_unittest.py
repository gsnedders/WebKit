# Copyright (C) 2024 Apple Inc. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
# 1.  Redistributions of source code must retain the above copyright
#     notice, this list of conditions and the following disclaimer.
# 2.  Redistributions in binary form must reproduce the above copyright
#     notice, this list of conditions and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY APPLE INC. AND ITS CONTRIBUTORS ``AS IS'' AND ANY
# EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL APPLE INC. OR ITS CONTRIBUTORS BE LIABLE FOR ANY
# DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

import logging
import posixpath
import unittest
from collections import OrderedDict
from unittest import mock

from pyfakefs.fake_filesystem import OSType

from webkitpy.common.host_mock import MockHost
from webkitpy.common.system.fakefs_testcase import (
    PyFakefsLinuxTestCaseMixin,
    PyFakefsMacOSTestCaseMixin,
    PyFakefsWindowsTestCaseMixin,
)
from webkitpy.common.system.filesystem import FileSystem
from webkitpy.layout_tests.controllers import layout_test_finder
from webkitpy.layout_tests.controllers.layout_test_finder import (
    LayoutTestFinder,
)
from webkitpy.layout_tests.models.server_routing import ServerRoute, ServerType
from webkitpy.layout_tests.models.test import test_name_and_variant
from webkitpy.port.test import (
    TestPort,
    add_unit_tests_to_mock_filesystem,
)


class LayoutTestFinderTestsBase(object):
    def __init__(self, *args, **kwargs):
        super(LayoutTestFinderTestsBase, self).__init__(*args, **kwargs)
        self.port = None
        self.finder = None

    def setUp(self):
        self.setUpPyfakefs()
        host = MockHost(create_stub_repository_files=True, filesystem=FileSystem())
        add_unit_tests_to_mock_filesystem(host.filesystem)
        self.port = TestPort(host)
        self.finder = LayoutTestFinder(
            self.port.host.filesystem,
            self.port.layout_tests_dir(),
            self.port.baseline_search_path(),
            test_routes=self.port.test_routes(),
        )

    def tearDown(self):
        self.port = None
        self.finder = None

    def test_emulated_os(self):
        self.assertEqual(self.fs.os, self.fs_os)
        expected_sep = "\\" if self.fs_os == OSType.WINDOWS else "/"
        self.assertEqual(self.port.host.filesystem.sep, expected_sep)

    def test_test_routes_prefixes_use_forward_slashes(self):
        # test_file_dir is compared as a string against "/"-separated test
        # names, so it must not use the host separator.
        for route in self.port.test_routes():
            self.assertNotIn("\\", route.test_file_dir)

    def test_split_glob(self):
        v = list(self.finder._split_glob("a"))
        self.assertEqual([("", "a", "")], v)

        v = list(self.finder._split_glob("a/"))
        self.assertEqual([("a", "", "")], v)

        v = list(self.finder._split_glob("a/b"))
        self.assertEqual([("a", "b", "")], v)

        v = list(self.finder._split_glob("a/b/"))
        self.assertEqual([("a/b", "", "")], v)

        v = list(self.finder._split_glob("a/b/c"))
        self.assertEqual([("a/b", "c", "")], v)

        v = list(self.finder._split_glob("a/b#c"))
        self.assertEqual([("a", "b", "#c")], v)

        v = list(self.finder._split_glob("a/b?c"))
        self.assertEqual([("a", "b", "?c"), ("a", "b?c", "")], v)

        v = list(self.finder._split_glob("a/b?c?d"))
        self.assertEqual(
            [("a", "b", "?c?d"), ("a", "b?c", "?d"), ("a", "b?c?d", "")], v
        )

        v = list(self.finder._split_glob("a/b?c#d"))
        self.assertEqual([("a", "b", "?c#d"), ("a", "b?c", "#d")], v)

        v = list(self.finder._split_glob("a/?b"))
        self.assertEqual([("a", "?b", "")], v)

        v = list(self.finder._split_glob("a/?b?c"))
        self.assertEqual([("a", "?b", "?c"), ("a", "?b?c", "")], v)

        v = list(self.finder._split_glob("a?b"))
        self.assertEqual([("", "a", "?b"), ("", "a?b", "")], v)

        v = list(self.finder._split_glob("a??b"))
        self.assertEqual([("", "a", "??b"), ("", "a?", "?b"), ("", "a??b", "")], v)

        v = list(self.finder._split_glob("a?b?c"))
        self.assertEqual([("", "a", "?b?c"), ("", "a?b", "?c"), ("", "a?b?c", "")], v)

        v = list(self.finder._split_glob("a/#b"))
        self.assertEqual([], v)

        v = list(self.finder._split_glob("a/b?c/d"))
        self.assertEqual([("a", "b", "?c/d"), ("a/b?c", "d", "")], v)

        v = list(self.finder._split_glob("a/b#c/d"))
        self.assertEqual([("a", "b", "#c/d")], v)

    def test_split_glob_agrees_with_test_name_and_variant(self):
        # Every way of writing a variant must be split into the same file and
        # variant by _split_glob as by test_name_and_variant, since one is
        # used to find tests on disk and the other to name them.
        for name in (
            "a/b.html?x",
            "a/b.html#x",
            "a/b.html?x#y",
            "a/b.html#x?y",
            "a/b.html?x?y",
            "a/b.html?",
            "a/b.html#",
            "a/b.html?x/y",
            "a/b.html#x/y",
            "a/b.html?x#y/z",
            "a/b.html?a%20b",
            "a.b/c.d/e.html?x",
        ):
            with self.subTest(name):
                file_path, variant = test_name_and_variant(name)
                dirname, basename = posixpath.split(file_path)
                self.assertIn((dirname, basename, variant), list(self.finder._split_glob(name)))

    def test_get_tests__double_star_glob(self):
        self.assertTestsFound(
            ['**/*test-crash-crash*'],
            ['imported/w3c/web-platform-tests/some/test-crash-crash.html'],
        )

    def test_generated_js_sources_are_only_tests_under_wpt_roots(self):
        any_js = '// META: global=window\ntest(() => {}, "pass");\n'
        self._add_test_file('fast/foo/bar.any.js', any_js)
        self._add_test_file('fast/foo/bar.window.js', any_js)
        self._add_test_file('fast/foo/bar.worker.js', any_js)
        self._add_test_file('imported/w3c/web-platform-tests/foo/bar.any.js', any_js)

        self.assertTestsFound(['fast/foo'], [])
        self.assertTestsFound(
            ['imported/w3c/web-platform-tests/foo'],
            ['imported/w3c/web-platform-tests/foo/bar.any.html'],
        )

    def _add_test_file(self, path, contents=''):
        fs = self.port.host.filesystem
        full_path = fs.join(self.port.layout_tests_dir(), path)
        fs.maybe_make_directory(fs.dirname(full_path))
        fs.write_text_file(full_path, contents)

    def assertTestsFound(self, queries, expected_paths):
        tests = list(self.finder.get_tests(queries))
        self.assertEqual([t.test_path for t in tests], expected_paths)
        return tests


class LayoutTestFinderLinuxTests(PyFakefsLinuxTestCaseMixin, LayoutTestFinderTestsBase, unittest.TestCase):
    pass


class LayoutTestFinderWindowsTests(PyFakefsWindowsTestCaseMixin, LayoutTestFinderTestsBase, unittest.TestCase):
    pass


class LayoutTestFinderMacOSTests(PyFakefsMacOSTestCaseMixin, LayoutTestFinderTestsBase, unittest.TestCase):
    pass


class WptTestsForPathTestsBase(object):
    """Tests for _wpt_tests_for_path dispatch on item_type."""

    WPT_PREFIX = "imported/w3c/web-platform-tests"
    WPT_URL_BASE = "/"

    def setUp(self):
        self.setUpPyfakefs()
        host = MockHost(create_stub_repository_files=True, filesystem=FileSystem())
        add_unit_tests_to_mock_filesystem(host.filesystem)
        self.port = TestPort(host)
        self.filesystem = self.port.host.filesystem
        self.layout_tests_dir = self.port.layout_tests_dir()
        self.test_routes = [
            ServerRoute(self.WPT_PREFIX, self.WPT_URL_BASE, ServerType.WPT),
        ]
        self.finder = LayoutTestFinder(
            self.filesystem,
            self.layout_tests_dir,
            self.port.baseline_search_path(),
            test_routes=self.test_routes,
        )

    def tearDown(self):
        self.port = None
        self.finder = None
        self.filesystem = None

    def test_emulated_os(self):
        self.assertEqual(self.fs.os, self.fs_os)
        expected_sep = "\\" if self.fs_os == OSType.WINDOWS else "/"
        self.assertEqual(self.filesystem.sep, expected_sep)

    def _write_wpt_file(self, rel_path, contents):
        """Write a file under the WPT prefix, return its absolute path."""
        # WPT_PREFIX and rel_path use "/", so normalise to the host separator
        # to match the paths the finder reports.
        abs_path = self.filesystem.normpath(self.filesystem.join(self.layout_tests_dir, self.WPT_PREFIX, rel_path))
        self.filesystem.maybe_make_directory(self.filesystem.dirname(abs_path))
        self.filesystem.write_text_file(abs_path, contents)
        return abs_path

    def _get_wpt_tests(self, rel_path, variants=None):
        """Run _wpt_tests_for_path for a file under the WPT prefix."""
        parts = rel_path.rsplit("/", 1)
        if len(parts) == 2:
            dirname = self.WPT_PREFIX + "/" + parts[0]
            basename = parts[1]
        else:
            dirname = self.WPT_PREFIX
            basename = parts[0]
        from collections import OrderedDict
        non_test_files = OrderedDict()
        layout_dir = self.filesystem.join(self.layout_tests_dir, dirname)
        files = set()
        if self.filesystem.isdir(layout_dir):
            for entry in self.filesystem.scandir(layout_dir):
                if entry.is_file():
                    files.add(entry.name)
        non_test_files[layout_dir] = files
        return list(self.finder._wpt_tests_for_path(dirname, basename, variants, non_test_files))

    # -----------------------------------------------------------------------
    # Test: jsshell variant is skipped
    # -----------------------------------------------------------------------
    def test_any_js_jsshell_variant_skipped(self):
        """TestharnessTest with jsshell=True must not yield a Test."""
        # An .any.js declaring global=window,jsshell produces two items:
        # one for the .any.html window variant, and one for jsshell (.any.js URL).
        # Only the window variant should appear.
        self._write_wpt_file("blob/Blob-bytes.any.js", "// META: global=window,jsshell\ntest(() => {}, 'blob');\n")
        tests = self._get_wpt_tests("blob/Blob-bytes.any.js")
        test_paths = [t.test_path for t in tests]
        # jsshell URL is the .any.js source itself — must not appear
        self.assertNotIn(self.WPT_PREFIX + "/blob/Blob-bytes.any.js", test_paths)
        # The .any.html window variant must appear
        self.assertIn(self.WPT_PREFIX + "/blob/Blob-bytes.any.html", test_paths)

    # -----------------------------------------------------------------------
    # Test: manual item type yields nothing
    # -----------------------------------------------------------------------
    def test_manual_file_yields_nothing(self):
        """-manual.window.js files produce a 'manual' item_type — yield nothing."""
        self._write_wpt_file("foo/test-manual.window.js", "// META: global=window\ntest(() => {}, 'manual');\n")
        tests = self._get_wpt_tests("foo/test-manual.window.js")
        self.assertEqual(tests, [])

    # -----------------------------------------------------------------------
    # Test: HTML support file → no Test yielded, warning fires
    # -----------------------------------------------------------------------
    def test_html_support_file_warns_and_yields_nothing(self):
        """Pure HTML support file under WPT root: no Test, warning logged."""
        self._write_wpt_file("foo/helper.html", "<html><body>helper</body></html>\n")
        with self.assertLogs("webkitpy.layout_tests.controllers.layout_test_finder", level=logging.WARNING) as cm:
            tests = self._get_wpt_tests("foo/helper.html")
        self.assertEqual(tests, [])
        self.assertTrue(any("helper.html" in msg for msg in cm.output),
                        "Expected warning mentioning helper.html")

    # -----------------------------------------------------------------------
    # Test: .any.js produces expected .any.html and .any.worker.html Tests
    # -----------------------------------------------------------------------
    def test_any_js_produces_html_and_worker_variants(self):
        """A basic .any.js (global=window,worker) yields .any.html and .any.worker.html Tests."""
        self._write_wpt_file("foo/basic.any.js", "// META: global=window,worker\ntest(() => {}, 'pass');\n")
        tests = self._get_wpt_tests("foo/basic.any.js")
        test_paths = sorted(t.test_path for t in tests)
        self.assertIn(self.WPT_PREFIX + "/foo/basic.any.html", test_paths)
        self.assertIn(self.WPT_PREFIX + "/foo/basic.any.worker.html", test_paths)
        # All tests should be WPT server type
        for t in tests:
            self.assertEqual(t.served_by, ServerType.WPT)

    # -----------------------------------------------------------------------
    # Test: variant with spaces is percent-encoded in test_path
    # -----------------------------------------------------------------------
    def test_window_js_variant_with_spaces_is_percent_encoded(self):
        """A .window.js with '// META: variant=?foo bar' must yield a Test
        whose test_path ends with '?foo%20bar' (percent-encoded), and the
        baseline lookup must resolve to the canonical '…_foo_20bar-expected.txt'
        on-disk filename.
        """
        from collections import OrderedDict

        # Write the .window.js source with a variant that contains a space.
        self._write_wpt_file(
            "foo/test.window.js",
            "// META: variant=?foo bar\ntest(() => {}, 'pass');\n",
        )

        # Write a baseline file using the canonical on-disk form: space → %20
        # via _percent_encoded_variant, then % → _ via sanitized_variant.
        # So "?foo bar" → "?foo%20bar" → sanitized "foo_20bar" →
        # baseline "test.window_foo_20bar-expected.txt".
        baseline_filename = "test.window_foo_20bar-expected.txt"
        dirname = self.WPT_PREFIX + "/foo"
        layout_dir = self.filesystem.join(self.layout_tests_dir, dirname)
        self.filesystem.maybe_make_directory(layout_dir)
        self.filesystem.write_text_file(
            self.filesystem.join(layout_dir, baseline_filename),
            "PASS\n",
        )

        # Build non_test_files: include layout dir (with test file + baseline).
        non_test_files = OrderedDict()
        files = set()
        for entry in self.filesystem.scandir(layout_dir):
            if entry.is_file():
                files.add(entry.name)
        non_test_files[layout_dir] = files

        tests = list(
            self.finder._wpt_tests_for_path(dirname, "test.window.js", None, non_test_files)
        )

        # Should produce exactly one test (the .window.html variant with encoded query).
        self.assertEqual(len(tests), 1, f"Expected 1 test, got {len(tests)}: {[t.test_path for t in tests]}")
        t = tests[0]

        # test_path must carry the percent-encoded variant.
        self.assertTrue(
            t.test_path.endswith("?foo%20bar"),
            f"Expected test_path to end with '?foo%20bar', got: {t.test_path!r}",
        )

        # Baseline lookup must resolve to the canonical on-disk file.
        self.assertIsNotNone(
            t.expected_text_path,
            "Expected a non-None expected_text_path (baseline should be found on disk)",
        )
        self.assertTrue(
            t.expected_text_path.endswith(baseline_filename),
            f"Expected expected_text_path to end with {baseline_filename!r}, got: {t.expected_text_path!r}",
        )

    def test_reftest_fuzzy_keyed_by_relative_path(self):
        """Fuzzy dict keys must be relative-to-test-dir strings, not abs paths."""
        self._write_wpt_file(
            "foo/reftest.html",
            '<html><head>'
            '<link rel=match href="some-ref.html">'
            '<meta name="fuzzy" content="some-ref.html:0-5;0-100">'
            '</head></html>\n'
        )
        # Create the reference file so it resolves on disk
        self._write_wpt_file("foo/some-ref.html", "<html><body>ref</body></html>\n")

        tests = self._get_wpt_tests("foo/reftest.html")
        self.assertEqual(len(tests), 1)
        t = tests[0]
        self.assertIsNotNone(t.fuzzy)
        # The key must be the relative path from the test's directory.
        # (A later change in this series keys by absolute reference path
        # instead, and rewrites this test accordingly.)
        self.assertIn("some-ref.html", t.fuzzy,
                      f"Expected 'some-ref.html' key in fuzzy dict, got: {list(t.fuzzy.keys())}")
        # Must NOT be an absolute path key
        abs_keys = [k for k in t.fuzzy if k is not None and k.startswith("/")]
        self.assertEqual(abs_keys, [], f"Found absolute path key(s) in fuzzy dict: {abs_keys}")

    def test_reftest_prefers_sibling_over_manifest_ref(self):
        """When a reftest's manifest ref AND an imported `<stem>-expected.<ext>`
        sibling both exist on disk, the sibling must win — the WebKit WPT
        importer hand-tweaks the imported sibling for WebKit-specific
        rendering quirks, so TestExpectations is calibrated against the
        sibling, not the upstream manifest ref."""
        self._write_wpt_file(
            "foo/reftest.html",
            '<html><head>'
            '<link rel=match href="upstream-ref.html">'
            '</head></html>\n'
        )
        # Manifest target — resolves on disk
        self._write_wpt_file("foo/upstream-ref.html", "<html><body>upstream</body></html>\n")
        # Imported sibling — what TestExpectations is calibrated against
        self._write_wpt_file("foo/reftest-expected.html", "<html><body>imported</body></html>\n")

        tests = self._get_wpt_tests("foo/reftest.html")
        self.assertEqual(len(tests), 1)
        t = tests[0]
        self.assertIsNotNone(t.reference_files)
        ref_paths = [ref.path for ref in t.reference_files]
        # Sibling must win
        self.assertTrue(
            any(p.endswith("reftest-expected.html") for p in ref_paths),
            f"Expected sibling reftest-expected.html in references, got: {ref_paths}",
        )
        # Manifest ref must NOT appear
        self.assertFalse(
            any(p.endswith("upstream-ref.html") for p in ref_paths),
            f"Manifest ref upstream-ref.html should be overridden by sibling, got: {ref_paths}",
        )

    # -----------------------------------------------------------------------
    # Regression test for fixup 4: stub-recognition pre-filter removal
    # -----------------------------------------------------------------------
    def test_paired_any_html_stub_triggers_support_warning_via_process_directory(self):
        """When a .any.js source and its .any.html stub both exist in a WPT
        directory, the stub must reach the dispatcher and fire the 'support'
        audit warning.

        Pre-fixup-4: the pre-filter in _process_directory dropped the stub
        before it reached _wpt_tests_for_path → no warning.
        Post-fixup-4: the stub reaches the dispatcher, is classified as
        'support', and the warning fires.
        """
        # Write the .any.js source (produces .any.html and .any.worker.html tests).
        self._write_wpt_file(
            "blob/Blob-bytes.any.js",
            "// META: global=window,worker\ntest(() => {}, 'blob');\n",
        )
        # Write the paired .any.html stub (generated by the WPT importer).
        # Real WPT importer stubs are comment-only files with no testharness.js,
        # so SourceFile classifies them as 'support'.
        self._write_wpt_file(
            "blob/Blob-bytes.any.html",
            "<!-- This file is required for WebKit test infrastructure to run the templated test -->\n",
        )

        dirname = self.WPT_PREFIX + "/blob"

        with self.assertLogs("webkitpy.layout_tests.controllers.layout_test_finder", level=logging.WARNING) as cm:
            items = list(self.finder._process_directory(dirname))

        # The stub itself is not run as a test; only the generated variants are.
        self.assertEqual(
            sorted(t.test_path for t in items),
            [
                self.WPT_PREFIX + "/blob/Blob-bytes.any" + suffix
                for suffix in (".html", ".serviceworker.html", ".sharedworker.html", ".worker.html")
            ],
        )

        # The 'support' warning must mention the stub filename.
        self.assertTrue(
            any("Blob-bytes.any.html" in msg for msg in cm.output),
            "Expected 'support' warning mentioning Blob-bytes.any.html; got: " + str(cm.output),
        )

    # -----------------------------------------------------------------------
    # Exception narrowing around SourceFile.manifest_items()
    # -----------------------------------------------------------------------
    def test_manifest_items_value_error_is_skipped(self):
        """SourceFile.manifest_items() raising ValueError (malformed fuzzy,
        malformed reference keys, print reftests without refs, etc.) is
        treated as 'skip this file', not a discovery-aborting failure."""
        self._write_wpt_file("foo/malformed.html", "<html></html>\n")
        with mock.patch.object(
            layout_test_finder.SourceFile, "manifest_items", side_effect=ValueError("bad fuzzy value")
        ):
            tests = self._get_wpt_tests("foo/malformed.html")
        self.assertEqual(tests, [])

    def test_manifest_items_other_exception_propagates(self):
        """A non-ValueError from SourceFile.manifest_items() must propagate,
        rather than being silently swallowed like the old `except Exception`."""
        self._write_wpt_file("foo/broken.html", "<html></html>\n")
        with mock.patch.object(
            layout_test_finder.SourceFile, "manifest_items", side_effect=RuntimeError("boom")
        ):
            with self.assertRaises(RuntimeError):
                self._get_wpt_tests("foo/broken.html")

    def test_malformed_wpt_files_are_skipped_with_a_warning(self):
        """One real file per `raise ValueError` site in SourceFile; none is mocked."""
        ref = '<link rel=match href="ref.html">'
        for description, rel_path, head in (
            ("fuzzy key is not a reference", "foo/a.html", ref + '<meta name=fuzzy content="other-ref.html:0-1;0-1">'),
            ("malformed fuzzy value", "foo/b.html", ref + '<meta name=fuzzy content="1">'),
            ("invalid fuzzy property", "foo/c.html", ref + '<meta name=fuzzy content="foo=1;2">'),
            ("duplicate fuzzy property", "foo/d.html", ref + '<meta name=fuzzy content="maxDifference=1;maxDifference=2">'),
            ("non-integer fuzzy range", "foo/e.html", ref + '<meta name=fuzzy content="a;1">'),
            (
                "duplicate page-ranges",
                "print/f.html",
                ref + '<meta name=reftest-pages content="1"><meta name=reftest-pages content="2">',
            ),
            ("malformed page-range", "print/g.html", ref + '<meta name=reftest-pages content="a-b">'),
            ("zero page-range", "print/h.html", ref + '<meta name=reftest-pages content="0-1">'),
            ("single non-integer page-range", "print/i.html", ref + '<meta name=reftest-pages content="x">'),
            ("print reftest without references", "print/j.html", ""),
        ):
            with self.subTest(description):
                self._write_wpt_file(rel_path, "<html><head>%s</head></html>\n" % head)
                self._write_wpt_file(rel_path.rsplit("/", 1)[0] + "/ref.html", "<html></html>\n")
                with self.assertLogs("webkitpy.layout_tests.controllers.layout_test_finder", level=logging.WARNING) as cm:
                    tests = self._get_wpt_tests(rel_path)
                self.assertEqual(tests, [])
                self.assertTrue(
                    any("Skipping WPT file" in msg and rel_path in msg for msg in cm.output),
                    "Expected a warning naming %s, got: %s" % (rel_path, cm.output),
                )

    def test_unreadable_file_falls_back_to_sourcefile_read(self):
        self._write_wpt_file("foo/plain.html", '<script src="/resources/testharness.js"></script>\n')
        for error in (IOError("gone"), UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")):
            with self.subTest(type(error).__name__):
                with mock.patch.object(self.filesystem, "read_binary_file", side_effect=error):
                    tests = self._get_wpt_tests("foo/plain.html")
                self.assertEqual([t.test_path for t in tests], [self.WPT_PREFIX + "/foo/plain.html"])

    def test_only_requested_variants_are_returned(self):
        self._write_wpt_file(
            "foo/test.window.js",
            "// META: variant=?a\n// META: variant=?b\n// META: variant=?c\ntest(() => {}, 'pass');\n",
        )
        self.assertEqual(
            [t.test_path for t in self._get_wpt_tests("foo/test.window.js")],
            [self.WPT_PREFIX + "/foo/test.window.html" + v for v in ("?a", "?b", "?c")],
        )
        self.assertEqual(
            [t.test_path for t in self._get_wpt_tests("foo/test.window.js", variants=["?b"])],
            [self.WPT_PREFIX + "/foo/test.window.html?b"],
        )
        self.assertEqual(self._get_wpt_tests("foo/test.window.js", variants=["?zzz"]), [])

    def test_reftest_uses_manifest_reference_when_there_is_no_sibling(self):
        self._write_wpt_file("foo/reftest.html", '<link rel=match href="manifest-ref.html">\n')
        ref_path = self._write_wpt_file("foo/manifest-ref.html", "<html></html>\n")
        (test,) = self._get_wpt_tests("foo/reftest.html")
        self.assertEqual([(r.relation, r.path) for r in test.reference_files], [("==", ref_path)])

    def test_reftest_with_missing_manifest_reference_and_no_sibling_warns(self):
        self._write_wpt_file("foo/reftest.html", '<link rel=match href="missing-ref.html">\n')
        with self.assertLogs("webkitpy.layout_tests.controllers.layout_test_finder", level=logging.WARNING) as cm:
            (test,) = self._get_wpt_tests("foo/reftest.html")
        self.assertIsNone(test.reference_files)
        self.assertTrue(
            any("manifest reference(s) missing" in msg and "missing-ref.html" in msg for msg in cm.output),
            cm.output,
        )

    def test_reftest_drops_only_the_missing_manifest_references(self):
        self._write_wpt_file(
            "foo/reftest.html",
            '<link rel=match href="present-ref.html"><link rel=mismatch href="missing-ref.html">\n',
        )
        present = self._write_wpt_file("foo/present-ref.html", "<html></html>\n")
        (test,) = self._get_wpt_tests("foo/reftest.html")
        self.assertEqual([(r.relation, r.path) for r in test.reference_files], [("==", present)])

    def test_url_base_other_than_root(self):
        finder = LayoutTestFinder(
            self.filesystem,
            self.layout_tests_dir,
            self.port.baseline_search_path(),
            test_routes=[ServerRoute("http/wpt", "/WebKit/", ServerType.WPT)],
        )
        abs_path = self.filesystem.join(self.layout_tests_dir, "http/wpt/foo/bar.html")
        self.filesystem.maybe_make_directory(self.filesystem.dirname(abs_path))
        self.filesystem.write_text_file(abs_path, '<script src="/resources/testharness.js"></script>\n')
        tests = list(finder.get_tests(["http/wpt/foo"]))
        self.assertEqual([t.test_path for t in tests], ["http/wpt/foo/bar.html"])
        self.assertEqual(tests[0].served_by, ServerType.WPT)

        self.assertEqual(finder._wpt_url_to_test_path("/WebKit/foo/bar.html?x", "http/wpt", "/WebKit/"), "http/wpt/foo/bar.html?x")
        self.assertIsNone(finder._wpt_url_to_test_path("/other/foo/bar.html", "http/wpt", "/WebKit/"))
        self.assertIsNone(finder._wpt_url_to_test_path("relative/bar.html", "http/wpt", "/WebKit/"))

    def test_discovery_through_tests_for_path_dispatches_on_wpt_route(self):
        self._write_wpt_file("foo/basic.any.js", "// META: global=window,worker\ntest(() => {}, 'pass');\n")
        dirname = self.WPT_PREFIX + "/foo"
        tests = list(self.finder._tests_for_path(dirname, "basic.any.js", None, OrderedDict()))
        self.assertEqual(
            sorted(t.test_path for t in tests),
            [
                self.WPT_PREFIX + "/foo/basic.any" + suffix
                for suffix in (".html", ".serviceworker.html", ".sharedworker.html", ".worker.html")
            ],
        )
        for t in tests:
            self.assertEqual(t.served_by, ServerType.WPT)


class WptTestsForPathLinuxTests(PyFakefsLinuxTestCaseMixin, WptTestsForPathTestsBase, unittest.TestCase):
    pass


class WptTestsForPathWindowsTests(PyFakefsWindowsTestCaseMixin, WptTestsForPathTestsBase, unittest.TestCase):
    pass


class WptTestsForPathMacOSTests(PyFakefsMacOSTestCaseMixin, WptTestsForPathTestsBase, unittest.TestCase):
    pass
