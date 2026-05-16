"""Tests for shared URL canonicalization."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.url_utils import canonicalize_url, has_tracking_params


def test_canonicalize_url_removes_tracking_params_and_fragment():
    url = (
        "https://glints.com/id/opportunities/jobs/frontend/abc"
        "?utm_referrer=explore&traceInfo=xyz&utm_source=ddg&foo=1#section"
    )

    canonical = canonicalize_url(url)

    assert canonical == "https://glints.com/id/opportunities/jobs/frontend/abc?foo=1"
    assert has_tracking_params(url)
    assert not has_tracking_params(canonical)
