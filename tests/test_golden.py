import json

import pytest

from golden_harness import case_dirs, run_case


@pytest.mark.parametrize("case_dir", case_dirs(), ids=lambda p: p.name)
def test_golden(case_dir):
    expected = json.loads((case_dir / "expected.json").read_text(encoding="utf-8"))
    assert run_case(case_dir) == expected
