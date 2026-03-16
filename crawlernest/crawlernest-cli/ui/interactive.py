"""
Interactive user input and parameter collection.
"""

import traceback
from typing import Dict, List, Optional, Union, Tuple

from constants import (
    SUBJECT_PRESETS,
    REGION_SUBREGION_PRESETS,
    COUNTRY_CODES,
    COUNTRY_ALIASES,
    get_available_countries,
)
from .validators import validate_country_input, validate_positive_integer, parse_multi_select


def print_available_countries_table():
    """Display available countries in a formatted table."""
    items = sorted(get_available_countries().items(), key=lambda x: x[0])
    if not items:
        return

    print("\nAvailable Countries (code -> name):")
    print("-" * 60)
    col_width = 20
    row: list[str] = []
    for code, name in items:
        row.append(f"{code:<3} -> {name:<{col_width - 7}}")
        if len(row) == 3:
            print("  ".join(row))
            row = []
    if row:
        print("  ".join(row))
    print("-" * 60)


def select_ranking_type() -> tuple[str, Optional[Union[str, List[str]]], Optional[str], Optional[str]]:
    """
    Prompt user to select ranking type.
    
    Returns:
        Tuple of (type_choice, ranking_id, ranking_page_url, region_name)
    """
    print("\n── Select Ranking Type ──────────────────────────────")
    print("  [1]  QS World University Rankings 2025")
    print("  [2]  Ranking by Subject  (multi-select)")
    print("  [3]  QS World University Rankings by Region")
    print("  [4]  QS World University Rankings: Sustainability")
    print("  [5]  QS Global MBA Rankings")
    print("  [6]  QS Business Master's Rankings")
    print("  [7]  QS Best Student Cities")
    print("─────────────────────────────────────────────────────")
    type_choice = input("  Choice [1/2/3/4/5/6/7, default: 1]: ").strip()
    
    ranking_id: Optional[Union[str, List[str]]] = None
    ranking_page_url: Optional[str] = None
    region_name: Optional[str] = None
    
    if type_choice == '2':
        ranking_id = select_subjects()
    elif type_choice == '3':
        ranking_page_url, region_name = select_region()
        ranking_id = None
    elif type_choice == '4':
        from constants import RANKING_PAGE_PRESETS
        ranking_id = None
        ranking_page_url = RANKING_PAGE_PRESETS["sustainability"]
        print("\nSelected: QS World University Rankings: Sustainability")
    elif type_choice == '5':
        from constants import RANKING_PAGE_PRESETS
        ranking_id = None
        ranking_page_url = RANKING_PAGE_PRESETS.get("mba", "https://www.topuniversities.com/mba-rankings/global")
        region_name = select_mba_region()
        if region_name:
            print(f"\nSelected: QS Global MBA Rankings ({region_name})")
        else:
            print("\nSelected: QS Global MBA Rankings (Global)")
    elif type_choice == '6':
        ranking_id = None
        ranking_page_url, subject_name = select_business_masters_subject()
        region_name = select_business_masters_region()
        if region_name:
            print(f"\nSelected: QS Business Master's Rankings - {subject_name} ({region_name})")
        else:
            print(f"\nSelected: QS Business Master's Rankings - {subject_name} (Global)")
    elif type_choice == '7':
        from constants import RANKING_PAGE_PRESETS
        ranking_id = None
        ranking_page_url = RANKING_PAGE_PRESETS.get("city_rankings", "https://www.topuniversities.com/city-rankings")
        print("\nSelected: QS Best Student Cities")
    else:
        type_choice = '1'
        ranking_id = SUBJECT_PRESETS['general']['ranking_id']
        print(f"\nSelected: {SUBJECT_PRESETS['general']['name']}")
    
    return type_choice, ranking_id, ranking_page_url, region_name


