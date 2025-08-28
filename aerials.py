#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "requests>=2.32.3,<3.0.0",
#     "tqdm>=4.67.1,<5.0.0",
#     "urllib3>=2.2.3,<2.3.0",
# ]
# [tool.uv]
# exclude-newer = "2025-08-27T00:00:00Z"
# ///
# Forked and adapted from https://github.com/mikeswanson/WallGet and
# https://github.com/lejacobroy/aerials-downloader

"""macOS Aerial Live Wallpaper Downloader.

This script downloads, manages, and lists macOS Aerial live wallpapers.
It can work in both interactive and non-interactive modes, supporting
download, delete, and list operations on wallpaper categories.

Features:
- Download wallpapers from Apple's servers
- Delete existing wallpapers
- List available wallpapers
- Category-based filtering
- Progress tracking with tqdm
- Parallel downloads for better performance
- Both interactive and command-line interfaces

Usage:
    Interactive: uv run aerials.py
    Download:    uv run aerials.py -d -c 1
    Delete:      uv run aerials.py -x -c 1,2
    List:        uv run aerials.py -l -c all
"""

import argparse
import http.client
import json
import pathlib
import plistlib
import ssl
import sys
import textwrap
import time
import urllib.parse
import warnings
from multiprocessing.pool import ApplyResult, ThreadPool
from pathlib import Path
from typing import Any, Literal, TypedDict

import requests
import tqdm
import urllib3

AERIALS_PATH: Path = (
    pathlib.Path.home() / "Library/Application Support/com.apple.wallpaper/aerials"
)
STRINGS_PATH: Path = (
    AERIALS_PATH / "manifest/TVIdleScreenStrings.bundle/en.lproj/Localizable.nocache.strings"
)
ENTRIES_PATH: Path = AERIALS_PATH / "manifest/entries.json"
VIDEO_PATH: Path = AERIALS_PATH / "videos"

# Constants
CHUNK_SIZE: int = 32 * 1024  # 32KB chunks for downloading
REQUEST_TIMEOUT: int = 10  # seconds
DEFAULT_NAME_LENGTH: int = 30  # default length for formatted names
CACHE_EXPIRY_DAYS: int = 90  # Cache expiry in days
CACHE_FILE: Path = AERIALS_PATH / "cache.json"


# Type aliases for better readability
class ContentLengthCacheEntry(TypedDict):
    """A cache entry for content length."""

    length: int
    timestamp: float


AssetItem = tuple[str, str, str, int]  # (label, url, file_path, size)
Category = dict[str, Any]
AssetEntry = dict[str, Any]
Strings = dict[str, str]
ContentLengthCache = dict[str, ContentLengthCacheEntry]


def parse_arguments() -> argparse.Namespace:
    """Parses command-line arguments.

    Returns:
        Parsed command-line arguments.
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="macOS Aerial Live Wallpaper Downloader",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
            Examples:
              %(prog)s                    # Interactive mode
              %(prog)s -d -c 1            # Download category 1
              %(prog)s -x -c 2,3          # Delete categories 2 and 3
              %(prog)s -l -c all          # List all categories
              %(prog)s -d -c all          # Download all categories
        """),
    )

    # Action group (mutually exclusive)
    action_group: argparse._ArgumentGroup = parser.add_mutually_exclusive_group(required=False)
    action_group.add_argument("-d", "--download", action="store_true", help="Download wallpapers")
    action_group.add_argument("-x", "--delete", action="store_true", help="Delete wallpapers")
    action_group.add_argument("-l", "--list", action="store_true", help="List wallpapers")

    # Category selection
    parser.add_argument(
        "-c", "--category", type=str, help="Category number(s) or 'all' (e.g., 1, 2,3, all)"
    )

    # Skip confirmation
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompts")

    # Clear cache
    parser.add_argument(
        "-cc", "--clear-cache", action="store_true", help="Clear the content length cache"
    )

    return parser.parse_args()


