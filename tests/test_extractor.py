"""Tests untuk Extractor module (refactored with quality gates)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import RawPage
from engine.extractor import (
    check_internship_title,
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


def test_internship_title_gate():
    """Title harus mengandung sinyal internship (word-boundary)."""
    assert check_internship_title("Frontend Developer Intern") is True
    assert check_internship_title("Magang Data Analyst") is True
    assert check_internship_title("Internship Backend Developer") is True
    assert check_internship_title("KOL Specialist") is False
    assert check_internship_title("Document Control") is False
    assert check_internship_title("Marketing Admin") is False
    # Word boundary: 'internasional' bukan 'intern'
    assert check_internship_title("Ganesha Utopia Internasional") is False
    assert check_internship_title("PT International Company") is False
    print("[PASS] internship title gate (word-boundary)")


def test_detect_internship_3tier():
    config = load_keywords()

    # Tier 1: sinyal di title
    is_intern, conf, src = detect_internship("Some description", "Frontend Intern at Company", config)
    assert is_intern is True
    assert src == "title"
    assert conf >= 80

    # Tier 2: job_type signal
    is_intern, conf, src = detect_internship("Job Type: Internship\nFrontend role", "Frontend Role", config)
    assert is_intern is True
    assert src == "job_type"

    # Tier 3: deskripsi
    is_intern, conf, src = detect_internship("Program magang untuk mahasiswa semester akhir", "Some Title", config)
    assert is_intern is True
    assert src == "description"

    # Negative: no signal
    is_intern, conf, src = detect_internship("Senior developer needed", "Senior Developer", config)
    assert is_intern is False
    print("[PASS] detect_internship 3-tier")


def test_detect_role_from_title_first():
    """Role harus dideteksi dari title dulu, bukan raw_text."""
    config = load_keywords()

    # Role ada di title
    role, conf = detect_role("Frontend Developer Intern - Company", "Some random description with react", config)
    assert role == "Frontend Developer"
    assert conf >= 90
    print(f"[PASS] detect_role from title -> {role} (conf={conf})")


def test_detect_role_no_false_positive():
    """KOL Specialist, Document Control, dll TIDAK boleh jadi tech/data role."""
    config = load_keywords()

    # KOL Specialist — BUKAN actuarial
    role, conf = detect_role("KOL Specialist", "Manage key opinion leaders for marketing", config)
    assert role is None, f"Expected None, got {role}"
    print("[PASS] KOL Specialist -> None (no false positive)")

    # Document Control — BUKAN backend
    role, conf = detect_role("Document Control", "Manage documents and filing system", config)
    assert role is None, f"Expected None, got {role}"
    print("[PASS] Document Control -> None")

    # Architect Intern — only if has backend keywords in title
    role, conf = detect_role("Architect Intern", "Design building architecture", config)
    assert role is None, f"Expected None, got {role}"
    print("[PASS] Architect Intern -> None")


def test_detect_role_from_description():
    """Fallback: role dari deskripsi awal jika tidak ada di title."""
    config = load_keywords()
    role, conf = detect_role("Lowongan Intern", "Dibutuhkan frontend developer yang menguasai React dan Vue", config)
    assert role == "Frontend Developer"
    assert 50 <= conf <= 80
    print(f"[PASS] detect_role from description -> {role} (conf={conf})")


def test_detect_location():
    config = load_keywords()
    loc = detect_location("Posisi ini berlokasi di Jakarta", config)
    assert loc == "Jakarta"
    print(f"[PASS] detect_location -> {loc}")


def test_detect_work_mode():
    assert detect_work_mode("Full remote position available") == "remote"
    assert detect_work_mode("Work from office required daily") == "onsite"
    assert detect_work_mode("Hybrid WFO/WFH schedule") == "hybrid"
    print("[PASS] detect_work_mode")


def test_strict_deadline():
    """Deadline hanya valid jika tanggal eksplisit."""
    assert detect_deadline("Deadline: 19 Mei 2026") is not None
    assert detect_deadline("Apply before 2026-05-19") is not None
    # Kalimat biasa tanpa tanggal harus None
    assert detect_deadline("Kami bekerja dengan deadline ketat") is None
    assert detect_deadline("No specific deadline mentioned") is None
    print("[PASS] strict deadline")


def test_strict_salary():
    """Salary hanya valid jika format Rp/IDR + angka masuk akal."""
    assert detect_salary("Uang saku Rp3.000.000/bulan") is not None
    assert detect_salary("IDR 5,000,000 per month") is not None
    assert detect_salary("3-5 juta per bulan") is not None
    # Noise harus None
    assert detect_salary("RP,") is None
    assert detect_salary("No salary info") is None
    print("[PASS] strict salary")


def test_strict_duration():
    """Duration harus angka + satuan yang masuk akal."""
    assert detect_duration("Durasi magang 3 bulan") is not None
    assert detect_duration("6 months internship") is not None
    # Angka aneh harus None
    assert detect_duration("We have 99 bulan experience") is None
    print("[PASS] strict duration")


def test_extract_opportunity_internship_only():
    """Non-internship page harus di-reject."""
    page = RawPage(
        url="https://dealls.com/loker/kol-specialist~company",
        title="KOL Specialist at Company",
        text_content="We are looking for a KOL specialist to manage marketing.",
        status_code=200,
        page_type="detail",
    )
    opp = extract_opportunity(page)
    assert opp is None, "Non-internship should be rejected"
    print("[PASS] non-internship rejected")


def test_extract_opportunity_valid_intern():
    """Valid internship harus berhasil diekstrak."""
    page = RawPage(
        url="https://dealls.com/loker/frontend-intern~pt-example",
        title="Frontend Developer Intern - PT Example",
        text_content="""
        Frontend Developer Intern
        PT Example Tech

        Program magang untuk mahasiswa semester akhir.
        Lokasi: Jakarta (Hybrid)
        Durasi: 3 bulan
        Uang saku: Rp3.000.000/bulan
        Deadline: 19 Mei 2026

        Kualifikasi:
        - Menguasai React dan Next.js
        """,
        status_code=200,
        page_type="detail",
    )
    opp = extract_opportunity(page)
    assert opp is not None
    assert opp.role == "Frontend Developer"
    assert opp.page_type == "detail"
    assert opp.extraction_status == "extracted"
    print(f"[PASS] valid intern -> role={opp.role}, conf={opp.confidence}")


if __name__ == "__main__":
    test_internship_title_gate()
    test_detect_internship_3tier()
    test_detect_role_from_title_first()
    test_detect_role_no_false_positive()
    test_detect_role_from_description()
    test_detect_location()
    test_detect_work_mode()
    test_strict_deadline()
    test_strict_salary()
    test_strict_duration()
    test_extract_opportunity_internship_only()
    test_extract_opportunity_valid_intern()
    print("\n[OK] All extractor tests passed!")
