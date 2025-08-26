# /// script
# requires-python = ">=3.13,<3.14"
# dependencies = [
#     "requests>=2.32.3,<3.0.0",
#     "tqdm>=4.67.1,<5.0.0",
#     "urllib3>=2.2.3,<2.3.0",
# ]
# ///
# Forked from https://github.com/joshuaclayton/wallget and https://github.com/lejacobroy/aerials-downloader
import http.client
import json
import pathlib
import plistlib
import ssl
import sys
import time
import urllib.parse
import warnings
from multiprocessing.pool import ApplyResult, ThreadPool
from pathlib import Path
from typing import Any, Literal

import requests
import tqdm
import urllib3

AERIALS_PATH: Path = (
    pathlib.Path.home() / "Library/Application Support/com.apple.wallpaper/aerials"
)
STRINGS_PATH: Path = (
    AERIALS_PATH
    / "manifest/TVIdleScreenStrings.bundle/en.lproj/Localizable.nocache.strings"
)
ENTRIES_PATH: Path = AERIALS_PATH / "manifest/entries.json"
VIDEO_PATH: Path = AERIALS_PATH / "videos"


def print_summary(
    items: list, action: str, elapsed_time: float, total_bytes: int
) -> None:
    """Print a summary of the operation."""
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


def main() -> None:
    print("WallGet Live Wallpaper Download/Delete Script")
    print("=" * 50)
    print()

    # Validate environment
    print("Validating environment...")
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
    print("✅ Environment validated successfully")
    print()

    # Read localizable strings
    print("Loading asset data...")
    with pathlib.Path(STRINGS_PATH).open("rb") as fp:
        strings: Any = plistlib.load(fp)

    # Read asset entries
    with pathlib.Path(ENTRIES_PATH).open(encoding="utf-8") as fp:
        asset_entries: dict[str, Any] = json.load(fp)

    # Show categories
    print("Available categories:")
    print("-" * 30)
    item = 0
    categories: list[dict[str, Any]] = asset_entries.get("categories", [])
    for category in categories:
        name: str = strings.get(category.get("localizedNameKey", ""), "")
        item += 1
        print(f"{item:2d}. {name}")
    print(f"{item + 1:2d}. All")
    print()

    # Select category
    category_index: int = as_int(input("Category number? "))
    if category_index < 1 or category_index > item + 1:
        print("\n❌ No category selected.")
        sys.exit()
    category_id: str | None = (
        categories[int(category_index) - 1]["id"] if category_index <= item else None
    )
    selected_category: str = (
        categories[int(category_index) - 1]["localizedNameKey"]
        if category_index <= item
        else "All"
    )
    print(f"✅ Selected: {strings.get(selected_category, selected_category)}")
    print()

    # Download, delete, or list?
    action = input("Download (d), delete (x), or list (l)? ").strip().lower()
    if action not in {"d", "x", "l"}:
        print("\n❌ No action selected.")
        sys.exit()
    action_text: Literal["delete", "download", "list"] = (
        "download" if action == "d" else "delete" if action == "x" else "list"
    )
    print(f"✅ Action: {action_text.capitalize()}")
    print()

    # Determine items
    print(f"Analyzing {action_text} requirements...")
    items: list[tuple[str, str, str, int]] = []
    total_bytes: int = 0
    total_assets: int = len(asset_entries.get("assets", []))

    with tqdm.tqdm(total=total_assets, desc="Scanning assets", unit="asset") as pbar:
        for asset in asset_entries.get("assets", []):
            # On macOS 26, default wallpapers have a category ID that is off by
            # the last character
            asset_categories: list[str] = [
                category.split("-")[0] for category in asset.get("categories", [])
            ]
            if category_id and category_id.split("-")[0] not in asset_categories:
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
            file_size: int = (
                pathlib.Path(file_path).stat().st_size if file_exists else 0
            )
            if action in {"d", "l"}:
                content_length: int = get_content_length(url)
                if action == "l" or not file_exists or file_size != content_length:
                    items.append((label, url, file_path, content_length))
                    total_bytes += content_length
            elif action == "x" and file_exists:
                items.append((format_name(label), url, file_path, file_size))
                total_bytes += file_size

            pbar.update(1)

    print(f"✅ Analysis complete: {len(items)} files to {action_text}")
    print()

    # Anything to process?
    if not items:
        print(f"ℹ️  Nothing to {action_text}.")  # noqa: RUF001
        sys.exit()

    print("System Information:")
    print(f"  Files to {action_text}: {len(items)}")
    print(f"  Total size: {format_bytes(total_bytes)}")
    print()

    if action == "l":
        print("=" * 50)
        print("📂 Listing files...")
        print("=" * 50)
        for item in items:
            print(f"{format_name(item[0])} - {pathlib.Path(item[2]).name}")
        sys.exit()

    proceed = input(f"Proceed with {action_text}? (y/n) ").strip().lower()
    if proceed != "y":
        print("❌ Operation cancelled.")
        sys.exit()

    if action == "d":
        start_time: float = time.time()
        print(f"\n📥 Downloading {len(items)} files in parallel...")
        print("=" * 50)
        results: list[str] = []
        with (
            tqdm.tqdm(
                total=len(items), desc="Overall Progress", unit="file"
            ) as overall_pbar,
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
        print_summary(items, action_text, elapsed_time, total_bytes)

    elif action == "x":
        start_time: float = time.time()
        print(f"\n🗑️  Deleting {len(items)} files...")
        print("=" * 50)

        deleted_count: int = 0
        with tqdm.tqdm(total=len(items), desc="Deleting files", unit="file") as pbar:
            for item in items:
                _, _, file_path, _ = item
                pathlib.Path(file_path).unlink()
                deleted_count += 1
                pbar.update(1)

        elapsed_time: float = time.time() - start_time
        print_summary(items, action_text, elapsed_time, total_bytes)

    print("\n🎉 Operation completed successfully!")


def as_int(s: str) -> int:
    try:
        return int(s)
    except ValueError:
        return -1


def format_bytes(bytes_: int) -> str:
    units: tuple[
        tuple[int, Literal["PB"]],
        tuple[int, Literal["TB"]],
        tuple[int, Literal["GB"]],
        tuple[int, Literal["MB"]],
        tuple[int, Literal["KB"]],
        tuple[Literal[1], Literal["bytes"]],
    ] = (
        (1 << 50, "PB"),
        (1 << 40, "TB"),
        (1 << 30, "GB"),
        (1 << 20, "MB"),
        (1 << 10, "KB"),
        (1, "bytes"),
    )
    if bytes_ == 1:
        return "1 byte"
    for factor, _suffix in units:
        if bytes_ >= factor:
            break
    return f"{bytes_ / factor:.2f} {_suffix}"


def format_name(name: str, length: int = 30) -> str:
    """Format a string name to an exact length, with ... if truncated.

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
    # disable SSL verification
    context: ssl.SSLContext = ssl._create_unverified_context()  # noqa: SLF001, S323
    return (
        http.client.HTTPSConnection(parsed_url.netloc, context=context)
        if parsed_url.scheme == "https"
        else http.client.HTTPConnection(parsed_url.netloc)
    )


def get_content_length(url: str) -> int:
    """Get content length from URL.

    Args:
        url: The URL to get the content length from.

    Returns:
        The content length of the URL.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
        req: requests.Response = requests.head(url, verify=False, timeout=10)
    return int(req.headers["Content-Length"])


def download_file_with_progress(download: tuple[str, str, str, int]) -> str:
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
            parsed_url, stream=True, headers=headers, verify=False, timeout=10
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


if __name__ == "__main__":
    main()
