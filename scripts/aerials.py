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
# exclude-newer = "2026-02-12T00:00:00Z"
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
    List:        uv run aerials.py -l
    Open:        uv run aerials.py -o
"""

import argparse
import json
import locale
import pathlib
import plistlib
import sys
import textwrap
import time
import urllib.parse
import warnings
import webbrowser
from multiprocessing.pool import ApplyResult, ThreadPool
from pathlib import Path
from typing import Any, Literal, TypedDict, cast

import requests
import tqdm
import urllib3

AERIALS_PATH: Path = (
    pathlib.Path.home() / "Library/Application Support/com.apple.wallpaper/aerials"
)
LEGACY_STRINGS_PATH: Path = (
    AERIALS_PATH / "manifest/TVIdleScreenStrings.bundle/en.lproj/Localizable.nocache.strings"
)
MODERN_STRINGS_PATH: Path = (
    AERIALS_PATH
    / "manifest/TVIdleScreenStrings.bundle/Contents/Resources/Localizable.nocache.loctable"
)
ENTRIES_PATH: Path = AERIALS_PATH / "manifest/entries.json"
VIDEO_PATH: Path = AERIALS_PATH / "videos"

# Constants
CHUNK_SIZE: int = 32 * 1024  # 32KB chunks for downloading
REQUEST_TIMEOUT: int = 10  # seconds
MAX_DOWNLOAD_RETRIES: int = 3
RETRY_BACKOFF_SECONDS: int = 2
HTTP_STATUS_OK: int = 200
HTTP_STATUS_RANGE_NOT_SATISFIABLE: int = 416
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
              %(prog)s -l                 # List all categories (same as -l -c all)
              %(prog)s -d                 # Download all categories (same as -d -c all)
              %(prog)s -o                 # Open video directory in Finder
        """),
    )

    # Action group (mutually exclusive)
    action_group: argparse._ArgumentGroup = parser.add_mutually_exclusive_group(required=False)
    action_group.add_argument("-d", "--download", action="store_true", help="Download wallpapers")
    action_group.add_argument("-x", "--delete", action="store_true", help="Delete wallpapers")
    action_group.add_argument("-l", "--list", action="store_true", help="List wallpapers")
    action_group.add_argument(
        "-o", "--open", action="store_true", help="Open video directory in Finder"
    )

    # Category selection
    parser.add_argument(
        "-c",
        "--category",
        type=str,
        help="Category number(s) or 'all' (e.g., 1, 2,3, all) (default: all)",
        default="all",
    )

    # Skip confirmation
    parser.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompts")

    # Clear cache
    parser.add_argument(
        "-cc", "--clear-cache", action="store_true", help="Clear the content length cache"
    )

    return parser.parse_args()


def open_video_directory() -> None:
    """Opens the video directory in Finder."""
    print(f"📂 Opening video directory: {VIDEO_PATH}")
    webbrowser.open(f"file://{VIDEO_PATH}")


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
    if args.open:
        return "o", "open"
    return "", ""


def print_summary(
    items: list[AssetItem], action: str, elapsed_time: float, total_bytes: int
) -> None:
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
        sys.exit(1)
    if not resolve_strings_path().is_file():
        print("❌ Unable to find localizable strings file.")
        sys.exit(1)
    if not pathlib.Path(ENTRIES_PATH).is_file():
        print("❌ Unable to find entries.json file.")
        sys.exit(1)
    if not pathlib.Path(VIDEO_PATH).is_dir():
        print("❌ Unable to find video path.")
        sys.exit(1)


def load_asset_data() -> tuple[Strings, AssetEntry]:
    """Loads localizable strings and asset entries.

    Returns:
        A tuple containing the localizable strings and asset entries.
    """
    strings: Strings = load_strings(resolve_strings_path())

    with pathlib.Path(ENTRIES_PATH).open(encoding="utf-8") as fp:
        asset_entries: AssetEntry = json.load(fp)

    return strings, asset_entries


def resolve_strings_path(aerials_path: Path = AERIALS_PATH) -> Path:
    """Returns the active strings catalog path for the current macOS layout."""
    legacy_path: Path = (
        aerials_path / "manifest/TVIdleScreenStrings.bundle/en.lproj/Localizable.nocache.strings"
    )
    modern_path: Path = (
        aerials_path
        / "manifest/TVIdleScreenStrings.bundle/Contents/Resources/Localizable.nocache.loctable"
    )
    for path in (legacy_path, modern_path):
        if path.is_file():
            return path
    return legacy_path


