# Crawl Quality Summary Printer
# 輕量級 CLI summary，供 pipeline 結尾呼叫

def print_crawl_quality_summary(summary):
    print("===== Crawl Quality Summary =====")
    print(f"total_records: {summary.get('total_records', 0)}")
    print("anomalies:")
    for k, v in summary.get('anomalies', {}).items():
        print(f"  {k}: {v}")
    print("resolution:")
    for k, v in summary.get('resolution', {}).items():
        print(f"  {k}: {v}")
