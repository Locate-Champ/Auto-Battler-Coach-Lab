"""
MetaTFT Log Parser
Extracts augment data and match information from Overwolf/MetaTFT logs
"""

import re
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


class MetaTFTLogParser:
    """Parse MetaTFT Overwolf logs to extract augment and match data"""

    def __init__(self, log_dir: str = None):
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = None

        self.augment_events = []
        self.matches = []

    def parse_augment_log(self, log_path: str) -> List[Dict]:
        """Parse an augment_recommendations log file"""
        events = []

        with open(log_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                # Look for augment_armory data lines
                if 'augment_armory data' not in line:
                    continue

                # Extract timestamp
                timestamp_match = re.match(r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3})', line)
                if not timestamp_match:
                    continue
                timestamp = timestamp_match.group(1)

                # Extract augment_options JSON
                options_match = re.search(r'"augment_options":\[([^\]]+)\]', line)
                if options_match:
                    try:
                        options_str = options_match.group(1)
                        # Parse the array
                        options = [s.strip('"') for s in options_str.split(',')]
                        options = [self._clean_augment_name(o) for o in options]
                    except:
                        options = []
                else:
                    options = []

                # Extract selected augments if present
                selected = {}
                for i in range(1, 4):
                    pattern = f'"augment_{i}":{{"name":"([^"]*)"'
                    match = re.search(pattern, line)
                    if match and match.group(1):
                        selected[i] = self._clean_augment_name(match.group(1))

                # Extract armory state
                state_match = re.search(r'"armory_state":"(\w+)"', line)
                armory_state = state_match.group(1) if state_match else 'unknown'

                # Extract armory type
                type_match = re.search(r'"armory_type":"(\w+)"', line)
                armory_type = type_match.group(1) if type_match else 'regular'

                if options:
                    events.append({
                        'timestamp': timestamp,
                        'options': options,
                        'selected': selected,
                        'armory_state': armory_state,
                        'armory_type': armory_type
                    })

        return events

    def _clean_augment_name(self, name: str) -> str:
        """Clean augment internal name to readable format"""
        if not name:
            return name
        # Remove TFT prefixes
        name = re.sub(r'^TFT\d*_Augment_', '', name)
        # Add spaces before capitals
        name = re.sub(r'([a-z])([A-Z])', r'\1 \2', name)
        # Handle special cases
        name = name.replace('_', ' ')
        name = name.replace('II', ' II').replace('III', ' III')
        name = re.sub(r'\s+', ' ', name).strip()
        return name

    def parse_all_augment_logs(self, log_dir: str = None) -> List[Dict]:
        """Parse all augment recommendation logs in directory"""
        if log_dir:
            search_dir = Path(log_dir)
        elif self.log_dir:
            search_dir = self.log_dir
        else:
            raise ValueError("No log directory specified")

        all_events = []

        # Find all augment recommendation logs
        for log_file in search_dir.glob('**/augment_recommendations*.log'):
            events = self.parse_augment_log(str(log_file))
            all_events.extend(events)

        # Sort by timestamp
        all_events.sort(key=lambda x: x['timestamp'])

        # Deduplicate (same timestamp, same options = same event)
        seen = set()
        unique_events = []
        for event in all_events:
            key = (event['timestamp'], tuple(event['options']))
            if key not in seen:
                seen.add(key)
                unique_events.append(event)

        self.augment_events = unique_events
        return unique_events

    def get_augment_stats(self) -> Dict:
        """Analyze augment appearance and selection rates"""
        offered_counts = defaultdict(int)
        selected_counts = defaultdict(int)

        for event in self.augment_events:
            for aug in event['options']:
                offered_counts[aug] += 1
            for aug in event.get('selected', {}).values():
                if aug:
                    selected_counts[aug] += 1

        stats = {
            'total_armories': len(self.augment_events),
            'unique_augments_seen': len(offered_counts),
            'augments': {}
        }

        for aug, offered in offered_counts.items():
            stats['augments'][aug] = {
                'times_offered': offered,
                'times_selected': selected_counts.get(aug, 0),
                'selection_rate': selected_counts.get(aug, 0) / offered if offered > 0 else 0
            }

        return stats

    def export_to_csv(self, output_path: str):
        """Export augment events to CSV for analysis"""
        import csv

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['timestamp', 'armory_type', 'option_1', 'option_2', 'option_3',
                           'selected_1', 'selected_2', 'selected_3'])

            for event in self.augment_events:
                options = event['options'] + [''] * (3 - len(event['options']))
                selected = [event.get('selected', {}).get(i, '') for i in range(1, 4)]

                writer.writerow([
                    event['timestamp'],
                    event.get('armory_type', 'regular'),
                    *options[:3],
                    *selected
                ])

        print(f"Exported {len(self.augment_events)} augment events to {output_path}")


def main():
    """Demo the parser with extracted logs"""
    import sys

    # Default to metatft_logs directory
    log_dir = 'metatft_logs/Log/Apps/MetaTFT'

    if len(sys.argv) > 1:
        log_dir = sys.argv[1]

    print(f"Parsing MetaTFT logs from: {log_dir}")
    print("=" * 60)

    parser = MetaTFTLogParser()

    try:
        events = parser.parse_all_augment_logs(log_dir)
        print(f"Found {len(events)} augment armory events")

        if events:
            print("\n--- Recent Augment Offerings ---")
            for event in events[-10:]:
                ts = event['timestamp']
                opts = ', '.join(event['options'][:3])
                selected = list(event.get('selected', {}).values())
                sel_str = f" -> Selected: {selected[0]}" if selected else ""
                print(f"  [{ts}] {opts}{sel_str}")

            print("\n--- Augment Statistics ---")
            stats = parser.get_augment_stats()
            print(f"Total armories: {stats['total_armories']}")
            print(f"Unique augments seen: {stats['unique_augments_seen']}")

            # Show most offered augments
            print("\nMost Offered Augments:")
            sorted_augs = sorted(stats['augments'].items(),
                               key=lambda x: x[1]['times_offered'], reverse=True)
            for aug, data in sorted_augs[:15]:
                print(f"  {aug}: {data['times_offered']}x offered, "
                      f"{data['times_selected']}x selected ({data['selection_rate']*100:.0f}%)")

            # Export to CSV
            parser.export_to_csv('data/personal/metatft_augments.csv')

    except FileNotFoundError as e:
        print(f"Log directory not found: {e}")
    except Exception as e:
        print(f"Error parsing logs: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