def parse_category_selection(category_arg: str | None, num_categories: int) -> list[int]:
    """Parses category selection from command-line arguments.

    Args:
        category_arg: Category argument string (e.g., "1,2,3")
        num_categories: Total number of available categories

    Returns:
        List of category indices (1-based)
    """
    if not category_arg:
        return []

    if category_arg.lower() == "all":
        return list(range(1, num_categories + 1))

    try:
        # Parse comma-separated numbers
        categories: list[int] = [int(c.strip()) for c in category_arg.split(",")]
    except ValueError as e:
        print(f"❌ Invalid category selection: {e}")
        sys.exit(1)

    # Check if any category is the "all" option (which is num_categories + 1)
    if (num_categories + 1) in categories:
        return list(range(1, num_categories + 1))

    # Validate range for other categories
    for cat in categories:
        if cat < 1 or cat > num_categories:
            print(f"❌ Invalid category selection: {cat}")
            sys.exit(1)
    return categories


def get_action_from_args(args: argparse.Namespace) -> tuple[str, str]:
    """Gets action from command-line arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Tuple of (action_code, action_text)
    """
    if args.download:
        return "d", "download"
    if args.delete:
        return "x", "delete"
    if args.list:
        return "l", "list"
    return "", ""


def print_summary(items: list, action: str, elapsed_time: float, total_bytes: int) -> None:
    """Prints a summary of the operation.

    Args:
        items: List of items that were processed
        action: Action that was performed (download, delete, list)
        elapsed_time: Time taken for the operation in seconds
        total_bytes: Total bytes processed
    """
    print("\n" + "=" * 50)
    print("📊 OPERATION SUMMARY")
    print("=" * 50)
    print(f"Action: {action.capitalize()}")
    print(f"Files processed: {len(items)}")
    print(f"Total size: {format_bytes(total_bytes)}")
    print(f"Time elapsed: {elapsed_time:.1f}s")
    if elapsed_time > 0:
        print(f"Average speed: {format_bytes(int(total_bytes / elapsed_time))}/s")
    print("=" * 50)


def validate_environment() -> None:
    """Validates that all required paths and files exist."""
    if not pathlib.Path(AERIALS_PATH).is_dir():
        print("❌ Unable to find aerials path.")
        sys.exit()
    if not pathlib.Path(STRINGS_PATH).is_file():
        print("❌ Unable to find localizable strings file.")
        sys.exit()
    if not pathlib.Path(ENTRIES_PATH).is_file():
        print("❌ Unable to find entries.json file.")
        sys.exit()
    if not pathlib.Path(VIDEO_PATH).is_dir():
        print("❌ Unable to find video path.")
        sys.exit()


def load_asset_data() -> tuple[Strings, AssetEntry]:
    """Loads localizable strings and asset entries.

    Returns:
        A tuple containing the localizable strings and asset entries.
    """
    print("📂 Loading asset data...")
    with pathlib.Path(STRINGS_PATH).open("rb") as fp:
        strings: Strings = plistlib.load(fp)

    with pathlib.Path(ENTRIES_PATH).open(encoding="utf-8") as fp:
        asset_entries: AssetEntry = json.load(fp)

    return strings, asset_entries


def display_categories(categories: list[Category], strings: Strings) -> int:
    """Displays available categories and returns the number of categories.

    Args:
        categories: A list of categories.
        strings: A dictionary of localizable strings.

    Returns:
        The number of categories.
    """
    print("🟢 Available categories:")
    print("-" * 50)
    item = 0
    for category in categories:
        name: str = strings.get(category.get("localizedNameKey", ""), "")
        item += 1
        print(f"{item:2d}. {name}")
    print(f"{item + 1:2d}. All")
    print()
    return item


def select_category(
    categories: list[Category], strings: Strings, num_categories: int
) -> tuple[str | None, str]:
    """Handles category selection and returns category ID and name.

    Args:
        categories: A list of categories.
        strings: A dictionary of localizable strings.
        num_categories: The number of categories.

    Returns:
        A tuple containing the category ID and name.
    """
    category_index: int = as_int(input("Choose category number: "))
    if category_index < 1 or category_index > num_categories + 1:
        print("\n❌ No category selected.")
        sys.exit()

    if category_index == num_categories + 1:
        # "All" option selected
        return None, "All"

    # Regular category selected
    category: Category = categories[category_index - 1]
    category_id: str = category["id"]
    selected_category: str = category["localizedNameKey"]

    print(f"✅ Selected: {strings.get(selected_category, selected_category)}")
    print()
    return category_id, selected_category


