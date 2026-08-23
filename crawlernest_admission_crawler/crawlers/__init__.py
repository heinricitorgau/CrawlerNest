"""Crawlers are no longer defined here.

This package held ExampleUniversityCrawler: one hardcoded MIT record that stood
in for the real crawler while nothing connected the two admission packages.
crawl_bridge drives crawlernest/crawlernest-admission-crawler now, so the
stand-in is deleted rather than left somewhere it could be wired back in.
"""

__all__: list[str] = []
