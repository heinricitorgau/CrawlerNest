#!/usr/bin/env python3
"""
QS University Rankings Crawler - Demonstration Script

This script demonstrates the crawler's basic functionality as described in README.md.
It fetches the TOP 5 world ranking universities and displays them in the console.
"""

from crawler import run_crawler

def run_demo():
    print("\nSelect ranking type:")
    print("1. World Ranking")
    print("2. Subject Ranking")
    print("3. Regional Ranking")
    print("\nTop Universities (sample)\n")
    
    # Run a small world ranking crawl for demonstration
    run_crawler(
        ranking_id="3990755", # World 2025
        output_format='console',
        ranking_limit=5,
        use_async=False,
        show_progress=True
    )

if __name__ == "__main__":
    try:
        run_demo()
    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
    except Exception as e:
        print(f"\nError: {e}")