def select_action() -> tuple[str, Literal["delete", "download", "list"]]:
    """Handles action selection and returns action code and text.

    Returns:
        A tuple containing the action code and text.
    """
    while True:
        action = input("Download (d), delete (x), or list (l)? ").strip().lower()
        if action in {"d", "x", "l"}:
            break
        print("❌ Please enter 'd', 'x', or 'l'")

    action_text: Literal["delete", "download", "list"] = (
        "download" if action == "d" else "delete" if action == "x" else "list"
    )
    print(f"✅ Action: {action_text.capitalize()}")
    print()
    return action, action_text


def analyze_assets(
    asset_entries: AssetEntry,
    strings: Strings,
    category_ids: list[str | None],
    action: str,
) -> tuple[list[AssetItem], int]:
    """Analyzes assets and returns items to process and total bytes.

    Args:
        asset_entries: A dictionary of asset entries.
        strings: A dictionary of localizable strings.
        category_ids: A list of category IDs to filter by (None means all
            categories).
        action: The action to perform.

    Returns:
        A tuple containing the items to process and the total bytes.
    """
    print(f"🔄 Analyzing {get_action_text(action)} requirements...")
    items: list[AssetItem] = []
    total_bytes: int = 0
    total_assets: int = len(asset_entries.get("assets", []))

    with tqdm.tqdm(total=total_assets, desc="🔍 Scanning assets", unit="asset") as pbar:
        for asset in asset_entries.get("assets", []):
            # On macOS 26, default wallpapers have a category ID that is off by
            # the last character
            asset_categories: list[str] = [
                category.split("-")[0] for category in asset.get("categories", [])
            ]
            # Check if asset belongs to any of the selected categories
            if category_ids and not any(
                cat_id.split("-")[0] in asset_categories
                for cat_id in category_ids
                if cat_id is not None
            ):
                pbar.update(1)
                continue

            label: str = strings.get(asset.get("localizedNameKey", ""), "")
            # Fallback to accessibilityLabel for videos where localizedNameKey
            # is missing (e.g. "Tea Gardens Day" or "Goa Beaches")
            if not label:
                label: str = asset.get("accessibilityLabel", "")

            id_: str = asset.get("id", "")

            # NOTE: May need to update this key logic if new formats are added
            url: str = asset.get("url-4K-SDR-240FPS", "")

            # Valid asset?
            if not label or not id_ or not url:
                pbar.update(1)
                continue

            path: str = urllib.parse.urlparse(url).path
            ext: str = pathlib.Path(path).suffix
            file_path: str = f"{VIDEO_PATH}/{id_}{ext}"

            # Download if file doesn't exist or is the wrong size
            file_exists: bool = pathlib.Path(file_path).is_file()
            file_size: int = pathlib.Path(file_path).stat().st_size if file_exists else 0
            if action in {"d", "l"}:
                content_length: int = get_content_length(url)
                if action == "l" or not file_exists or file_size != content_length:
                    items.append((label, url, file_path, content_length))
                    total_bytes += content_length
            elif action == "x" and file_exists:
                items.append((format_name(label), url, file_path, file_size))
                total_bytes += file_size

            pbar.update(1)

    print(f"✅ Analysis complete: {len(items)} files to {get_action_text(action)}")
    print()
    return items, total_bytes


def get_action_text(action: str) -> str:
    """Converts action code to readable text.

    Args:
        action: The action to convert.

    Returns:
        The readable text of the action.
    """
    return "download" if action == "d" else "delete" if action == "x" else "list"


def list_files(items: list[AssetItem]) -> None:
    """Lists files that would be processed.

    Args:
        items: A list of items to list.
    """
    print("=" * 50)
    print("📂 Listing files...")
    print("=" * 50)
    for item in items:
        print(f"{format_name(item[0])} - {pathlib.Path(item[2]).name}")


def confirm_operation(action_text: str, items: list, total_bytes: int) -> bool:
    """Asks user to confirm the operation.

    Args:
        action_text: The action to confirm.
        items: A list of items to confirm.
        total_bytes: The total bytes of the items.

    Returns:
        True if the user confirms the operation, False otherwise.
    """
    print("⚙️ System Information:")
    print(f"  Files to {action_text}: {len(items)}")
    print(f"  Total size: {format_bytes(total_bytes)}")
    print()

    proceed = input(f"Proceed with {action_text}? (y/n) ").strip().lower()
    if proceed != "y":
        print("❌ Operation cancelled.")
        return False
    return True


