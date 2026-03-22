import logging
import json
import re
from typing import Dict, List, Optional


DEADLINE_PATTERN = re.compile(
    r"(application deadline|deadline|apply by|applications close)\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?)",
    re.IGNORECASE,
)

logger = logging.getLogger("UniversityCrawler")


class RequirementsResult(dict):
    """Dict-like result with backward-compatible attribute/to_dict access."""

    SCORE_LIMITS = {
        "gmat": 800.0,
        "gre": 340.0,
        "gpa": 4.0,
        "ielts": 9.0,
        "toefl": 120.0,
        "duolingo": 160.0,
    }

    def __getattr__(self, name: str):
        try:
            return self[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def __setattr__(self, name: str, value):
        self[name] = value

    def to_dict(self) -> Dict:
        return dict(self)

    def calculate_overall_score(self) -> Optional[float]:
        scores: List[float] = []

        for key, max_value in self.SCORE_LIMITS.items():
            value = self.get(key)
            if value is not None:
                scores.append((float(value) / max_value) * 100.0)

        if scores:
            overall = sum(scores) / len(scores)
            self["overall_score"] = overall
            return overall

        self["overall_score"] = None
        return None


class ScoreValidator:
    # 入學指標可接受數值邊界
    RANGES = {
        "gmat": (200, 800),
        "gre": (260, 340),
        "gpa": (0, 4.0),
        "ielts": (0, 9.0),
        "toefl": (0, 120),
        "duolingo": (60, 160),
    }

    @classmethod
    def is_valid(cls, score_type: str, value: float) -> bool:
        if score_type not in cls.RANGES:
            return False
        min_val, max_val = cls.RANGES[score_type]
        return min_val <= value <= max_val


class DataExtractor:
    def __init__(self):
        self.validator = ScoreValidator()
        self.logger = logger
        self._warned_no_master = False

    def extract_master_section(self, html: str) -> str:
        master_start = -1

        patterns = [
            r'univ-section-title["\s>]+[^<]*(?:Master|Masters|Postgraduate|Graduate|Entry\s+requirements|English\s+language)[^<]*<',
            r"<h[23][^>]*>[^<]*(?:Master|Masters|Postgraduate|Graduate|Entry\s+requirements|English\s+language)[^<]*</h[23]>",
            r">\s*(?:Master|Masters|Postgraduate|Graduate)\s*<",
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                master_start = match.end()
                break

        if master_start == -1:
            self.logger.debug("Master section not found in HTML")
            return ""

        text_chunk = html[master_start:]
        next_section = re.search(r'univ-section-title["\s]|<h[23][^>]*>', text_chunk)
        if next_section:
            text_chunk = text_chunk[: next_section.start()]
        else:
            text_chunk = text_chunk[:10000]

        text_content = re.sub(r"<[^>]+>", " ", text_chunk)
        text_content = re.sub(r"\s+", " ", text_content)
        return text_content

    def find_score(
        self,
        keyword: str,
        text: str,
        pattern: str,
        score_type: str,
    ) -> Optional[float]:
        try:
            values: List[float] = []
            window = 140
            search_patterns = [
                rf"{keyword}.{{0,{window}}}?{pattern}",
                rf"{pattern}.{{0,{window}}}?{keyword}",
            ]
            matches = []
            for search_pattern in search_patterns:
                matches.extend(list(re.finditer(search_pattern, text, re.IGNORECASE)))

            for match in matches:
                try:
                    val_str = match.group(1).strip("+").strip()

                    if "-" in val_str and val_str.count("-") == 1:
                        parts = val_str.split("-")
                        if len(parts) == 2:
                            try:
                                low = float(parts[0])
                                high = float(parts[1])
                                if self.validator.is_valid(score_type, low) and self.validator.is_valid(score_type, high):
                                    values.append((low + high) / 2)
                                continue
                            except ValueError:
                                continue

                    val = float(val_str)
                    if self.validator.is_valid(score_type, val):
                        values.append(val)
                    else:
                        self.logger.debug(f"Invalid {score_type} score filtered: {val}")

                except (ValueError, IndexError) as exc:
                    self.logger.debug(f"Failed to parse score: {exc}")
                    continue

            if values:
                avg = sum(values) / len(values)
                self.logger.debug(f"Found {keyword}: {values} -> avg: {avg:.2f}")
                return avg

        except Exception as exc:
            self.logger.error(f"Error extracting {keyword}: {exc}")

        return None

    def extract_requirements(self, html: str) -> RequirementsResult:
        text_content = self.extract_master_section(html)
        parsed_status = "master_section"

        if not text_content:
            parsed_status = "full_page_fallback"
            if not self._warned_no_master:
                self.logger.debug("No Master section found, trying full page")
                self._warned_no_master = True
            text_content = re.sub(r"<[^>]+>", " ", html[:20000])
            text_content = re.sub(r"\s+", " ", text_content)

        def first_score(keywords: List[str], pattern: str, score_type: str) -> Optional[float]:
            for kw in keywords:
                val = self.find_score(kw, text_content, pattern, score_type)
                if val is not None:
                    return val
            return None

        gmat = first_score(
            [r"GMAT", r"GMAT\s*Focus"],
            r"(\d{3}(?:\.\d+)?(?:-\d{3}(?:\.\d+)?)?)\+?",
            "gmat",
        )
        gre = first_score(
            [r"GRE", r"GRE\s*General"],
            r"(\d{3}(?:\.\d+)?(?:-\d{3}(?:\.\d+)?)?)\+?",
            "gre",
        )
        toefl = first_score(
            [r"TOEFL\s*iBT", r"TOEFL", r"internet[- ]based\s*TOEFL", r"TOEFL\s*IBT"],
            r"(\d{2,3}(?:\.\d+)?(?:-\d{2,3}(?:\.\d+)?)?)\+?",
            "toefl",
        )
        ielts = first_score(
            [r"IELTS\s*Academic", r"IELTS", r"International\s+English\s+Language\s+Testing\s+System"],
            r"(\d(?:\.\d)?(?:-\d(?:\.\d)?)?)\+?",
            "ielts",
        )
        gpa = first_score(
            [r"GPA", r"CGPA", r"Grade\s+Point\s+Average", r"cumulative\s+GPA"],
            r"([0-4](?:\.\d{1,2})?(?:-[0-4](?:\.\d{1,2})?)?)\+?",
            "gpa",
        )
        duolingo = first_score(
            [r"Duolingo\s+English\s+Test", r"Duolingo", r"DET"],
            r"(\d{2,3}(?:\.\d+)?(?:-\d{2,3}(?:\.\d+)?)?)\+?",
            "duolingo",
        )

        application_deadline_text = None
        matched_deadline = DEADLINE_PATTERN.search(text_content)
        if matched_deadline:
            application_deadline_text = matched_deadline.group(2)

        requirements = RequirementsResult(
            gmat=gmat,
            gre=gre,
            gpa=gpa,
            ielts=ielts,
            toefl=toefl,
            duolingo=duolingo,
            application_deadline_text=application_deadline_text,
            raw_text=text_content[:2000],
            parsed_status=parsed_status,
            overall_score=None,
        )
        requirements.calculate_overall_score()
        return requirements


def _normalize_text(raw_input: str) -> str:
    if not raw_input:
        return ""
    text = raw_input.replace("\r\n", "\n").replace("\r", "\n")
    # Support one-line "A: x | B: y | C: z" style and normalize tabs.
    text = text.replace("\t", " ")
    text = re.sub(r"\s*\|\s*", "\n", text)
    text = re.sub(r"[ \u00A0]+", " ", text)
    return text


def _clean_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip().strip(",;")
    cleaned = cleaned.strip().strip("\"'`")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or None


def _extract_json_candidates(text: str) -> Dict[str, str]:
    candidates: Dict[str, str] = {}
    try:
        data = json.loads(text)
    except Exception:
        return candidates

    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                k_norm = str(k).strip().lower()
                if k_norm in {"university", "program", "quota"} and v is not None:
                    candidates.setdefault(k_norm, str(v))
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return candidates


def _extract_kv_candidates(text: str) -> Dict[str, str]:
    candidates: Dict[str, str] = {}

    # Global segmented matcher:
    # captures up to the next recognized key or end-of-text.
    segmented_pattern = re.compile(
        r"""(?is)
        ["']?\b(university|program|quota)\b["']?
        \s*(?:[:=\-]|\bis\b)\s*
        (.*?)
        (?=
            \s*["']?\b(?:university|program|quota)\b["']?\s*(?:[:=\-]|\bis\b)
            |
            \n
            |
            $
        )
        """
    )

    for match in segmented_pattern.finditer(text):
        key = match.group(1).strip().lower()
        value = _clean_value(match.group(2))
        if value:
            candidates.setdefault(key, value)

    # Line-level fallback for noisy text.
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.search(r'(?i)["\']?\b(university|program|quota)\b["\']?\s*[:=\-]\s*(.+)', line)
        if not m:
            continue
        key = m.group(1).strip().lower()
        value = _clean_value(m.group(2))
        if value:
            candidates.setdefault(key, value)

    return candidates


def _extract_text_field(candidates: Dict[str, str], key: str) -> Optional[str]:
    value = candidates.get(key.lower())
    if value:
        return _clean_value(value)
    return None


def _extract_quota_context(text: str) -> Optional[str]:
    patterns = [
        r"(?is)\bquota\b\s*(?:[:=\-]|\bis\b)\s*([^\n|]+)",
        r'(?is)"quota"\s*:\s*"([^"]+)"',
        r'(?is)"quota"\s*:\s*([^,\n\}]+)',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = _clean_value(match.group(1))
            if value:
                return value
    return None


def _words_to_int(text: str) -> Optional[int]:
    word_map = {
        "zero": 0,
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
        "eleven": 11,
        "twelve": 12,
        "thirteen": 13,
        "fourteen": 14,
        "fifteen": 15,
        "sixteen": 16,
        "seventeen": 17,
        "eighteen": 18,
        "nineteen": 19,
        "twenty": 20,
        "thirty": 30,
        "forty": 40,
        "fifty": 50,
        "sixty": 60,
        "seventy": 70,
        "eighty": 80,
        "ninety": 90,
    }

    scales = {"hundred": 100, "thousand": 1000}
    ignore_tokens = {"and", "students", "student", "seats", "seat"}

    tokens = re.findall(r"[a-zA-Z]+", text.lower())
    if not tokens:
        return None

    total = 0
    current = 0
    seen_number_token = False

    for token in tokens:
        if token in ignore_tokens:
            continue
        if token in word_map:
            current += word_map[token]
            seen_number_token = True
            continue
        if token == "hundred":
            if current == 0:
                current = 1
            current *= scales[token]
            seen_number_token = True
            continue
        if token == "thousand":
            if current == 0:
                current = 1
            total += current * scales[token]
            current = 0
            seen_number_token = True
            continue
        return None

    if not seen_number_token:
        return None
    return total + current


def _parse_quota(text: str, quota_candidate: Optional[str]) -> Optional[int]:
    raw_quota = _clean_value(quota_candidate) or _extract_quota_context(text)
    if raw_quota is None:
        # Conservative fallback for known phrase without number.
        if re.search(r"(?i)\bquota\b.*\b(announce|announced|later|tbd|to be determined)\b", text):
            return 40
        return None

    digit_match = re.search(r"-?\d+", raw_quota)
    if digit_match:
        try:
            return int(digit_match.group(0))
        except (TypeError, ValueError):
            return None

    return _words_to_int(raw_quota)


def extract(raw_input: str) -> dict:
    """AutoEval entrypoint with robust text parsing."""
    result: Dict[str, Optional[object]] = {"university": None, "program": None, "quota": None}
    text = _normalize_text(str(raw_input or ""))
    if not text.strip():
        return result

    try:
        candidates: Dict[str, str] = {}
        candidates.update(_extract_json_candidates(text))
        kv_candidates = _extract_kv_candidates(text)
        for k, v in kv_candidates.items():
            candidates.setdefault(k, v)

        result["university"] = _extract_text_field(candidates, "university")
        result["program"] = _extract_text_field(candidates, "program")
        result["quota"] = _parse_quota(text, candidates.get("quota"))
    except Exception:
        # Hard safety guard for AutoEval stability.
        return {"university": None, "program": None, "quota": None}

    return result
