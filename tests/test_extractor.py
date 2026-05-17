"""Tests untuk Extractor module — nested keywords, role confidence, false positive prevention."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import RawPage
from engine.extractor import (
    check_internship_title,
    check_targeted_internship_title,
    detect_internship,
    detect_role,
    detect_category,
    detect_location,
    detect_work_mode,
    detect_deadline,
    detect_salary,
    normalize_salary,
    detect_duration,
    detect_company,
    is_valid_company,
    check_suspicious_role,
    extract_all_with_rejections,
    extract_opportunity,
    extract_opportunity_with_rejection,
    load_keywords,
)


# === INTERNSHIP DETECTION ===

def test_internship_title_gate():
    """Word-boundary: 'intern' matches but 'internasional' does not."""
    assert check_internship_title("Frontend Developer Intern") is True
    assert check_internship_title("Magang Data Analyst") is True
    assert check_internship_title("Internship Backend Developer") is True
    assert check_internship_title("Apprentice Engineer") is True
    # Must NOT match
    assert check_internship_title("KOL Specialist") is False
    assert check_internship_title("Document Control") is False
    assert check_internship_title("Ganesha Utopia Internasional") is False
    assert check_internship_title("PT International Company") is False
    print("[PASS] internship title gate (word-boundary)")


def test_internship_strong_weak():
    config = load_keywords()

    # Strong signal in title
    ok, conf, src = detect_internship("Some desc", "Frontend Intern at Company", config)
    assert ok is True and src == "title_strong" and conf >= 80

    # Strong in description
    ok, conf, src = detect_internship(
        "Program magang untuk mahasiswa magang semester akhir",
        "Some Role", config
    )
    assert ok is True and conf >= 50

    # No signal
    ok, conf, src = detect_internship("Senior developer needed full time", "Senior Developer", config)
    assert ok is False

    # Hard reject
    ok, conf, src = detect_internship("Bootcamp online gratis", "Join Bootcamp", config)
    assert ok is False and src == "hard_reject"

    # Likely not job
    ok, conf, src = detect_internship("Some text", "Explore Jobs | Dealls", config)
    assert ok is False and src == "likely_not_job"

    print("[PASS] internship strong/weak detection")


def test_fulltime_no_intern_rejected():
    """Full-time Data Analyst tanpa kata intern/magang harus rejected."""
    config = load_keywords()
    ok, conf, src = detect_internship(
        "We are looking for a full-time data analyst to join our team",
        "Data Analyst",
        config,
    )
    # Should not pass — no intern signal, has non_internship_term in desc
    assert ok is False or conf < 60, f"Should reject: ok={ok}, conf={conf}, src={src}"
    print("[PASS] full-time without intern rejected")


def test_seniority_title_overrides_related_internship_noise():
    """Senior title should not become internship because related jobs mention internship."""
    config = load_keywords()
    ok, conf, src = detect_internship(
        "Senior Actuary role. Related jobs: actuarial internship, finance internship.",
        "Senior Actuary",
        config,
    )
    assert ok is False
    assert conf == 0
    assert src == "seniority_without_internship_title"


def test_prior_internship_requirement_does_not_make_job_an_internship():
    config = load_keywords()
    ok, conf, src = detect_internship(
        """
        You will be an entry level member of the actuarial team.
        What you bring: 0-1 years experience required; prior internship(s).
        Four-year degree required in Actuarial science.
        """,
        "Actuarial Analyst - Profitability Management",
        config,
    )
    assert ok is False
    assert src == "no_signal"


def test_targeted_internship_title_gate():
    assert check_targeted_internship_title("Actuarial Intern") is True
    assert check_targeted_internship_title("Actuarial Trainee") is True
    assert check_targeted_internship_title("Actuarial Analyst") is False


# === ROLE CLASSIFICATION ===

def test_role_frontend():
    config = load_keywords()
    role, conf = detect_role("Frontend Developer Intern - Company", "React and Vue skills required", config)
    assert role == "Frontend Developer", f"Expected Frontend Developer, got {role}"
    assert conf >= 70
    print(f"[PASS] Frontend Developer Intern -> {role} (conf={conf})")


def test_role_backend():
    config = load_keywords()
    role, conf = detect_role("Internship Back End Developer", "Node.js, Express, PostgreSQL", config)
    assert role == "Backend Developer", f"Expected Backend Developer, got {role}"
    assert conf >= 70
    print(f"[PASS] Back End Developer -> {role} (conf={conf})")


def test_role_data_analyst():
    config = load_keywords()
    role, conf = detect_role("Data Analyst Intern", "SQL, Power BI, dashboard analytics", config)
    assert role == "Data Analyst", f"Expected Data Analyst, got {role}"
    assert conf >= 70
    print(f"[PASS] Data Analyst Intern -> {role} (conf={conf})")


def test_role_actuarial():
    config = load_keywords()
    role, conf = detect_role("Actuarial Intern", "Pricing, reserving, insurance liability", config)
    assert role == "Actuarial", f"Expected Actuarial, got {role}"
    assert conf >= 70
    print(f"[PASS] Actuarial Intern -> {role} (conf={conf})")


def test_role_ui_ux():
    config = load_keywords()
    role, conf = detect_role("UI/UX Designer Intern", "Figma wireframe prototype user research", config)
    assert role == "UI/UX Designer", f"Expected UI/UX Designer, got {role}"
    assert conf >= 70
    print(f"[PASS] UI/UX Designer Intern -> {role} (conf={conf})")


def test_role_product():
    config = load_keywords()
    role, conf = detect_role("Product Manager Intern", "PRD user story backlog agile", config)
    assert role == "Product Manager", f"Expected Product Manager, got {role}"
    assert conf >= 70
    print(f"[PASS] Product Manager Intern -> {role} (conf={conf})")


def test_role_mobile():
    config = load_keywords()
    role, conf = detect_role("Android Developer Intern", "Kotlin, Jetpack Compose, Firebase", config)
    assert role == "Mobile Developer", f"Expected Mobile Developer, got {role}"
    assert conf >= 70
    print(f"[PASS] Android Developer Intern -> {role} (conf={conf})")


def test_role_software_engineering_generic():
    config = load_keywords()
    role, conf = detect_role("Software Engineer Intern", "Python API SQL Git", config)
    assert role == "Software Engineering", f"Expected Software Engineering, got {role}"
    assert conf >= 70

    role2, conf2 = detect_role("IT Intern", "Programming, database, debugging, Git", config)
    assert role2 == "Software Engineering", f"Expected Software Engineering, got {role2}"
    assert conf2 >= 70
    print(f"[PASS] generic software roles -> {role}, {role2}")


def test_role_qa_it_support_bi():
    config = load_keywords()
    qa_role, qa_conf = detect_role("QA Intern", "Test case, bug report, Postman API testing", config)
    assert qa_role == "Quality Assurance", f"Expected Quality Assurance, got {qa_role}"
    assert qa_conf >= 70

    support_role, support_conf = detect_role(
        "IT Support Intern",
        "Troubleshooting Windows network hardware ticketing",
        config,
    )
    assert support_role == "IT Support", f"Expected IT Support, got {support_role}"
    assert support_conf >= 70

    bi_role, bi_conf = detect_role(
        "Business Intelligence Intern",
        "SQL Power BI dashboard reporting KPI metrics",
        config,
    )
    assert bi_role == "Business Intelligence", f"Expected Business Intelligence, got {bi_role}"
    assert bi_conf >= 70
    print("[PASS] QA, IT Support, and BI roles")


# === FALSE POSITIVE PREVENTION ===

def test_kol_not_actuarial():
    config = load_keywords()
    role, conf = detect_role("KOL Specialist", "Manage key opinion leaders for marketing campaigns", config)
    assert role is None, f"KOL Specialist should be None, got {role}"
    print("[PASS] KOL Specialist -> None (not actuarial/data)")


def test_document_control_not_backend():
    config = load_keywords()
    role, conf = detect_role("Document Control", "Manage documents, filing system, compliance", config)
    assert role is None, f"Document Control should be None, got {role}"
    print("[PASS] Document Control -> None (not backend)")


def test_architect_intern_not_backend():
    config = load_keywords()
    role, conf = detect_role("Architect Intern", "Design building architecture and structural plans", config)
    assert role is None, f"Architect Intern should be None, got {role}"
    print("[PASS] Architect Intern -> None (not backend)")


def test_graphic_designer_not_frontend():
    config = load_keywords()
    role, conf = detect_role("Graphic Designer", "Create graphics using Photoshop and Illustrator", config)
    assert role is None, f"Graphic Designer should be None, got {role}"
    print("[PASS] Graphic Designer -> None (not frontend)")


def test_marketing_admin_not_data():
    config = load_keywords()
    role, conf = detect_role("Marketing Admin", "Support marketing team with admin tasks", config)
    assert role is None, f"Marketing Admin should be None, got {role}"
    print("[PASS] Marketing Admin -> None (not data)")


def test_procurement_not_tech():
    config = load_keywords()
    role, conf = detect_role("Procurement Officer", "Handle procurement and supplier management", config)
    assert role is None, f"Procurement should be None, got {role}"
    print("[PASS] Procurement -> None (not tech)")


# === SUSPICIOUS ROLE CHECK ===

def test_suspicious_roles():
    config = load_keywords()
    assert check_suspicious_role("KOL Specialist at Company", config) is not None
    assert check_suspicious_role("Host Livestreaming", config) is not None
    assert check_suspicious_role("Content Creator Intern", config) is not None
    assert check_suspicious_role("Frontend Developer Intern", config) is None
    print("[PASS] suspicious role detection")


# === LOCATION (grouped) ===

def test_location_grouped():
    config = load_keywords()
    loc, area = detect_location("Posisi ini berlokasi di Jakarta Selatan", config)
    assert loc is not None
    assert area == "jakarta_area"

    loc2, area2 = detect_location("Kantor di Bandung", config)
    assert loc2 is not None
    assert area2 == "west_java"

    loc3, area3 = detect_location("Remote Indonesia", config)
    assert loc3 == "Indonesia"
    assert area3 == "indonesia"

    print("[PASS] grouped location detection")


# === WORK MODE ===

def test_work_mode():
    config = load_keywords()
    assert detect_work_mode("Full remote position", config) == "remote"
    assert detect_work_mode("Work from office daily", config) == "onsite"
    assert detect_work_mode("Hybrid partly remote", config) == "hybrid"
    assert detect_work_mode("Magang Web Developer (WFH) hybrid discussion", config) == "remote"
    assert detect_work_mode("No info about mode", config) is None
    print("[PASS] work mode detection")


# === STRICT FIELDS ===

def test_strict_deadline():
    assert detect_deadline("Deadline: 19 Mei 2026") is not None
    assert detect_deadline("Apply before 2026-05-19") is not None
    assert detect_deadline("deadline ketat dalam tim") is None
    print("[PASS] strict deadline")


def test_strict_salary():
    assert detect_salary("Uang saku Rp3.000.000/bulan") is not None
    assert detect_salary("IDR 5,000,000") is not None
    assert detect_salary("3-5 juta per bulan") is not None
    assert detect_salary("Perusahaan tidak menampilkan gaji. 5 juta applicants viewed this job") is None
    assert detect_salary("RP,") is None
    assert detect_salary("No salary info") is None
    print("[PASS] strict salary")


def test_salary_normalization_for_dashboard():
    display, low, high = normalize_salary("Rp\n750.000", confidence=80)
    assert display == "Rp750.000"
    assert low == 750000
    assert high == 750000
    assert normalize_salary("Rp\n750.000", confidence=0) == (None, None, None)
    display, low, high = normalize_salary("3-5 juta", confidence=80)
    assert display == "Rp3.000.000 - Rp5.000.000"
    assert low == 3000000
    assert high == 5000000


def test_company_validation_and_title_fallback():
    bad = "Membantu pengembangan dan maintenance aplikasi berbasis .NET"
    title = "Lowongan Intern Full Stack Developer di Pt. BPOSeven Inovasi Indonesia (BENEMICA),  | Glints"
    assert not is_valid_company(bad)
    company = detect_company(bad, title)
    assert company == "Pt. BPOSeven Inovasi Indonesia (BENEMICA)"
    assert detect_company("Company: OPPO Indonesia", "Software Engineer Internship") == "OPPO Indonesia"
    assert detect_company("company: Business Web Solutions", "Web Developer Intern") == "Business Web Solutions"
    assert detect_company(
        "Company: PT MARVIO KREATIF VOYAGE Travel Agent & Digital Services Consultant",
        "Web Developer Intern",
    ) == "PT MARVIO KREATIF VOYAGE Travel Agent & Digital Services Consultant"
    assert detect_company(
        "Company: TIKTOK PTE LTD (TIKTOK)",
        "Backend Engineer Project Intern",
    ) == "TIKTOK PTE LTD (TIKTOK)"
    assert not is_valid_company("Indonesia | LinkedIn")
    assert not is_valid_company("Indonesia")
    assert detect_company(
        "",
        "Starpixel membuka lowongan Unity Game Developer Intern di Indonesia | LinkedIn",
    ) == "Starpixel"


def test_strict_duration():
    assert detect_duration("Durasi magang 3 bulan") is not None
    assert detect_duration("6 months internship") is not None
    assert detect_duration("We have 99 bulan experience") is None
    print("[PASS] strict duration")


# === FULL EXTRACTION ===

def test_extract_non_internship_rejected():
    page = RawPage(
        url="https://dealls.com/loker/kol-specialist~company",
        title="KOL Specialist at Company",
        text_content="We are looking for a KOL specialist to manage marketing.",
        status_code=200, page_type="detail",
    )
    opp = extract_opportunity(page)
    assert opp is None, "Non-internship should be rejected"
    print("[PASS] non-internship rejected")


def test_extract_rejection_reason():
    page = RawPage(
        url="https://dealls.com/loker/kol-specialist~company",
        title="KOL Specialist at Company",
        text_content="We are looking for a KOL specialist to manage marketing.",
        status_code=200, page_type="detail",
    )
    opp, rejection = extract_opportunity_with_rejection(page)
    assert opp is None
    assert rejection is not None
    assert rejection.rejection_reason.startswith("not_internship")
    assert rejection.url == page.url
    print(f"[PASS] rejection reason -> {rejection.rejection_reason}")


def test_extract_listing_rejection_reason():
    page = RawPage(
        url="https://dealls.com/loker",
        title="Explore Jobs | Dealls",
        text_content="Lowongan kerja di Indonesia",
        status_code=200, page_type="listing",
    )
    opp, rejection = extract_opportunity_with_rejection(page)
    assert opp is None
    assert rejection is not None
    assert rejection.rejection_reason == "listing_page"
    print("[PASS] listing rejection reason")


def test_extract_suspicious_intern_rejected():
    page = RawPage(
        url="https://example.com/jobs/content-creator-intern",
        title="Content Creator Intern",
        text_content="Program magang content creator social media affiliate campaign. Apply sekarang. Jakarta.",
        status_code=200, page_type="detail",
    )
    opp, rejection = extract_opportunity_with_rejection(page)
    assert opp is None
    assert rejection is not None
    assert rejection.rejection_reason.startswith("suspicious_role")
    print(f"[PASS] suspicious intern rejected -> {rejection.rejection_reason}")


def test_extract_valid_intern():
    page = RawPage(
        url="https://dealls.com/loker/frontend-intern~pt-example",
        title="Frontend Developer Intern - PT Example",
        text_content="""
        Frontend Developer Intern at PT Example Tech
        Program magang untuk mahasiswa semester akhir.
        Lokasi: Jakarta (Hybrid)
        Durasi: 3 bulan
        Uang saku: Rp3.000.000/bulan
        Deadline: 19 Mei 2026
        Skills: React, Next.js, TypeScript
        """,
        status_code=200, page_type="detail",
    )
    opp = extract_opportunity(page)
    assert opp is not None
    assert opp.role == "Frontend Developer"
    assert opp.role_confidence >= 60
    assert opp.is_internship is True
    assert opp.internship_confidence >= 60
    assert opp.category == "tech"
    print(f"[PASS] valid intern -> role={opp.role}, role_conf={opp.role_confidence}, intern_conf={opp.internship_confidence}")


def test_extract_architect_intern():
    """Architect Intern = is_internship=True, but role should NOT be Backend."""
    page = RawPage(
        url="https://dealls.com/loker/architect-intern~company",
        title="Lowongan Kerja Architect Intern di PT Cipta",
        text_content="""
        Architect Intern — PT Cipta Kota Makmur
        Program magang mahasiswa arsitektur.
        Lokasi: Jakarta
        """,
        status_code=200, page_type="detail",
    )
    opp = extract_opportunity(page)
    assert opp is not None, "Architect Intern should pass internship gate"
    assert opp.is_internship is True
    assert opp.role != "Backend Developer", f"Architect Intern should NOT be Backend, got {opp.role}"
    print(f"[PASS] Architect Intern -> role={opp.role} (not Backend)")


def test_targeted_actuarial_filter_accepts_only_actuarial():
    pages = [
        RawPage(
            url="https://glints.com/id/opportunities/jobs/pricing-valuation-actuary",
            title="Pricing & Valuation Internship (Actuary)",
            text_content="Internship program in reinsurance pricing valuation reserving IFRS 17.",
            status_code=200,
            page_type="detail",
        ),
        RawPage(
            url="https://glints.com/id/opportunities/jobs/legal-intern",
            title="Legal Internship",
            text_content="Legal internship for contract review and corporate documents.",
            status_code=200,
            page_type="detail",
        ),
        RawPage(
            url="https://glints.com/id/opportunities/jobs/senior-actuary",
            title="Senior Actuary",
            text_content="Senior actuary role. Related jobs: actuarial internship, internship program.",
            status_code=200,
            page_type="detail",
        ),
    ]

    opportunities, rejections = extract_all_with_rejections(pages, target_category="actuarial")

    assert len(opportunities) == 1
    assert opportunities[0].title == "Pricing & Valuation Internship (Actuary)"
    assert opportunities[0].category == "actuarial"

    reasons = {r.title: r.rejection_reason for r in rejections}
    assert reasons["Legal Internship"] == "out_of_scope_target:actuarial"
    assert reasons["Senior Actuary"].startswith("not_internship:seniority_without_internship_title")


def test_targeted_actuarial_rejects_non_internship_actuarial_analyst():
    page = RawPage(
        url="https://internal-careers.allianz.com/job/actuarial-analyst/1",
        title="Actuarial Analyst - Profitability Management",
        text_content="""
        Entry level actuarial role. What you bring: 0-1 years experience required;
        prior internship(s). Four-year degree required in Actuarial science.
        """,
        status_code=200,
        page_type="detail",
    )

    opportunities, rejections = extract_all_with_rejections([page], target_category="actuarial")

    assert opportunities == []
    assert rejections
    assert rejections[0].rejection_reason.startswith("not_internship")


def test_generic_mode_still_keeps_non_target_internships():
    page = RawPage(
        url="https://glints.com/id/opportunities/jobs/legal-intern",
        title="Legal Internship",
        text_content="Legal internship for contract review and corporate documents.",
        status_code=200,
        page_type="detail",
    )
    opportunities, rejections = extract_all_with_rejections([page])
    assert len(opportunities) == 1
    assert not rejections


def test_listing_title_rejected():
    """Titles like 'Lowongan Kerja Populer' and 'Explore Jobs' must be rejected."""
    config = load_keywords()

    ok1, _, src1 = detect_internship("Some text", "Lowongan Kerja Populer", config)
    # likely_not_job or no_signal
    assert ok1 is False, "Lowongan Kerja Populer should be rejected"

    ok2, _, src2 = detect_internship("Some text", "Explore Jobs | Dealls", config)
    assert ok2 is False, "Explore Jobs should be rejected"

    print("[PASS] listing titles rejected")


if __name__ == "__main__":
    # Internship
    test_internship_title_gate()
    test_internship_strong_weak()
    test_fulltime_no_intern_rejected()

    # Role (positive)
    test_role_frontend()
    test_role_backend()
    test_role_data_analyst()
    test_role_actuarial()
    test_role_ui_ux()
    test_role_product()
    test_role_mobile()
    test_role_software_engineering_generic()
    test_role_qa_it_support_bi()

    # False positive prevention
    test_kol_not_actuarial()
    test_document_control_not_backend()
    test_architect_intern_not_backend()
    test_graphic_designer_not_frontend()
    test_marketing_admin_not_data()
    test_procurement_not_tech()
    test_suspicious_roles()

    # Location & work mode
    test_location_grouped()
    test_work_mode()

    # Strict fields
    test_strict_deadline()
    test_strict_salary()
    test_strict_duration()

    # Full extraction
    test_extract_non_internship_rejected()
    test_extract_rejection_reason()
    test_extract_listing_rejection_reason()
    test_extract_suspicious_intern_rejected()
    test_extract_valid_intern()
    test_extract_architect_intern()
    test_listing_title_rejected()

    print("\n[OK] All extractor tests passed!")
