from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Optional
import json


@dataclass
class AdmissionRequirements:
    gmat: Optional[float] = None
    gre: Optional[float] = None
    gpa: Optional[float] = None
    ielts: Optional[float] = None
    toefl: Optional[float] = None
    duolingo: Optional[float] = None
    application_deadline_text: Optional[str] = None
    raw_text: Optional[str] = None
    parsed_status: Optional[str] = None
    overall_score: Optional[float] = None
    
    def __post_init__(self):
        self._validate()
    
    def _validate(self):
        validations = {
            'gmat': (200, 800),
            'gre': (260, 340),
            'gpa': (0, 4.0),
            'ielts': (0, 9.0),
            'toefl': (0, 120),
            'duolingo': (60, 160),
            'overall_score': (0, 100)
        }
        
        for field_name, (min_val, max_val) in validations.items():
            value = getattr(self, field_name)
            if value is not None:
                if not (min_val <= value <= max_val):
                    setattr(self, field_name, None)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def get_display_value(self, field_name: str) -> str:
        value = getattr(self, field_name)
        if value is None:
            return "N/A"
        return f"{value:.2f}".rstrip('0').rstrip('.')
    
    def calculate_overall_score(self) -> Optional[float]:
        scores = []
        
        if self.gpa is not None:
            scores.append(self.gpa / 4.0 * 100)
        if self.gmat is not None:
            scores.append(self.gmat / 800 * 100)
        if self.gre is not None:
            scores.append(self.gre / 340 * 100)
        if self.ielts is not None:
            scores.append(self.ielts / 9.0 * 100)
        if self.toefl is not None:
            scores.append(self.toefl / 120 * 100)
        if self.duolingo is not None:
            scores.append(self.duolingo / 160 * 100)
        
        if scores:
            self.overall_score = sum(scores) / len(scores)
            return self.overall_score
        return None


@dataclass
class University:
    rank: str
    name: str
    country: str = ""
    location: str = ""
    city_name: str = ""
    website_url: str = ""
    qs_profile_path: str = ""
    canonical_name: str = ""
    path: str = ""
    table_metrics: Dict[str, str] = field(default_factory=dict)
    requirements: AdmissionRequirements = field(default_factory=AdmissionRequirements)
    
    def get_effective_canonical_name(self) -> str:
        return self.canonical_name or self.name
    
    def to_dict(self) -> Dict[str, Any]:
        data = {
            'rank': self.rank,
            'name': self.name,
            'country': self.country,
            'location': self.location,
            'city_name': self.city_name,
            'website_url': self.website_url,
            'qs_profile_path': self.qs_profile_path,
            'canonical_name': self.canonical_name,
            'path': self.path,
            'table_metrics': self.table_metrics,
        }

        for key, value in self.requirements.to_dict().items():
            data[key] = value
        return data
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'University':
        requirements_fields = {
            'gmat', 'gre', 'gpa', 'ielts', 'toefl', 'duolingo',
            'application_deadline_text', 'raw_text', 'parsed_status', 'overall_score'
        }
        
        req_data = {k: v for k, v in data.items() if k in requirements_fields}
        requirements = AdmissionRequirements(**req_data)
        
        return cls(
            rank=data.get('rank', 'N/A'),
            name=data.get('name', ''),
            country=data.get('country', ''),
            location=data.get('location', ''),
            city_name=data.get('city_name', ''),
            website_url=data.get('website_url', ''),
            qs_profile_path=data.get('qs_profile_path', ''),
            canonical_name=data.get('canonical_name', ''),
            path=data.get('path', ''),
            table_metrics=data.get('table_metrics', {}) or {},
            requirements=requirements
        )
