"""Tests untuk Listing Parser module."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.listing_parser import (
    detect_platform,
    is_listing_url,
    is_listing_title,
    classify_page,
    DeallsAdapter,
    KalibrrAdapter,
    GlintsAdapter,
    JobstreetAdapter,
    LokerIdAdapter,
    ProspleAdapter,
    IndeedAdapter,
    GenericAdapter,
)


def test_detect_platform():
    assert detect_platform("https://dealls.com/loker") == "dealls"
    assert detect_platform("https://glints.com/id/en/find-jobs") == "glints"
    assert detect_platform("https://www.jobstreet.co.id/id/jobs") == "jobstreet"
    assert detect_platform("https://www.kalibrr.id/id-ID/job-board") == "kalibrr"
    assert detect_platform("https://www.loker.id/tipe-pekerjaan/magang") == "lokerid"
    assert detect_platform("https://id.prosple.com/lowongan-magang-indonesia") == "prosple"
    assert detect_platform("https://id.indeed.com/q-internship-lowongan.html") == "indeed"
    assert detect_platform("https://random-site.com/jobs") == "generic"
    print("[PASS] detect_platform")


def test_is_listing_url():
    # Listing URLs
    assert is_listing_url("https://dealls.com/loker") is True
    assert is_listing_url("https://dealls.com/loker/") is True
    assert is_listing_url("https://dealls.com/loker/industri") is True
    assert is_listing_url("https://dealls.com/loker/lokasi") is True
    assert is_listing_url("https://dealls.com/loker/posisi") is True
    assert is_listing_url("https://dealls.com/loker/tipe/loker-magang") is True
    assert is_listing_url("https://dealls.com/loker/populer") is True
    assert is_listing_url("https://glints.com/id/en/find-jobs/frontend") is True
    assert is_listing_url("https://www.kalibrr.id/id-ID/job-board") is True
    assert is_listing_url("https://www.jobstreet.co.id/id/frontend-developer-internship-jobs") is True
    assert is_listing_url("https://www.loker.id/tipe-pekerjaan/magang") is True
    assert is_listing_url("https://id.prosple.com/lowongan-magang-indonesia") is True
    assert is_listing_url("https://id.indeed.com/q-internship-lowongan.html") is True

    # Detail URLs — NOT listing
    assert is_listing_url("https://dealls.com/loker/frontend-intern~pt-example") is False
    assert is_listing_url("https://glints.com/id/en/opportunities/jobs/frontend/123") is False
    assert is_listing_url("https://www.kalibrr.id/id-ID/c/company/jobs/123/slug") is False
    assert is_listing_url("https://www.loker.id/lowongan-kerja/frontend-intern") is False
    assert is_listing_url("https://id.indeed.com/viewjob?jk=abc123") is False
    print("[PASS] is_listing_url")


def test_is_listing_title():
    assert is_listing_title("Explore Jobs | Dealls") is True
    assert is_listing_title("Job Vacancy & Opportunities in Indonesia") is True
    assert is_listing_title("Lowongan kerja di Indonesia - Cari Lowongan Kerja") is True
    assert is_listing_title("5 pekerjaan Software Engineer Intern di Jakarta Raya, Indonesia") is True
    assert is_listing_title("Frontend Developer Intern - PT Example") is False
    assert is_listing_title("") is False
    assert is_listing_title(None) is False
    print("[PASS] is_listing_title")


def test_classify_page():
    assert classify_page("https://dealls.com/loker") == "listing"
    assert classify_page("https://dealls.com/loker/frontend-intern~pt-example") == "detail"
    assert classify_page("https://random.com/page", "Explore Jobs | Site") == "listing"
    assert classify_page("https://random.com/page", "Frontend Intern at Company") == "detail"
    print("[PASS] classify_page")


def test_dealls_adapter():
    adapter = DeallsAdapter()
    assert adapter.needs_playwright() is False

    # Simulate SSR HTML
    html = """
    <html><body>
        <a href="/loker/frontend-intern~pt-example">Frontend Intern</a>
        <a href="/loker/backend-dev~pt-company">Backend Dev</a>
        <a href="/loker/industri">Industri</a>
        <a href="/loker/lokasi">Lokasi</a>
        <a href="/loker/posisi">Posisi</a>
        <a href="/loker/tipe/loker-magang">Magang</a>
        <a href="/loker/populer">Populer</a>
        <a href="/loker">Semua Loker</a>
    </body></html>
    """
    links = adapter.extract_detail_links("https://dealls.com/loker", html)
    assert len(links) == 2, f"Expected 2 detail links, got {len(links)}"
    urls = [l.url for l in links]
    assert "https://dealls.com/loker/frontend-intern~pt-example" in urls
    assert "https://dealls.com/loker/backend-dev~pt-company" in urls
    print(f"[PASS] DeallsAdapter -> {len(links)} links")


def test_kalibrr_adapter():
    adapter = KalibrrAdapter()
    assert adapter.needs_playwright() is False

    html = """
    <html><body>
        <a href="/id-ID/c/company-a/jobs/12345/frontend-dev">Frontend Dev</a>
        <a href="/id-ID/c/company-b/jobs/67890/backend-dev">Backend Dev</a>
        <a href="/id-ID/home">Home</a>
        <a href="/id-ID/employers">Employers</a>
    </body></html>
    """
    links = adapter.extract_detail_links("https://www.kalibrr.id/id-ID/job-board", html)
    assert len(links) == 2, f"Expected 2 detail links, got {len(links)}"
    print(f"[PASS] KalibrrAdapter -> {len(links)} links")


def test_glints_adapter():
    adapter = GlintsAdapter()
    assert adapter.needs_playwright() is True

    # Simulate rendered HTML
    html = """
    <html><body>
        <a href="/id/en/opportunities/jobs/frontend-dev/abc123">Frontend Dev</a>
        <a href="/id/en/opportunities/jobs/backend-dev/def456">Backend Dev</a>
        <a href="/id/en/find-jobs/all">All Jobs</a>
    </body></html>
    """
    links = adapter.extract_detail_links("https://glints.com/id/en/find-jobs", html)
    assert len(links) == 2, f"Expected 2 detail links, got {len(links)}"
    print(f"[PASS] GlintsAdapter -> {len(links)} links")


def test_glints_adapter_extracts_script_state_links():
    adapter = GlintsAdapter()
    html = r"""
    <html><body>
      <script id="__NEXT_DATA__" type="application/json">
      {"props":{"jobs":[{"url":"\/id\/en\/opportunities\/jobs\/software-engineer-intern\/abc123"}]}}
      </script>
    </body></html>
    """
    links = adapter.extract_detail_links("https://glints.com/id/en/find-jobs/loker-magang-internship", html)
    assert len(links) == 1
    assert links[0].url == "https://glints.com/id/en/opportunities/jobs/software-engineer-intern/abc123"
    print("[PASS] GlintsAdapter script-state links")


def test_jobstreet_adapter():
    adapter = JobstreetAdapter()
    assert adapter.needs_playwright() is True

    html = """
    <html><body>
        <a href="/id/job/12345">Frontend Job</a>
        <a href="/id/job/67890">Backend Job</a>
        <a href="/id/frontend-developer-internship-jobs">Listing</a>
    </body></html>
    """
    links = adapter.extract_detail_links("https://www.jobstreet.co.id/id/jobs", html)
    assert len(links) == 2, f"Expected 2 detail links, got {len(links)}"
    print(f"[PASS] JobstreetAdapter -> {len(links)} links")


def test_jobstreet_adapter_extracts_script_state_links():
    adapter = JobstreetAdapter()
    html = r"""
    <html><body>
      <script>
      window.__STATE__ = {"results":[{"url":"\/id\/job\/software-engineer-intern-78910"}]};
      </script>
    </body></html>
    """
    links = adapter.extract_detail_links("https://www.jobstreet.co.id/id/software-engineer-internship-jobs", html)
    assert len(links) == 1
    assert links[0].url == "https://www.jobstreet.co.id/id/job/software-engineer-intern-78910"
    print("[PASS] JobstreetAdapter script-state links")


def test_jobstreet_adapter_extracts_card_company():
    adapter = JobstreetAdapter()
    html = """
    <html><body>
      <article data-testid="job-card" data-job-id="91761487">
        <a data-automation="jobTitle" href="/job/91761487?type=standard">Software Engineer Internship</a>
        <a data-automation="jobCompany" href="/OPPO-jobs">OPPO Indonesia</a>
      </article>
    </body></html>
    """
    links = adapter.extract_detail_links("https://id.jobstreet.com/web-developer-internship-jobs", html)
    assert len(links) == 1
    assert links[0].title == "Software Engineer Internship"
    assert links[0].company == "OPPO Indonesia"
    assert links[0].discovery_method == "card"


def test_tier2_adapters():
    loker_html = """
    <html><body>
        <a href="/lowongan-kerja/frontend-developer-intern">Frontend Intern</a>
        <a href="/tipe-pekerjaan/magang">Magang listing</a>
    </body></html>
    """
    loker_links = LokerIdAdapter().extract_detail_links(
        "https://www.loker.id/tipe-pekerjaan/magang", loker_html
    )
    assert len(loker_links) == 1

    prosple_html = """
    <html><body>
        <a href="/graduate-employers/example/jobs-internships/software-engineer-intern">Software Intern</a>
        <a href="/graduate-employers/example/graduate-jobs-internships/data-analyst-intern">Data Intern</a>
        <a href="/lowongan-magang-indonesia">Listing</a>
    </body></html>
    """
    prosple_links = ProspleAdapter().extract_detail_links(
        "https://id.prosple.com/lowongan-magang-indonesia", prosple_html
    )
    assert len(prosple_links) == 2

    indeed_html = """
    <html><body>
        <a href="/viewjob?jk=abc123">IT Intern</a>
        <a href="/q-internship-lowongan.html">Listing</a>
    </body></html>
    """
    indeed_links = IndeedAdapter().extract_detail_links(
        "https://id.indeed.com/q-internship-lowongan.html", indeed_html
    )
    assert len(indeed_links) == 1
    print("[PASS] Tier 2 adapters")


def test_prosple_adapter_extracts_script_state_links():
    html = r"""
    <html><body>
      <script>
      window.__STATE__ = {"url":"\/graduate-employers\/example\/jobs-internships\/qa-intern"};
      </script>
    </body></html>
    """
    links = ProspleAdapter().extract_detail_links(
        "https://id.prosple.com/lowongan-magang-indonesia", html
    )
    assert len(links) == 1
    assert links[0].url == "https://id.prosple.com/graduate-employers/example/jobs-internships/qa-intern"
    print("[PASS] ProspleAdapter script-state links")


if __name__ == "__main__":
    test_detect_platform()
    test_is_listing_url()
    test_is_listing_title()
    test_classify_page()
    test_dealls_adapter()
    test_kalibrr_adapter()
    test_glints_adapter()
    test_glints_adapter_extracts_script_state_links()
    test_jobstreet_adapter()
    test_jobstreet_adapter_extracts_script_state_links()
    test_tier2_adapters()
    test_prosple_adapter_extracts_script_state_links()
    print("\n[OK] All listing_parser tests passed!")