def select_mba_region() -> Optional[str]:
    """
    Prompt user to select region specifically for QS Global MBA Rankings.
    
    Returns:
        Optional[str]: Region name or None if Global is selected.
    """
    regions = [
        ("Asia", "Asia"),
        ("Canada", "Canada"),
        ("Europe", "Europe"),
        ("Global", None),
        ("Latin America", "Latin America"),
        ("Middle East & Africa", "Middle East & Africa"),
        ("Oceania", "Oceania"),
        ("United States", "United States")
    ]
    
    print("\nAvailable MBA Regions:")
    for idx, (name, _) in enumerate(regions, 1):
        print(f"{idx}. {name}")
        
    choice = input(f"Enter choice [1-{len(regions)}, default: 4 (Global)]: ").strip()
    
    idx = 4
    if choice.isdigit():
        parsed_idx = int(choice)
        if 1 <= parsed_idx <= len(regions):
            idx = parsed_idx
            
    return regions[idx - 1][1]


def select_business_masters_subject() -> Tuple[str, str]:
    """
    Prompt user to select a Business Master's subject.
    
    Returns:
        Tuple[str, str]: (ranking_page_url, subject_name)
    """
    from constants import RANKING_PAGE_PRESETS
    
    subjects = [
        ("Business Analytics", RANKING_PAGE_PRESETS.get("business_analytics", "https://www.topuniversities.com/business-masters-rankings/business-analytics")),
        ("Finance", RANKING_PAGE_PRESETS.get("finance", "https://www.topuniversities.com/business-masters-rankings/finance")),
        ("Management", RANKING_PAGE_PRESETS.get("management", "https://www.topuniversities.com/business-masters-rankings/management")),
        ("Marketing", RANKING_PAGE_PRESETS.get("marketing", "https://www.topuniversities.com/business-masters-rankings/marketing")),
        ("Supply Chain Management", RANKING_PAGE_PRESETS.get("supply_chain_management", "https://www.topuniversities.com/business-masters-rankings/supply-chain-management"))
    ]
    
    print("\nAvailable Business Master's Subjects:")
    for idx, (name, _) in enumerate(subjects, 1):
        print(f"{idx}. {name}")
        
    choice = input(f"Enter choice [1-{len(subjects)}, default: 2 (Finance)]: ").strip()
    
    idx = 2
    if choice.isdigit():
        parsed_idx = int(choice)
        if 1 <= parsed_idx <= len(subjects):
            idx = parsed_idx
            
    name, url = subjects[idx - 1]
    return url, name


def select_business_masters_region() -> Optional[str]:
    """
    Prompt user to select region specifically for QS Business Master's Rankings.
    
    Returns:
        Optional[str]: Region name or None if Global is selected.
    """
    print("\n── Ranking Scope ────────────────────────────────────")
    print("  [1]  World Ranking (Global)")
    print("  [2]  Region Ranking")
    print("─────────────────────────────────────────────────────")
    scope_choice = input("  Choice [1/2, default: 1]: ").strip()
    
    if scope_choice != '2':
        return None

    regions = [
        ("Asia", "Asia"),
        ("Canada", "Canada"),
        ("Europe", "Europe"),
        ("Latin America", "Latin America"),
        ("Middle East & Africa", "Middle East & Africa"),
        ("Oceania", "Oceania"),
        ("United States", "United States")
    ]
    
    print("\nAvailable Regions:")
    for idx, (name, _) in enumerate(regions, 1):
        print(f"{idx}. {name}")
        
    choice = input(f"Enter choice [1-{len(regions)}, default: 1 (Asia)]: ").strip()
    
    idx = 1
    if choice.isdigit():
        parsed_idx = int(choice)
        if 1 <= parsed_idx <= len(regions):
            idx = parsed_idx
            
    return regions[idx - 1][1]


def select_subjects() -> Union[str, List[str]]:
    """
    Prompt user to select subjects (multi-select).
    
    Returns:
        Single ranking_id or list of ranking_ids
    """
    subject_keys = [k for k in SUBJECT_PRESETS.keys() if k != 'general']
    if not subject_keys:
        print("No subject presets found. Fallback to general ranking.")
        return SUBJECT_PRESETS['general']['ranking_id']
    
    print("\nAvailable Subjects (multi-select):")
    for idx, key in enumerate(subject_keys, 1):
        print(f"{idx}. {SUBJECT_PRESETS[key]['name']}")
    
    multi_input = input(f"Enter numbers [1-{len(subject_keys)}], default: all: ").strip()
    selected_idx = parse_multi_select(multi_input, len(subject_keys))
    
    ranking_ids = [SUBJECT_PRESETS[subject_keys[i-1]]['ranking_id'] for i in selected_idx]
    selected_subjects = [SUBJECT_PRESETS[subject_keys[i-1]]['name'] for i in selected_idx]
    print(f"\nSelected: {', '.join(selected_subjects)}")
    
    return ranking_ids


