"""Regression tests for calendar / internal release tag helpers.

Run from repository root:

    python3 -m unittest discover -s scripts -p test_release_tag_mapping.py -v

CI: .github/workflows/scripts-release-tag-tests.yaml runs the same command.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import date
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_APP_RELEASE = _SCRIPTS / "app-release"


def _load_script(module_name: str, relative_path: str):
    path = _SCRIPTS / relative_path
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


chore_release = _load_script("_chore_release_under_test", "app-release/chore-release.py")
internal_release = _load_script(
    "_internal_release_under_test", "app-release/internal-release.py"
)

sys.path.insert(0, str(_SCRIPTS))
import python_build_utils as python_build_utils  # noqa: E402
import ot2_calendar_semver as ot2_calendar_semver  # noqa: E402


class TestChoreReleaseIncrementTag(unittest.TestCase):
    def test_calendar_alpha_bump(self):
        self.assertEqual(
            chore_release.increment_tag("v26.4@alpha.6", "alpha"),
            "v26.4@alpha.7",
        )

    def test_calendar_stable_to_next_alpha(self):
        self.assertEqual(
            chore_release.increment_tag("v26.4", "alpha"),
            "v26.5@alpha.0",
        )

    def test_parse_chore_release_branch_external(self):
        self.assertEqual(
            chore_release.parse_chore_release_branch("chore_release-26.6.0"),
            (26, 6, 0),
        )

    def test_parse_chore_release_branch_internal_dnn(self):
        self.assertEqual(
            chore_release.parse_chore_release_branch("chore_release-26.5.2601"),
            (26, 5, 2601),
        )


class TestInternalReleaseHelpers(unittest.TestCase):
    def test_opentrons_calendar_tag_regex_accepts(self):
        cal = internal_release.OPENTRONS_CALENDAR_TAG_RE
        for t in (
            "internal@26.5.2601",
            "internal@26.5.2602-alpha",
            "internal@26.5.101",
        ):
            with self.subTest(tag=t):
                self.assertIsNotNone(cal.match(t), t)

    def test_get_next_tag_alpha(self):
        self.assertEqual(
            internal_release.get_next_tag(
                None, "internal_alpha", "2.8.0", 6
            ),
            "internal@2.8.0-alpha.6",
        )


class TestOt2InternalSemver(unittest.TestCase):
    def test_encode_decode_may_26(self):
        self.assertEqual(
            ot2_calendar_semver.encode_ot2_internal_version(2026, 5, 26, 1),
            "26.5.2601",
        )
        self.assertEqual(
            ot2_calendar_semver.decode_ot2_internal_version("26.5.2601-alpha"),
            (2026, 5, 26, 1, "alpha"),
        )

    def test_allocate_next_internal_tag(self):
        existing = {
            "internal@26.5.2601-alpha",
            "internal@26.5.2601",
        }
        tag = ot2_calendar_semver.allocate_next_internal_tag(
            existing,
            "alpha",
            release_date=date(2026, 5, 26),
        )
        self.assertEqual(tag, "internal@26.5.2602-alpha")


class TestOt2ExternalSemver(unittest.TestCase):
    def test_encode_decode_june_first(self):
        self.assertEqual(
            ot2_calendar_semver.encode_ot2_external_version(2026, 6, 0),
            "26.6.0",
        )
        self.assertEqual(
            ot2_calendar_semver.decode_ot2_external_version("26.6.0-alpha.0"),
            (2026, 6, 0, "alpha", 0),
        )

    def test_allocate_next_external_stable(self):
        existing = {"v26.6.0", "v26.6.1"}
        tag = ot2_calendar_semver.allocate_next_external_tag(
            existing,
            "stable",
            release_date=date(2026, 6, 15),
        )
        self.assertEqual(tag, "v26.6.2")

    def test_allocate_next_external_alpha(self):
        existing = {"v26.6.0-alpha.0", "v26.6.0"}
        tag = ot2_calendar_semver.allocate_next_external_tag(
            existing,
            "alpha",
            base_version="26.6.0",
            release_date=date(2026, 6, 15),
        )
        self.assertEqual(tag, "v26.6.0-alpha.1")


class TestPythonBuildUtilsRobotStackInternal(unittest.TestCase):
    def test_pep440_internal(self):
        self.assertEqual(
            python_build_utils._pep440_from_git_version(
                "robot-stack-internal", "26.5.2601-alpha"
            ),
            "26.5.2601-alpha",
        )

    def test_pep440_external(self):
        self.assertEqual(
            python_build_utils._pep440_from_git_version("robot-stack", "26.6.0-alpha.0"),
            "26.6.0-alpha.0",
        )


if __name__ == "__main__":
    unittest.main()
