"""Per-university admission crawl profiles.

Each profile lists candidate URLs to attempt in order.  The crawler tries
each URL until it gets a usable response or exhausts the list.

URL selection heuristic
-----------------------
Prefer a dedicated "English language requirements" or "admission requirements"
page over the general admissions homepage.  Specific pages contain structured
data (IELTS bands, TOEFL scores) and far less navigation noise.

Adding a new university
-----------------------
1. Add a ``UniversityProfile`` to ``UNIVERSITY_PROFILES``.
2. List at least one candidate URL.  List up to 3 in priority order.
3. If the university does not require IELTS/TOEFL (e.g. wholly domestic),
   set ``expects_language_score=False`` so the evaluator knows this.
4. Set ``country``. Entity resolution uses it to block candidates, and a
   missing one is the difference between a confident match and a fuzzy one
   that needs a person -- the page itself never states it.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class UniversityProfile:
    name: str                           # Canonical display name
    base_url: str                       # Root domain (for CrawlReport)
    candidate_urls: list[str]           # Try in order; stop at first success
    country: str = ""                   # Country hint for entity resolution
    degree_level_hint: str = "postgraduate"   # Expected degree level of page
    expects_language_score: bool = True       # False for domestic-only schools
    notes: str = ""                     # Human-readable notes for maintainers


UNIVERSITY_PROFILES: dict[str, UniversityProfile] = {
    "ucl": UniversityProfile(
        name="UCL (University College London)",
        base_url="https://www.ucl.ac.uk",
        candidate_urls=[
            "https://www.ucl.ac.uk/prospective-students/graduate/taught-degrees/english-language-requirements",
            "https://www.ucl.ac.uk/prospective-students/graduate/research-degrees/english-language-requirements",
        ],
        country="United Kingdom",
        notes="UCL has separate pages for taught and research degrees.",
    ),
    "melbourne": UniversityProfile(
        name="University of Melbourne",
        base_url="https://study.unimelb.edu.au",
        candidate_urls=[
            "https://study.unimelb.edu.au/admissions/english-language-requirements",
            "https://study.unimelb.edu.au/admissions",
        ],
        country="Australia",
        notes="Melbourne publishes a unified ELR page covering all postgrad programs.",
    ),
    "toronto": UniversityProfile(
        name="University of Toronto",
        base_url="https://www.utoronto.ca",
        candidate_urls=[
            "https://www.sgs.utoronto.ca/applicants/english-language-requirements/",
            "https://www.sgs.utoronto.ca/applicants/how-to-apply/",
        ],
        country="Canada",
        notes="SGS page covers all graduate programs. TOEFL minimum is 93.",
    ),
    "nus": UniversityProfile(
        name="National University of Singapore",
        base_url="https://nus.edu.sg",
        candidate_urls=[
            "https://nusgs.nus.edu.sg/admissions/english-language/",
            "https://nusgs.nus.edu.sg/admissions/",
        ],
        country="Singapore",
        notes="NUS Graduate School covers Masters and PhD English requirements.",
    ),
    "manchester": UniversityProfile(
        name="University of Manchester",
        base_url="https://www.manchester.ac.uk",
        candidate_urls=[
            "https://www.manchester.ac.uk/study/international/entry-requirements/language/",
            "https://www.manchester.ac.uk/study/postgraduate/applications/requirements/",
        ],
        country="United Kingdom",
        notes="Manchester has a comprehensive language requirements page.",
    ),
    "oxford": UniversityProfile(
        name="University of Oxford",
        base_url="https://www.ox.ac.uk",
        candidate_urls=[
            "https://www.ox.ac.uk/admissions/graduate/applying-to-oxford/application-guide/tests",
            "https://www.ox.ac.uk/admissions/graduate/applying-to-oxford/application-guide",
        ],
        country="United Kingdom",
        notes="Oxford requires IELTS 7.0 for most graduate courses; 7.5 for some.",
    ),
    "imperial": UniversityProfile(
        name="Imperial College London",
        base_url="https://www.imperial.ac.uk",
        candidate_urls=[
            "https://www.imperial.ac.uk/study/application-guide/requirements/english-language/",
        ],
        country="United Kingdom",
        notes="Imperial uses tiered IELTS scores (6.5 / 7.0) depending on programme.",
    ),
    "mit": UniversityProfile(
        name="Massachusetts Institute of Technology",
        base_url="https://www.mit.edu",
        candidate_urls=[
            "https://gradadmissions.mit.edu/apply/english-language",
            "https://gradadmissions.mit.edu/apply/requirements",
        ],
        country="United States",
        expects_language_score=True,
        notes="MIT requires TOEFL or IELTS for non-native English speakers. Requirements vary by department.",
    ),
}
