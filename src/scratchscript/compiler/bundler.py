"""Bundler — combines project.json + assets into a .sb3 ZIP file,
and unbundles .sb3 files back to project.json."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Optional

from ..assets.library import (
    ASSET_CACHE,
    DEFAULT_BACKDROP_ASSET_ID,
    DEFAULT_BACKDROP_MD5EXT,
    AssetLibrary,
    get_library,
)


def unbundle(sb3_path: str | Path) -> dict:
    """Extract project.json from an .sb3 file.

    Args:
        sb3_path: Path to the .sb3 file.

    Returns:
        The parsed project.json dict.

    Raises:
        FileNotFoundError: If the .sb3 file doesn't exist.
        KeyError: If project.json is missing from the archive.
        zipfile.BadZipFile: If the file isn't a valid ZIP.
    """
    sb3_path = Path(sb3_path)
    with zipfile.ZipFile(sb3_path, "r") as zf:
        return json.loads(zf.read("project.json"))


async def bundle(
    project_json: dict,
    output_path: str | Path,
    library: Optional[AssetLibrary] = None,
) -> Path:
    """Bundle project.json and required assets into an .sb3 file.

    Args:
        project_json: The complete project.json dict
        output_path: Path for the output .sb3 file
        library: Optional AssetLibrary instance (will create one if not provided)

    Returns:
        Path to the created .sb3 file
    """
    output_path = Path(output_path)
    if library is None:
        library = await get_library()

    # Collect all required assets from the project
    required_assets: set[str] = set()
    for target in project_json.get("targets", []):
        for costume in target.get("costumes", []):
            md5ext = costume.get("md5ext")
            if md5ext:
                required_assets.add(md5ext)
        for sound in target.get("sounds", []):
            md5ext = sound.get("md5ext")
            if md5ext:
                required_assets.add(md5ext)

    # Resolve assets: try to look up real assets and update project.json
    resolved_assets: dict[str, Path] = {}
    project_json = _resolve_assets(project_json, library, resolved_assets)

    # Download required assets
    for md5ext in list(required_assets):
        cache_path = ASSET_CACHE / md5ext
        if cache_path.exists():
            resolved_assets[md5ext] = cache_path
        else:
            try:
                path = await library.download_asset(md5ext)
                resolved_assets[md5ext] = path
            except Exception:
                # Asset not found — will use fallback
                pass

    # Recollect after resolution
    final_assets: set[str] = set()
    for target in project_json.get("targets", []):
        for costume in target.get("costumes", []):
            md5ext = costume.get("md5ext")
            if md5ext:
                final_assets.add(md5ext)
        for sound in target.get("sounds", []):
            md5ext = sound.get("md5ext")
            if md5ext:
                final_assets.add(md5ext)

    # Create the .sb3 ZIP
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        # Write project.json (compact, no pretty print)
        zf.writestr("project.json", json.dumps(project_json, separators=(",", ":")))

        # Write asset files
        for md5ext in final_assets:
            if md5ext in resolved_assets and resolved_assets[md5ext].exists():
                zf.write(resolved_assets[md5ext], md5ext)
            elif md5ext == DEFAULT_BACKDROP_MD5EXT:
                # Write default backdrop
                zf.writestr(md5ext, library.get_default_backdrop_svg())
            else:
                # Create a minimal fallback SVG
                fallback_svg = _fallback_svg()
                zf.writestr(md5ext, fallback_svg)

    return output_path


def _resolve_assets(
    project_json: dict,
    library: AssetLibrary,
    resolved: dict[str, Path],
) -> dict:
    """Resolve placeholder asset hashes to real Scratch asset IDs."""
    import copy
    pj = copy.deepcopy(project_json)

    for target in pj.get("targets", []):
        is_stage = target.get("isStage", False)

        # Resolve costumes
        new_costumes = []
        for costume in target.get("costumes", []):
            name = costume.get("name", "")
            resolved_info = None

            if is_stage:
                resolved_info = library.lookup_backdrop(name)
            if not resolved_info:
                resolved_info = library.lookup_costume(name)

            if resolved_info:
                costume["assetId"] = resolved_info["assetId"]
                costume["md5ext"] = resolved_info["md5ext"]
                costume["dataFormat"] = resolved_info["dataFormat"]
                costume["rotationCenterX"] = resolved_info.get("rotationCenterX", costume.get("rotationCenterX", 48))
                costume["rotationCenterY"] = resolved_info.get("rotationCenterY", costume.get("rotationCenterY", 50))

            new_costumes.append(costume)
        target["costumes"] = new_costumes

        # Resolve sounds
        new_sounds = []
        for sound in target.get("sounds", []):
            name = sound.get("name", "")
            resolved_info = library.lookup_sound(name)
            if resolved_info:
                sound["assetId"] = resolved_info["assetId"]
                sound["md5ext"] = resolved_info["md5ext"]
                sound["dataFormat"] = resolved_info["dataFormat"]
                sound["rate"] = resolved_info.get("rate", 48000)
                sound["sampleCount"] = resolved_info.get("sampleCount", 0)
            new_sounds.append(sound)
        target["sounds"] = new_sounds

    return pj


def _fallback_svg() -> bytes:
    """Generate a minimal fallback SVG for missing assets."""
    svg = (
        '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" '
        'width="96" height="100" viewBox="0 0 96 100">'
        '<rect width="96" height="100" fill="#855CD6" rx="10"/>'
        '<text x="48" y="55" text-anchor="middle" fill="white" '
        'font-size="12" font-family="sans-serif">?</text>'
        "</svg>"
    )
    return svg.encode("utf-8")


def bundle_sync(
    project_json: dict,
    output_path: str | Path,
) -> Path:
    """Synchronous version of bundle — no asset resolution, just packages what's there."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Collect all required assets
    required_md5exts: set[str] = set()
    for target in project_json.get("targets", []):
        for costume in target.get("costumes", []):
            md5ext = costume.get("md5ext")
            if md5ext:
                required_md5exts.add(md5ext)
        for sound in target.get("sounds", []):
            md5ext = sound.get("md5ext")
            if md5ext:
                required_md5exts.add(md5ext)

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("project.json", json.dumps(project_json, separators=(",", ":")))

        for md5ext in required_md5exts:
            cache_path = ASSET_CACHE / md5ext
            if cache_path.exists():
                zf.write(cache_path, md5ext)
            else:
                zf.writestr(md5ext, _fallback_svg())

    return output_path
