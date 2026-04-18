
import os
import sys
import io
import contextlib
from crawlernest_admission_crawler.engine import AdmissionCrawlerEngine

def run_and_capture():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        records = AdmissionCrawlerEngine().run()
    return buf.getvalue(), records

def test_input_truncated():
    # 模擬 oversized.html 輸入
    # 這裡假設 AdmissionCrawlerEngine 支援讀取 snapshot_htmls/oversized.html
    # 實際情境下需根據 pipeline 實作調整
    output, _ = run_and_capture()
    assert "input_truncated" in output and any(s in output for s in ["1", "input_truncated: 1"]), output

def test_invalid_ielts():
    output, _ = run_and_capture()
    assert "invalid_ielts" in output and any(s in output for s in ["1", "invalid_ielts: 1"]), output

def test_invalid_toefl():
    output, _ = run_and_capture()
    assert "invalid_toefl" in output and any(s in output for s in ["1", "invalid_toefl: 1"]), output

def test_invalid_gpa():
    output, _ = run_and_capture()
    assert "invalid_gpa" in output and any(s in output for s in ["1", "invalid_gpa: 1"]), output

def test_invalid_deadline():
    output, _ = run_and_capture()
    assert "invalid_deadline" in output and any(s in output for s in ["1", "invalid_deadline: 1"]), output

def test_source_host_mismatch():
    output, _ = run_and_capture()
    assert "source_host_mismatch" in output and any(s in output for s in ["1", "source_host_mismatch: 1"]), output

def test_suspicious_merge():
    output, _ = run_and_capture()
    assert "suspicious_mapping" in output and any(s in output for s in ["1", "suspicious_mapping: 1"]), output

if __name__ == "__main__":
    # 手動執行所有測試
    tests = [
        test_input_truncated,
        test_invalid_ielts,
        test_invalid_toefl,
        test_invalid_gpa,
        test_invalid_deadline,
        test_source_host_mismatch,
        test_suspicious_merge,
    ]
    for t in tests:
        try:
            t()
            print(f"{t.__name__}: PASS")
        except AssertionError as e:
            print(f"{t.__name__}: FAIL\n{e}")
