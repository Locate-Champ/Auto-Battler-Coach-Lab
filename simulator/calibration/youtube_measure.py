"""
YouTube Video Timing Measurement Tool

Downloads TFT gameplay clips from YouTube and measures attack timing.

Usage:
    python youtube_measure.py <youtube_url> --champion <name>
    python youtube_measure.py "https://youtube.com/watch?v=..." --champion "Kai'Sa"

Requirements:
    pip install yt-dlp opencv-python

Tips for finding good videos:
    - Search: "TFT Set 16 [Champion] 3 star"
    - Search: "TFT [Champion] carry gameplay"
    - Look for clear 1v1 or isolated fights
    - Higher resolution = easier to measure
"""

import subprocess
import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime
import argparse

# Check for yt-dlp
try:
    import yt_dlp
except ImportError:
    print("Installing yt-dlp...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "yt-dlp"])
    import yt_dlp

# Import our measurement tool
from quick_measure import QuickMeasure


def sanitize_filename(title: str) -> str:
    """Remove invalid characters from filename."""
    return re.sub(r'[<>:"/\\|?*]', '_', title)[:50]


def download_youtube_video(url: str, output_dir: Path) -> Path:
    """
    Download YouTube video optimized for frame analysis.

    Downloads at highest available quality up to 1080p.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # yt-dlp options - use single format to avoid ffmpeg requirement
    # Priority: best combined mp4 up to 1080p (no merge needed)
    ydl_opts = {
        'format': 'best[height<=1080][ext=mp4]/best[ext=mp4]/best',
        'outtmpl': str(output_dir / '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': False,
    }

    print(f"\nDownloading: {url}")
    print("This may take a moment...\n")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = sanitize_filename(info.get('title', 'video'))

        # Find the downloaded file
        for ext in ['mp4', 'mkv', 'webm']:
            potential_file = output_dir / f"{info.get('title', 'video')}.{ext}"
            if potential_file.exists():
                return potential_file

        # Fallback: find most recent mp4
        mp4_files = list(output_dir.glob("*.mp4"))
        if mp4_files:
            return max(mp4_files, key=lambda p: p.stat().st_mtime)

    raise FileNotFoundError("Could not find downloaded video")


def get_video_info(url: str) -> dict:
    """Get video metadata without downloading."""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return {
            'title': info.get('title'),
            'duration': info.get('duration'),
            'fps': info.get('fps'),
            'resolution': f"{info.get('width', '?')}x{info.get('height', '?')}",
            'uploader': info.get('uploader'),
        }


def search_youtube_for_champion(champion: str, max_results: int = 5) -> list:
    """
    Search YouTube for TFT gameplay videos of a champion.
    Returns list of video URLs.
    """
    search_queries = [
        f"TFT Set 16 {champion} 3 star gameplay",
        f"TFT {champion} carry guide",
        f"TFT Set 16 {champion} spotlight",
    ]

    results = []

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'default_search': 'ytsearch5',  # Search YouTube, get 5 results
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        for query in search_queries[:1]:  # Just use first query
            try:
                search_results = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
                for entry in search_results.get('entries', []):
                    if entry:
                        results.append({
                            'title': entry.get('title'),
                            'url': f"https://youtube.com/watch?v={entry.get('id')}",
                            'duration': entry.get('duration'),
                            'channel': entry.get('channel'),
                        })
            except Exception as e:
                print(f"Search error: {e}")

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Measure TFT champion timing from YouTube videos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Download and measure from URL:
    python youtube_measure.py "https://youtube.com/watch?v=..." --champion "Kai'Sa"

    # Search for videos first:
    python youtube_measure.py --search "Azir"

    # Use already downloaded video:
    python youtube_measure.py video.mp4 --champion "Xerath" --local
        """
    )

    parser.add_argument("url", nargs="?", help="YouTube URL or local video path")
    parser.add_argument("--champion", "-c", required=False, help="Champion name")
    parser.add_argument("--search", "-s", help="Search YouTube for champion videos")
    parser.add_argument("--local", "-l", action="store_true", help="Treat URL as local file path")
    parser.add_argument("--keep", "-k", action="store_true", help="Keep downloaded video after measuring")
    parser.add_argument("--output-dir", "-o", default="downloads", help="Directory for downloads")
    parser.add_argument("--scale", type=float, default=2.0, help="Display scale factor (default: 2.0 = 2x bigger)")

    args = parser.parse_args()

    # Search mode
    if args.search:
        print(f"\nSearching YouTube for: {args.search}")
        print("-" * 50)

        results = search_youtube_for_champion(args.search)

        if not results:
            print("No results found. Try a different search term.")
            return

        print(f"\nFound {len(results)} videos:\n")
        for i, r in enumerate(results, 1):
            duration = f"{r['duration']//60}:{r['duration']%60:02d}" if r['duration'] else "?"
            print(f"{i}. [{duration}] {r['title']}")
            print(f"   {r['url']}")
            print()

        # Ask user to select
        try:
            choice = input("Enter number to download (or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                return

            idx = int(choice) - 1
            if 0 <= idx < len(results):
                args.url = results[idx]['url']
                args.champion = args.champion or args.search
            else:
                print("Invalid selection")
                return
        except (ValueError, KeyboardInterrupt):
            return

    if not args.url:
        parser.print_help()
        return

    # Determine video path
    if args.local:
        video_path = Path(args.url)
        if not video_path.exists():
            print(f"Error: File not found: {video_path}")
            return
    else:
        # Download from YouTube
        output_dir = Path(__file__).parent / args.output_dir

        # Show video info first
        print("\nFetching video info...")
        try:
            info = get_video_info(args.url)
            print(f"  Title: {info['title']}")
            print(f"  Duration: {info['duration']//60}:{info['duration']%60:02d}")
            print(f"  Resolution: {info['resolution']}")
            print(f"  FPS: {info['fps']}")
        except Exception as e:
            print(f"Could not get video info: {e}")

        # Download
        try:
            video_path = download_youtube_video(args.url, output_dir)
            print(f"\nDownloaded to: {video_path}")
        except Exception as e:
            print(f"Error downloading video: {e}")
            return

    # Get champion name
    champion = args.champion
    if not champion:
        champion = input("Enter champion name: ").strip()

    if not champion:
        print("Champion name required")
        return

    # Run measurement
    print(f"\n{'='*50}")
    print(f"MEASURING: {champion}")
    print(f"{'='*50}")
    print("\nOpening video for measurement...")
    print("Controls: SPACE=next, 1=attack start, 2=damage, ENTER=compute, S=save, Q=quit\n")

    try:
        measurer = QuickMeasure(str(video_path), champion, scale=args.scale)
        measurer.run()
    except Exception as e:
        print(f"Error during measurement: {e}")
        import traceback
        traceback.print_exc()

    # Cleanup
    if not args.keep and not args.local:
        try:
            os.remove(video_path)
            print(f"\nCleaned up: {video_path}")
        except:
            pass

    print("\nDone!")


if __name__ == "__main__":
    main()
