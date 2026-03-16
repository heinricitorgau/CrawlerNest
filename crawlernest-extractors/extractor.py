import re
import logging
from typing import Optional, List, Tuple
from models import AdmissionRequirements


DEADLINE_PATTERN = re.compile(
    r"(application deadline|deadline|apply by|applications close)\s*[:\-]?\s*([A-Za-z]{3,9}\s+\d{1,2}(?:,\s*\d{4})?)",
    re.IGNORECASE,
)


logger = logging.getLogger('UniversityCrawler')


class ScoreValidator:

    
    # 【技術細節：入學指標邊界 (Score Boundary Check)】
    # 設定各大留學指標的合法數值範圍，用於在解析過程中過濾掉「雜訊」或「非分數數值」。
    RANGES = {
        'gmat': (200, 800),
        'gre': (260, 340),
        'gpa': (0, 4.0),
        'ielts': (0, 9.0),
        'toefl': (0, 120),
        'duolingo': (60, 160),
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
        """
        【技術細節：上下文隔離 (Context Isolation)】
        為了避免大學網頁中 Undergraduate (大學部) 與 Postgraduate (研究所) 的入學要求混淆，
        系統會利用 Regex 偵測關鍵字，動態定位「研究所/碩士」相關的 HTML 區塊，
        並進行區段截取 (Slicing)，確保後續解析僅針對目標區塊。
        """
        master_start = -1
        
                                           
        patterns = [

            r'univ-section-title["\s>]+[^<]*(?:Master|Masters|Postgraduate|Graduate|Entry\s+requirements|English\s+language)[^<]*<',
            r'<h[23][^>]*>[^<]*(?:Master|Masters|Postgraduate|Graduate|Entry\s+requirements|English\s+language)[^<]*</h[23]>',
            r'>\s*(?:Master|Masters|Postgraduate|Graduate)\s*<',

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
            text_chunk = text_chunk[:next_section.start()]
        else:
            text_chunk = text_chunk[:10000]                            
        
                                                   
        text_content = re.sub(r'<[^>]+>', ' ', text_chunk)
        text_content = re.sub(r'\s+', ' ', text_content)
        
        return text_content
    
    def find_score(
        self,
        keyword: str,
        text: str,
        pattern: str,
        score_type: str
    ) -> Optional[float]:

        try:
            values = []
            
            # 【技術細節：視窗化滑動搜尋 (Windowed Extract)】
            # 設定 window = 140 字元。這是一個經驗值，用於限制關鍵字（如 IELTS）
            # 與目標數值（如 7.0）之間的距離。
            # 超出此「視窗」的數值會被視為無關數據，從而極大提高提取的準確度。
            window = 140
            search_patterns = [
                rf"{keyword}.{{0,{window}}}?{pattern}",
                rf"{pattern}.{{0,{window}}}?{keyword}",
            ]
            matches = []
            for sp in search_patterns:
                matches.extend(list(re.finditer(sp, text, re.IGNORECASE)))
            
            for match in matches:
                try:
                                           
                    val_str = match.group(1).strip('+').strip()
                    
                                                           
                    if '-' in val_str and val_str.count('-') == 1:
                        parts = val_str.split('-')
                        if len(parts) == 2:
                            try:
                                low = float(parts[0])
                                high = float(parts[1])
                                # 【技術細節：範圍平均算術化】
                                # 如果解析出範圍 (如 7.0-7.5)，則執行算術平均計算。
                                if (self.validator.is_valid(score_type, low) and 
                                    self.validator.is_valid(score_type, high)):
                                    val = (low + high) / 2                         
                                    values.append(val)
                                continue
                            except ValueError:
                                continue
                    
                    val = float(val_str)
                    
                                    
                    if self.validator.is_valid(score_type, val):
                        values.append(val)
                    else:
                        self.logger.debug(
                            f"Invalid {score_type} score filtered: {val}"
                        )
                
                except (ValueError, IndexError) as e:
                    self.logger.debug(f"Failed to parse score: {e}")
                    continue
            
            if values:
                avg = sum(values) / len(values)
                self.logger.debug(
                    f"Found {keyword}: {values} -> avg: {avg:.2f}"
                )
                return avg
            
        except Exception as e:
            self.logger.error(f"Error extracting {keyword}: {e}")
        
        return None
    
    def extract_requirements(self, html: str) -> AdmissionRequirements:

                                         
        text_content = self.extract_master_section(html)
        parsed_status = "master_section"
        
        if not text_content:
            parsed_status = "full_page_fallback"
            if not self._warned_no_master:
                self.logger.debug("No Master section found, trying full page")
                self._warned_no_master = True
            text_content = re.sub(r'<[^>]+>', ' ', html[:20000])
            text_content = re.sub(r'\s+', ' ', text_content)

                                                                 
        def first_score(keywords, pattern, score_type):
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

                                    
        # Attempt to detect application deadline text
        application_deadline_text = None
        m = DEADLINE_PATTERN.search(text_content)
        if m:
            application_deadline_text = m.group(2)

        requirements = AdmissionRequirements(
            gmat=gmat,
            gre=gre,
            gpa=gpa,
            ielts=ielts,
            toefl=toefl,
            duolingo=duolingo,
            application_deadline_text=application_deadline_text,
            raw_text=text_content[:2000],
            parsed_status=parsed_status,
        )
        
                                 
        requirements.calculate_overall_score()
        
        return requirements
