"""
Command-line interface for QS University Rankings crawler.
"""

import argparse
import logging
import sys

from constants import COUNTRY_CODES, COUNTRY_ALIASES
from crawler import run_crawler
from config import Config
from utils import setup_logging


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='University Admission Requirements Crawler',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                      # Default: World TOP 100 universities, console output
  %(prog)s --country uk --format csv            # UK universities, export to CSV
  %(prog)s --output mydata.xlsx --format excel  # Export to Excel file
  %(prog)s --progress --log crawler.log         # With progress bar and logging

Supported countries: us, uk, ca, au, de, fr, sg, hk, cn, jp (leave empty for World TOP 100)
Supported formats: console, csv, excel, json
        """
    )
    
    parser.add_argument(
        '--country',
        type=str,
        default=None,
        help='Country code or name (e.g., us, uk, ca, tw, etc.; default: None for World TOP 100)'
    )
    
    parser.add_argument(
        '--format',
        type=str,
        default='console',
        choices=['console', 'csv', 'excel', 'json'],
        help='Output format (default: console)'
    )
    
    parser.add_argument(
        '--output',
        type=str,
        help='Output file path (auto-generated if not specified)'
    )
    
    parser.add_argument(
        '--progress',
        action='store_true',
        default=True,
        help='Show progress bar (default: enabled, requires tqdm)'
    )
    
    parser.add_argument(
        '--no-progress',
        dest='progress',
        action='store_false',
        help='Disable progress bar'
    )
    
    parser.add_argument(
        '--log',
        type=str,
        help='Log file path (default: no file logging)'
    )
    
    parser.add_argument(
        '--log-level',
        type=str,
        default='INFO',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (default: INFO)'
    )
    
    parser.add_argument(
        '--async',
        dest='use_async',
        action='store_true',
        help='Use async mode for faster scraping (requires aiohttp)'
    )
    
    parser.add_argument(
        '--limit',
        dest='ranking_limit',
        type=int,
        default=100,
        help='Maximum number of universities to process (default: 100)'
    )
    
    parser.add_argument(
        '--sort-ascending',
        dest='sort_ascending',
        action='store_true',
        help='Sort results in ascending order of rank (Low to High)'
    )
    
    parser.add_argument(
        '--ranking-id',
        dest='ranking_id',
        type=str,
        help='Specific Ranking ID to fetch'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 2.0.0'
    )
    
    return parser.parse_args()


def main():
    """Main CLI entry point."""
    args = parse_arguments()
    if args.ranking_limit is None or args.ranking_limit <= 0:
        print("✗ --limit must be a positive integer.")
        return 1

    internal_country = COUNTRY_ALIASES.get(args.country, args.country) if args.country else None
    
    # Set default ranking_id if not specified
    ranking_id = args.ranking_id
    if not ranking_id:
        from constants import SUBJECT_PRESETS
        ranking_id = SUBJECT_PRESETS['general']['ranking_id']
    
    output_file = args.output
    if not output_file and args.format != 'console':
        extensions = {
            'csv': '.csv',
            'excel': '.xlsx',
            'json': '.json'
        }
        suffix = args.country if args.country else "world"
        output_file = f"universities_{suffix}{extensions.get(args.format, '.txt')}"
    
    print("=" * 80)
    print("University Admission Requirements Crawler v2.0")
    print("=" * 80)
    country_display = COUNTRY_CODES.get(args.country, args.country) if args.country else "World"
    limit_display = f" (TOP {args.ranking_limit})" if args.ranking_limit else ""
    sort_display = " [Ascending]" if args.sort_ascending else ""
    print(f"Scope: {country_display}{limit_display}{sort_display}")
    print(f"Output format: {args.format}")
    if output_file:
        print(f"Output file: {output_file}")
    print("=" * 80)
    
    try:
        universities = run_crawler(
            ranking_id=ranking_id,
            country=internal_country,
            output_format=args.format,
            output_file=output_file,
            ranking_limit=args.ranking_limit,
            sort_ascending=args.sort_ascending,
            use_async=args.use_async,
            show_progress=args.progress,
            log_file=args.log,
            log_level=args.log_level
        )
        
        if universities:
            print(f"\n✓ Successfully scraped {len(universities)} universities")
            if output_file:
                print(f"✓ Results saved to: {output_file}")
        else:
            print("\n✗ No data was scraped")
            return 1
    
    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
        return 130
    
    except Exception as e:
        print(f"\n✗ Fatal error: {e}")
        logging.exception("Fatal error in main")
        return 1
    
    return 0
