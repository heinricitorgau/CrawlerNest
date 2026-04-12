from crawlernest_admission_crawler.engine import AdmissionCrawlerEngine
from crawlernest_ranking_crawler.engine import RankingCrawlerEngine


if __name__ == "__main__":
    print("=== Ranking Engine ===")
    for record in RankingCrawlerEngine().run():
        print(record)

    print("\n=== Admission Engine ===")
    for record in AdmissionCrawlerEngine().run():
        print(record)