def download_files(items: list[AssetItem], total_bytes: int) -> None:
    """Downloads files in parallel with progress tracking.

    Args:
        items: A list of items to download.
        total_bytes: The total bytes of the items.
    """
    start_time: float = time.time()
    print(f"\n📥 Downloading {len(items)} files in parallel...")
    print("=" * 50)
    results: list[str] = []
    with (
        tqdm.tqdm(total=len(items), desc="Overall Progress", unit="file") as overall_pbar,
        ThreadPool() as pool,
    ):
        futures: list[ApplyResult[str]] = [
            pool.apply_async(download_file_with_progress, (item,)) for item in items
        ]
        for future in futures:
            result: str = future.get()
            results.append(result)
            overall_pbar.update(1)

    elapsed_time: float = time.time() - start_time
    print_summary(items, "download", elapsed_time, total_bytes)


def delete_files(items: list[AssetItem], total_bytes: int) -> None:
    """Deletes files with progress tracking.

    Args:
        items: A list of items to delete.
        total_bytes: The total bytes of the items.
    """
    start_time: float = time.time()
    print(f"\n🗑️ Deleting {len(items)} files...")
    print("=" * 50)

    with tqdm.tqdm(total=len(items), desc="Deleting files", unit="file") as pbar:
        for item in items:
            _, _, file_path, _ = item
            pathlib.Path(file_path).unlink()
            pbar.update(1)

    elapsed_time: float = time.time() - start_time
    print_summary(items, "delete", elapsed_time, total_bytes)


def as_int(s: str) -> int:
    """Converts a string to an integer, returning -1 on failure.

    Args:
        s: String to convert

    Returns:
        Integer value or -1 if conversion fails
    """
    try:
        return int(s)
    except ValueError:
        return -1


def format_bytes(bytes_: int) -> str:
    """Formats bytes into human-readable format.

    Args:
        bytes_: Number of bytes to format

    Returns:
        Formatted string with appropriate unit
    """
    if bytes_ == 0:
        return "0 bytes"
    if bytes_ == 1:
        return "1 byte"

    units = [
        (1 << 50, "PB"),
        (1 << 40, "TB"),
        (1 << 30, "GB"),
        (1 << 20, "MB"),
        (1 << 10, "KB"),
        (1, "bytes"),
    ]

    for factor, suffix in units:
        if bytes_ >= factor:
            return f"{bytes_ / factor:.2f} {suffix}"

    return f"{bytes_} bytes"


def format_name(name: str, length: int = DEFAULT_NAME_LENGTH) -> str:
    """Formats a string name to an exact length, with ... if truncated.

    Args:
        name: The string to format.
        length: The exact length of the string.

    Returns:
        The formatted string.
    """
    if len(name) <= length:
        return f"{name:<{length}}"
    return f"{name[: length - 3]}..."


def connect(parsed_url: urllib.parse.ParseResult) -> http.client.HTTPConnection:
    """Creates an HTTP connection for the given URL.

    Args:
        parsed_url: Parsed URL object

    Returns:
        HTTP connection object
    """
    if parsed_url.scheme == "https":
        # Disable SSL verification for compatibility
        context: ssl.SSLContext = ssl._create_unverified_context()  # noqa: SLF001, S323
        return http.client.HTTPSConnection(parsed_url.netloc, context=context)
    return http.client.HTTPConnection(parsed_url.netloc)


def load_cache() -> ContentLengthCache:
    """Loads the content length cache from disk.

    Returns:
        The loaded cache dictionary, or empty dict if loading fails.
    """
    if not CACHE_FILE.is_file():
        return {}

    try:
        with CACHE_FILE.open("r", encoding="utf-8") as f:
            cache: ContentLengthCache = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"⚠️ Error loading cache file {CACHE_FILE}: {e}")
        print("Starting with fresh cache.")
        return {}
    return cache