def select_region() -> tuple[str, str]:
    """
    Prompt user to select region/subregion.
    
    Returns:
        Tuple of (ranking_page_url, region_name)
    """
    print("\nAvailable Sub-regions:")
    for idx, (subregion, _) in enumerate(REGION_SUBREGION_PRESETS, 1):
        print(f"{idx}. {subregion}")
    
    sub_input = input(f"Enter choice [1-{len(REGION_SUBREGION_PRESETS)}, default: 1]: ").strip()
    sub_idx = 1
    if sub_input.isdigit():
        parsed_sub = int(sub_input)
        if 1 <= parsed_sub <= len(REGION_SUBREGION_PRESETS):
            sub_idx = parsed_sub
    
    selected_subregion, ranking_page_url = REGION_SUBREGION_PRESETS[sub_idx - 1]
    
    if selected_subregion == "Arab Region University Rankings":
        region_name = "Arab Region"
    else:
        region_name = selected_subregion
    
    print(f"\nSelected: QS World University Rankings by Region ({selected_subregion})")
    return ranking_page_url, region_name


def select_scope() -> Optional[Union[str, List[str]]]:
    """
    Prompt user to select scope (world, regional, or national).
    
    Returns:
        Country code(s) or None for world ranking, or dict with 'region_scope' for regional.
    """
    print("\n── Select Scope ─────────────────────────────────────")
    print("  [1]  World Ranking  (all countries)")
    print("  [2]  Regional Ranking  (filter by continent/region)")
    print("  [3]  National Ranking  (filter by country)")
    print("─────────────────────────────────────────────────────")
    scope_choice = input("  Choice [1/2/3, default: 1]: ").strip()

    if scope_choice == "3":
        return select_countries()
    elif scope_choice == "2":
        region_name = select_regional_scope()
        # Return a sentinel dict so get_user_parameters knows to treat this as region_name
        return {"_region_scope": region_name} if region_name else None
    else:
        print("\nSelected Scope: World Ranking")
        return None

def select_regional_scope() -> Optional[str]:
    """
    Prompt user to select a regional grouping for generic rankings.
    
    Returns:
        Region name string to use for client-side filtering.
    """
    regions = [
        "Africa",
        "Asia",
        "Europe",
        "Latin America",
        "Middle East",
        "North America",
        "Oceania"
    ]
    
    print("\nAvailable Regions:")
    for idx, name in enumerate(regions, 1):
        print(f"{idx}. {name}")
        
    choice = input(f"Enter choice [1-{len(regions)}, default: 2 (Asia)]: ").strip()
    
    idx = 2
    if choice.isdigit():
        parsed_idx = int(choice)
        if 1 <= parsed_idx <= len(regions):
            idx = parsed_idx
            
    selected_region = regions[idx - 1]
    print(f"\nSelected Scope: Regional Ranking ({selected_region})")
    return selected_region


def select_countries() -> Union[str, List[str]]:
    """
    Prompt user to select one or more countries.
    
    Returns:
        Single country code or list of country codes
    """
    print_available_countries_table()
    available_countries = get_available_countries()
    
    while True:
        c_in = input("Enter country code/name (comma-separated for multiple, e.g., us,uk,tw) [default: us]: ").strip()
        if not c_in:
            c_in = "us"

        valid_countries, invalid_inputs = validate_country_input(c_in, available_countries, COUNTRY_ALIASES)
        
        if invalid_inputs:
            print(f"Invalid country codes/names: {', '.join(invalid_inputs)}")
            print("Try codes like us/uk/tw or full country names from the table above.")
            continue

        if valid_countries:
            # Return single string if only one country, otherwise return list
            if len(valid_countries) == 1:
                country = valid_countries[0]
                print(f"\nSelected Scope: National Ranking ({COUNTRY_CODES.get(country, country)})")
                return country
            else:
                country_names = [COUNTRY_CODES.get(c, c) for c in valid_countries]
                print(f"\nSelected Scope: National Ranking ({', '.join(country_names)})")
                return valid_countries


