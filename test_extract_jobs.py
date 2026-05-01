import pytest
from datetime import datetime
from extract_jobs import JobExtractor

def test_target_monday_logic():
    extractor = JobExtractor("https://example.com")
    
    # Monday, 2026-04-27 -> should target 2026-04-27
    dt_mon = datetime(2026, 4, 27)
    assert extractor.get_target_monday(dt_mon).isoformat() == "2026-04-27"
    
    # Wednesday, 2026-04-29 -> should target 2026-04-27
    dt_wed = datetime(2026, 4, 29)
    assert extractor.get_target_monday(dt_wed).isoformat() == "2026-04-27"
    
    # Thursday, 2026-04-30 -> should target NEXT Monday 2026-05-04
    dt_thu = datetime(2026, 4, 30)
    assert extractor.get_target_monday(dt_thu).isoformat() == "2026-05-04"
    
    # Friday, 2026-05-01 -> should target NEXT Monday 2026-05-04
    dt_fri = datetime(2026, 5, 1)
    assert extractor.get_target_monday(dt_fri).isoformat() == "2026-05-04"

def test_markdown_formatting():
    extractor = JobExtractor("https://example.com")
    jobs = [
        {'title': 'Job 1', 'link': 'http://link1'},
        {'title': 'Job 2', 'link': 'http://link2'}
    ]
    output = extractor.format_as_markdown(jobs)
    assert "* **[Job 1](http://link1)**" in output
    assert "* **[Job 2](http://link2)**" in output
    assert "\n" in output

def test_empty_jobs_markdown():
    extractor = JobExtractor("https://example.com")
    assert extractor.format_as_markdown([]) == "No jobs found for the specified period."