def save_cache(cache: ContentLengthCache) -> None:
    """Saves the content length cache to disk.

    Args:
        cache: The cache dictionary to save.
    """
    try:
        # Ensure the cache directory exists
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with CACHE_FILE.open("w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except OSError as e:
        print(f"❌ Error saving cache to {CACHE_FILE}: {e}")


def get_content_length(url: str) -> int:
    """Get content length from URL, using cache when possible.

    Args:
        url: The URL to get the content length from.

    Returns:
        The content length of the URL.
    """
    # Load cache
    cache: ContentLengthCache = load_cache()

    # Check cache for URL
    if url in cache:
        entry = cache[url]
        # Check if cache is expired
        if time.time() - entry["timestamp"] < CACHE_EXPIRY_DAYS * 24 * 60 * 60:
            return entry["length"]

    # Fetch from URL
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        req: requests.Response = requests.head(url, verify=False, timeout=REQUEST_TIMEOUT)  # noqa: S501
    content_length: int = int(req.headers["Content-Length"])

    # Update cache
    cache[url] = {"length": content_length, "timestamp": time.time()}

    # Save cache
    save_cache(cache)

    return content_length


def download_file_with_progress(download: AssetItem) -> str:
    """Download a file with progress bar.

    Args:
        download: A tuple containing the label, URL, file path, and content
        length.

    Returns:
        The label of the downloaded file.
    """
    label, url, file_path, content_length = download
    parsed_url: str = urllib.parse.urlparse(url).geturl()
    headers: dict[str, str] = {"Range": f"bytes={0}-"}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        req: requests.Response = requests.get(
            parsed_url,
            stream=True,
            headers=headers,
            verify=False,  # noqa: S501
            timeout=REQUEST_TIMEOUT,
        )
    try:
        req.raise_for_status()
    except requests.exceptions.HTTPError:
        print(f"❌ Error downloading {label}: HTTP {req.status_code}")
        return label

    with pathlib.Path(file_path).open("wb") as f:
        # If content_length is not available, use None for unknown total
        total: int | None = content_length if content_length > 0 else None
        with tqdm.tqdm(
            total=total,
            desc=format_name(label),
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            leave=False,
            initial=0,
        ) as pbar:
            for chunk in req.iter_content(chunk_size=32 * 1024):
                f.write(chunk)
                pbar.update(len(chunk))

    return label


def clear_cache() -> None:
    """Clears the content length cache file."""
    if CACHE_FILE.is_file():
        print(f"🗑️ Clearing cache file: {CACHE_FILE}")
        try:
            CACHE_FILE.unlink()
            print("✅ Cache cleared.")
        except OSError as e:
            print(f"❌ Error clearing cache: {e}")
    else:
        print(f"ℹ️ Cache file not found: {CACHE_FILE}")  # noqa: RUF001


def main() -> None:
    """Main function for the macOS Aerial Live Wallpaper Downloader."""
    print("🖥️ macOS Aerial Live Wallpaper Downloader")
    print("=" * 50)
    print()

    # Parse command-line arguments
    args: argparse.Namespace = parse_arguments()

    if args.clear_cache:
        clear_cache()

    interactive_mode: bool = not any([args.download, args.delete, args.list])

    validate_environment()

    strings, asset_entries = load_asset_data()

    categories: list[Category] = asset_entries.get("categories", [])
    num_categories: int = display_categories(categories, strings)

    if interactive_mode:
        # Interactive mode - ask user for input
        category_id, _ = select_category(categories, strings, num_categories)
        category_ids: list[str | None] = [category_id]
        action, action_text = select_action()
        skip_confirmation: bool = False
    else:
        # Non-interactive mode - use command-line arguments
        action, action_text = get_action_from_args(args)

        # Parse category selection
        selected_categories: list[int] = parse_category_selection(args.category, num_categories)
        if not selected_categories:
            print("❌ No category selected. Use -c/--category (e.g., -c 1, -c 1,2, -c all)")
            sys.exit(1)

        # Convert category numbers to category IDs
        category_ids: list[str | None] = []
        for cat in selected_categories:
            category_ids.append(categories[cat - 1]["id"] if cat <= num_categories else None)

        print(f"✅ Selected categories: {', '.join(str(c) for c in selected_categories)}")
        print(f"✅ Action: {action_text.capitalize()}")
        print()

        skip_confirmation: bool = args.yes

    # Analyze assets
    items, total_bytes = analyze_assets(asset_entries, strings, category_ids, action)

    # Anything to process?
    if not items:
        print(f"ℹ️ Nothing to {action_text}.")  # noqa: RUF001
        sys.exit()

    # Handle list action
    if action == "l":
        list_files(items)
        sys.exit()

    # Confirm operation (skip if -y flag or non-interactive mode)
    if not skip_confirmation and not confirm_operation(action_text, items, total_bytes):
        sys.exit()

    # Execute operation
    if action == "d":
        download_files(items, total_bytes)
    elif action == "x":
        delete_files(items, total_bytes)

    print("\n🎉 Operation completed successfully!")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🚨 Operation cancelled by user.")
        sys.exit(1)
