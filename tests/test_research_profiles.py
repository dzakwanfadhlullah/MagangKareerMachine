"""Tests for research profile capacity presets."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.research.profiles import get_research_profile


def test_normal_research_profile_v8_capacity():
    profile = get_research_profile("normal")

    assert profile["query_count"] >= 36
    assert profile["max_fetch"] >= 80
    assert profile["workers"] == 8