def load_strings(strings_path: Path) -> Strings:
    """Load strings from a legacy or modern catalog.

    Args:
        strings_path: Path to the strings catalog to load.

    Returns:
        The selected localized strings for the current catalog.
    """
    with strings_path.open("rb") as fp:
        raw_strings: Any = plistlib.load(fp)

    if strings_path.suffix != ".loctable":
        return raw_strings

    return select_localized_strings(raw_strings)


def select_localized_strings(localizations: object) -> Strings:
    """Select the best localization from a modern `.loctable` plist.

    Args:
        localizations: Raw localization data loaded from the plist.

    Returns:
        The best matching language mapping,
        or an empty mapping when unavailable.
    """
    if not isinstance(localizations, dict):
        return {}
    localized_map = cast("dict[str, object]", localizations)

    preferred_languages: list[str] = []
    default_language, _ = locale.getlocale()
    if default_language:
        preferred_languages.extend([
            default_language,
            default_language.replace("_", "-"),
            default_language.split("_")[0],
        ])
    preferred_languages.append("en")

    for language in preferred_languages:
        localized_strings = localized_map.get(language)
        if isinstance(localized_strings, dict):
            return cast("Strings", localized_strings)

    for localized_strings in localized_map.values():
        if isinstance(localized_strings, dict):
            return cast("Strings", localized_strings)

    return {}


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
    item: int = 0
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
        sys.exit(1)

    if category_index == num_categories + 1:
        # "All" option selected
        return None, "All"

    # Regular category selected
    category: Category = categories[category_index - 1]
    category_id: str = category["id"]
    selected_category: str = category["localizedNameKey"]

    print(f"✅ Selected: {strings.get(selected_category, selected_category)}")
    return category_id, selected_category


def select_action() -> tuple[str, Literal["delete", "download", "list"]]:
    """Handles action selection and returns action code and text.

    Returns:
        A tuple containing the action code and text.
    """
    while True:
        action: str = input("Download (d), delete (x), or list (l)? ").strip().lower()
        if action in {"d", "x", "l"}:
            break
        print("❌ Please enter 'd', 'x', or 'l'")

    action_text: Literal["delete", "download", "list"] = (
        "download" if action == "d" else "delete" if action == "x" else "list"
    )
    print(f"✅ Action: {action_text.capitalize()}")
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
    items: list[AssetItem] = []
    total_bytes: int = 0
    total_assets: int = len(asset_entries.get("assets", []))

    # If "All" category is selected, set category_ids to empty list
    if None in category_ids:
        category_ids = []

    with tqdm.tqdm(total=total_assets, desc="🔍 Scanning assets", unit="asset") as pbar:
        for asset in asset_entries.get("assets", []):
            # On macOS 26, default wallpapers have a category ID that is off by
            # the last character
            asset_categories: list[str] = [
                category.split("-")[0] for category in asset.get("categories", [])
            ]
            # Skip if asset does not belong to any of the selected categories
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
    print("\n" + "=" * 50)
    print("📂 Listing files...")
    print("=" * 50)
    for item in items:
        print(f"{format_name(item[0])} - {pathlib.Path(item[2]).name}")


def confirm_operation(action_text: str, items: list[AssetItem], total_bytes: int) -> bool:
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

    proceed: str = input(f"Proceed with {action_text}? (y/n) ").strip().lower()
    if proceed != "y":
        print("❌ Operation cancelled.")
        return False
    return True


