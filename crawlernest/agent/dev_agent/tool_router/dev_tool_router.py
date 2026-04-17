from __future__ import annotations

from crawlernest.agent.tools.dev_tools import DevTools
from crawlernest.agent.tools.ranking_tools import RankingTools
from crawlernest.agent.tools.recommendation_tools import RecommendationTools
from crawlernest.agent.tools.university_tools import UniversityTools


class DevToolRouter:
    def __init__(self) -> None:
        self.ranking_tools = RankingTools()
        self.recommendation_tools = RecommendationTools()
        self.university_tools = UniversityTools()
        self.dev_tools = DevTools()
