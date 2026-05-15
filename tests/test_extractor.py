"""Tests untuk Extractor module."""

import sys
import os

# Tambah root project ke path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import RawPage
from engine.extractor import (
    detect_internship,
    detect_role,
    detect_location,
    detect_work_mode,
    detect_deadline,
    detect_salary,
    detect_duration,
    extract_opportunity,
    load_keywords,
)


def test_detect_internship_positive():
    config = load_keywords()
    text = "Kami membuka lowongan magang untuk posisi frontend developer"
    is_intern, confidence = detect_internship(text, config)
    assert is_intern is True
    assert confidence > 0
    print("[PASS] detect_internship positive")


def test_detect_internship_negative():
    config = load_keywords()
    text = "Ikuti bootcamp fullstack developer dengan biaya terjangkau"
    is_intern, confidence = detect_internship(text, config)
    assert is_intern is False
    print("[PASS] detect_internship negative (bootcamp)")


def test_detect_role():
    config = load_keywords()
    text = "Looking for React and Next.js frontend developer intern"
    role = detect_role(text, config)
    assert role == "Frontend Developer"
    print(f"[PASS] detect_role -> {role}")


def test_detect_location():
    config = load_keywords()
    text = "Posisi ini berlokasi di Jakarta dengan sistem hybrid"
    loc = detect_location(text, config)
    assert loc == "Jakarta"
    print(f"[PASS] detect_location -> {loc}")


def test_detect_work_mode():
    assert detect_work_mode("Full remote position") == "remote"
    assert detect_work_mode("Work from office required") == "onsite"
    assert detect_work_mode("Hybrid WFO/WFH") == "hybrid"
    print("[PASS] detect_work_mode")


def test_detect_deadline():
    assert detect_deadline("Apply before 19 Mei 2026") is not None
    assert detect_deadline("Deadline: 2026-05-19") is not None
    assert detect_deadline("Batas akhir 19/05/2026") is not None
    print("[PASS] detect_deadline")


def test_detect_salary():
    assert detect_salary("Uang saku Rp3.000.000/bulan") is not None
    assert detect_salary("3-5 juta per bulan") is not None
    assert detect_salary("This is unpaid internship") is not None
    print("[PASS] detect_salary")


def test_detect_duration():
    assert detect_duration("Durasi magang 3 bulan") is not None
    assert detect_duration("6 months internship") is not None
    print("[PASS] detect_duration")


def test_extract_opportunity():
    page = RawPage(
        url="https://example.com/jobs/frontend-intern",
        title="Frontend Developer Intern — PT Example Tech",
        text_content="""
        Frontend Developer Intern
        PT Example Tech

        Kami membuka lowongan magang untuk posisi Frontend Developer.
        Lokasi: Jakarta (Hybrid)
        Durasi: 3 bulan
        Uang saku: Rp3.000.000/bulan
        Deadline: 19 Mei 2026

        Kualifikasi:
        - Menguasai React dan Next.js
        - Mahasiswa semester akhir
        - Familiar dengan TypeScript

        Lamar sekarang di website kami.
        """,
        status_code=200,
    )

    opp = extract_opportunity(page)
    assert opp is not None
    assert opp.role is not None
    assert opp.confidence > 0
    print(f"[PASS] extract_opportunity -> title={opp.title}, role={opp.role}, confidence={opp.confidence}")


if __name__ == "__main__":
    test_detect_internship_positive()
    test_detect_internship_negative()
    test_detect_role()
    test_detect_location()
    test_detect_work_mode()
    test_detect_deadline()
    test_detect_salary()
    test_detect_duration()
    test_extract_opportunity()
    print("\n[OK] All extractor tests passed!")
