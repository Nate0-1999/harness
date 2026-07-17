"""Reserved H2 contract-test entry point; P0 asserts no Spine behavior."""

import pytest

pytestmark = pytest.mark.contract


def test_spine_contract_is_reserved_for_h2() -> None:
    pytest.skip("H2 implements live Spine contract assertions")