def get_ranking_limit() -> int:
    """
    Prompt user for ranking limit.
    
    Returns:
        Ranking limit (positive integer)
    """
    while True:
        limit_input = input("\nEnter ranking limit (positive integer, default: 100): ").strip()
        if not limit_input:
            return 100
        
        limit = validate_positive_integer(limit_input)
        if limit:
            return limit
        
        print("Invalid input. Please enter a positive integer (e.g., 10, 25, 100).")


def get_sort_direction() -> bool:
    """
    Prompt user for sort direction.
    
    Returns:
        True for ascending, False for descending
    """
    print("\n── Sort Direction ───────────────────────────────────")
    print("  [1]  High → Low  (rank 1 first)  [default]")
    print("  [2]  Low → High  (rank N first)")
    print("─────────────────────────────────────────────────────")
    sort_choice = input("  Choice [1/2]: ").strip()
    return sort_choice == '2'


def get_user_parameters() -> Dict:
    """
    Get all user parameters through interactive prompts.
    
    Returns:
        Dictionary of parameters for run_crawler
    """
    type_choice, ranking_id, ranking_page_url, region_name = select_ranking_type()
    
    country = None
    if type_choice in ("", "1", "2", "4", "7"):
        scope = select_scope()
        # Sentinel dict means user chose regional scope → client-side filter via region_name
        if isinstance(scope, dict) and "_region_scope" in scope:
            if not region_name:  # don't override MBA/Business Masters region_name
                region_name = scope["_region_scope"]
        else:
            country = scope
    
    ranking_limit = get_ranking_limit()
    sort_ascending = get_sort_direction()
    
    return {
        "ranking_id": ranking_id,
        "ranking_page_url": ranking_page_url,
        "region_name": region_name,
        "country": country,
        "ranking_limit": ranking_limit,
        "sort_ascending": sort_ascending
    }


def fetch_rankings():
    """Main interactive ranking fetcher."""
    banner = """
╔══════════════════════════════════════════════════════╗
║        QS University Rankings  ·  Data Explorer      ║
║     topuniversities.com  |  Powered by web crawler   ║
╚══════════════════════════════════════════════════════╝"""
    print(banner)
    params = get_user_parameters()
    
    while True:
        try:
            from crawler import run_crawler
            universities = run_crawler(
                output_format='console',
                use_async=False,
                show_progress=True,
                log_level='WARNING',
                **params
            )
        except Exception as e:
            print(f"\n✗ Error occurred: {type(e).__name__}: {e}")
            print("\nFull traceback:")
            traceback.print_exc()
            universities = []

        if not universities:
            print("\n✗ No universities found with these parameters.")
            print("  This can still happen if QS does not provide rows for the selected country/ranking.")
        
        while True:
            print("── What would you like to do next? ─────────────────")
            print("  [1]  Sort by admission metric  (GMAT / GRE / IELTS …)")
            print("  [2]  New search  (change ranking / scope / limit)")
            print("  [3]  Exit")
            print("─────────────────────────────────────────────────────")
            action = input("  Choice [1/2/3, default: 1]: ").strip() or "1"
            
            if action == '1':
                if not universities:
                    print("✗ No data available to sort. Please perform a new search.")
                    continue
                if params.get("ranking_page_url") and not params.get("region_name"):
                    print("This ranking type is ranking-only; secondary metric ranking is not applicable.")
                    continue
                
                print("\n  Metrics: gmat  gre  gpa  ielts  toefl  det  overall")
                metric = input("  Select metric (or Enter to go back): ").lower().strip()
                if metric:
                    from exporter import get_exporter, ConsoleExporter
                    exporter = get_exporter('console')
                    if isinstance(exporter, ConsoleExporter):
                        exporter.print_metric_ranking(universities, metric)
                    else:
                        print("Metric ranking not supported by this exporter.")
                continue
            
            elif action == '2':
                params = get_user_parameters()
                break
                
            elif action == '3':
                print("\nGoodbye!")
                return
            
            else:
                print("Invalid choice.")