def download_files(items: list[AssetItem], total_bytes: int) -> None:
    """Downloads files in parallel with progress tracking.

    Args:
        items: A list of items to download.
        total_bytes: The total bytes of the items.

    Raises:
        RuntimeError: If one or more files fail to download.
    """
    start_time: float = time.time()
    print(f"\n📥 Downloading {len(items)} files in parallel...")
    print("=" * 50)
    results: list[str] = []
    errors: list[str] = []
    with (
        tqdm.tqdm(total=len(items), desc="Overall Progress", unit="file") as overall_pbar,
        ThreadPool() as pool,
    ):
        futures: list[ApplyResult[str]] = [
            pool.apply_async(download_file_with_progress, (item,)) for item in items
        ]
        for future in futures:
            try:
                result: str = future.get()
                results.append(result)
            except RuntimeError as e:
                errors.append(str(e))
            finally:
                overall_pbar.update(1)

    if errors:
        error_count: int = len(errors)
        error_details: str = "\n".join(f"  - {error}" for error in errors)
        raise RuntimeError(f"Failed to download {error_count} file(s):\n{error_details}")

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

    units: list[tuple[int, str]] = [
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
        entry: ContentLengthCacheEntry = cache[url]
        # Check if cache is expired
        if time.time() - entry["timestamp"] < CACHE_EXPIRY_DAYS * 24 * 60 * 60:
            return entry["length"]

    # Fetch from URL
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        # SSL verification must be disabled for host 'sylvan.apple.com'
        req: requests.Response = requests.head(url, verify=False, timeout=REQUEST_TIMEOUT)  # noqa: S501
    content_length: int = int(req.headers["Content-Length"])

    # Update cache
    cache[url] = ContentLengthCacheEntry(length=content_length, timestamp=time.time())

    # Save cache
    save_cache(cache)

    return content_length


def set_progress(pbar: tqdm.std.tqdm, value: int) -> None:
    """Move a progress bar position when needed.

    Args:
        pbar: Progress bar to update.
        value: New progress value.
    """
    if pbar.n != value:
        pbar.n = value
        pbar.refresh()


def start_download_request(parsed_url: str, headers: dict[str, str]) -> requests.Response:
    """Starts a streaming download request.

    Args:
        parsed_url: URL to download.
        headers: Request headers.

    Returns:
        Streaming HTTP response.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        # SSL verification must be disabled for host 'sylvan.apple.com'.
        return requests.get(
            parsed_url,
            stream=True,
            headers=headers,
            verify=False,  # noqa: S501
            timeout=(REQUEST_TIMEOUT, REQUEST_TIMEOUT * 6),
        )


def write_response_chunks(
    req: requests.Response,
    file_path_obj: Path,
    downloaded: int,
    pbar: tqdm.std.tqdm,
) -> None:
    """Writes streamed response chunks to disk and updates progress."""
    file_mode: str = "ab" if downloaded > 0 else "wb"
    with file_path_obj.open(file_mode) as f:
        for chunk in req.iter_content(chunk_size=CHUNK_SIZE):
            if not chunk:
                continue
            f.write(chunk)
            pbar.update(len(chunk))


def download_file_with_progress(download: AssetItem) -> str:
    """Download a file with progress bar.

    Args:
        download: A tuple containing the label, URL, file path, and content
        length.

    Returns:
        The label of the downloaded file.

    Raises:
        RuntimeError: If download retries are exhausted.
    """
    label, url, file_path, content_length = download
    parsed_url: str = urllib.parse.urlparse(url).geturl()
    file_path_obj: Path = pathlib.Path(file_path)
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
        for attempt in range(1, MAX_DOWNLOAD_RETRIES + 1):
            downloaded: int = file_path_obj.stat().st_size if file_path_obj.is_file() else 0

            if total is not None and downloaded >= total:
                set_progress(pbar, total)
                return label

            set_progress(pbar, downloaded)

            headers: dict[str, str] = {}
            if downloaded > 0:
                headers["Range"] = f"bytes={downloaded}-"

            req: requests.Response | None = None
            try:
                req = start_download_request(parsed_url, headers)

                if (
                    req.status_code == HTTP_STATUS_RANGE_NOT_SATISFIABLE
                    and total is not None
                    and downloaded >= total
                ):
                    set_progress(pbar, total)
                    return label

                req.raise_for_status()

                if downloaded > 0 and req.status_code == HTTP_STATUS_OK:
                    # Server ignored Range header.
                    # Restart to avoid duplicated bytes.
                    downloaded = 0
                    file_path_obj.unlink(missing_ok=True)
                    pbar.reset(total=total)

                write_response_chunks(req, file_path_obj, downloaded, pbar)

                current_size: int = file_path_obj.stat().st_size
                if total is None or current_size >= total:
                    return label
            except (OSError, requests.exceptions.RequestException) as e:
                if attempt == MAX_DOWNLOAD_RETRIES:
                    raise RuntimeError(f"{label}: download failed after retries ({e})") from e
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            finally:
                if req is not None:
                    req.close()

    raise RuntimeError(f"{label}: download failed due to incomplete output")


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
    # Parse command-line arguments
    args: argparse.Namespace = parse_arguments()

    if args.clear_cache:
        clear_cache()

    # Handle open action immediately
    if args.open:
        validate_environment()
        open_video_directory()
        return

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

        skip_confirmation: bool = args.yes

    # Analyze assets
    items, total_bytes = analyze_assets(asset_entries, strings, category_ids, action)

    # Anything to process?
    if not items:
        print(f"✅ Nothing to {action_text}.")
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
