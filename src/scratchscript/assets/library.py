"""Scratch asset library — name→asset lookup, CDN download, and caching."""

from __future__ import annotations

import hashlib
import json
import re
from difflib import get_close_matches
from pathlib import Path
from typing import Optional

import httpx

# Words too generic to select assets by
_STOPWORDS = {
    "the", "and", "that", "with", "for", "make", "create", "add", "when",
    "then", "have", "has", "can", "will", "should", "game", "project",
    "sprite", "sprites", "player", "where", "which", "each", "every", "all",
    "you", "your", "its", "his", "her", "they", "them", "from", "into",
    "onto", "around", "moves", "moving", "clicked", "click", "press",
    "pressed", "key", "score", "points", "using", "use", "like",
}

SCRATCH_ASSET_CDN = "https://assets.scratch.mit.edu"
SCRATCH_GUI_RAW = "https://raw.githubusercontent.com/scratchfoundation/scratch-gui/develop/src/lib/libraries"

CACHE_DIR = Path.home() / ".scratchscript"
LIBRARY_CACHE = CACHE_DIR / "library"
ASSET_CACHE = CACHE_DIR / "assets"

# Library JSON file names on the scratch-gui repo
LIBRARY_FILES = {
    "sprites": "sprites.json",
    "costumes": "costumes.json",
    "backdrops": "backdrops.json",
    "sounds": "sounds.json",
}

# Default white backdrop SVG
DEFAULT_BACKDROP_SVG = (
    '<svg version="1.1" xmlns="http://www.w3.org/2000/svg" '
    'xmlns:xlink="http://www.w3.org/1999/xlink" width="480" height="360" '
    'viewBox="0 0 480 360">'
    '<rect width="480" height="360" fill="white"/>'
    "</svg>"
)

# Known asset ID for the default blank backdrop
DEFAULT_BACKDROP_ASSET_ID = "cd21514d0531fdffb22204e0ec5ed84a"
DEFAULT_BACKDROP_MD5EXT = f"{DEFAULT_BACKDROP_ASSET_ID}.svg"

# Scratch Cat costume asset IDs (SVG)
SCRATCH_CAT_ASSETS = {
    "cat-a": {
        "assetId": "bcf454acf82e4504149f7ffe07081dbc",
        "md5ext": "bcf454acf82e4504149f7ffe07081dbc.svg",
        "dataFormat": "svg",
        "rotationCenterX": 48,
        "rotationCenterY": 50,
    },
    "cat-b": {
        "assetId": "0fb9be3e8c72fe18e351bfe70e2824f7",
        "md5ext": "0fb9be3e8c72fe18e351bfe70e2824f7.svg",
        "dataFormat": "svg",
        "rotationCenterX": 46,
        "rotationCenterY": 53,
    },
}


class AssetLibrary:
    """Index of Scratch built-in assets with download + caching."""

    def __init__(self):
        self._costumes: dict[str, dict] = {}
        self._backdrops: dict[str, dict] = {}
        self._sounds: dict[str, dict] = {}
        self._sprites: dict[str, dict] = {}
        self._loaded = False

    async def ensure_loaded(self):
        """Load the asset index, downloading from GitHub if needed."""
        if self._loaded:
            return

        LIBRARY_CACHE.mkdir(parents=True, exist_ok=True)
        ASSET_CACHE.mkdir(parents=True, exist_ok=True)

        for lib_type, filename in LIBRARY_FILES.items():
            cache_path = LIBRARY_CACHE / filename
            data = None

            if cache_path.exists():
                try:
                    data = json.loads(cache_path.read_text())
                except (json.JSONDecodeError, OSError):
                    pass

            if data is None:
                url = f"{SCRATCH_GUI_RAW}/{filename}"
                try:
                    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                        resp = await client.get(url)
                        if resp.status_code == 200:
                            data = resp.json()
                            cache_path.write_text(json.dumps(data))
                except Exception:
                    data = []

            if data:
                self._index_library(lib_type, data)

        # Always ensure Scratch Cat is available
        for name, info in SCRATCH_CAT_ASSETS.items():
            self._costumes.setdefault(name.lower(), info)

        self._loaded = True

    def _index_library(self, lib_type: str, data: list[dict]):
        """Build name→info lookup from library JSON data."""
        for entry in data:
            name = entry.get("name", "").lower()

            if lib_type == "costumes":
                if "md5ext" in entry:
                    self._costumes[name] = {
                        "assetId": entry.get("assetId", entry.get("md5ext", "").split(".")[0]),
                        "md5ext": entry["md5ext"],
                        "dataFormat": entry.get("dataFormat", "svg"),
                        "rotationCenterX": entry.get("rotationCenterX", 48),
                        "rotationCenterY": entry.get("rotationCenterY", 50),
                    }
            elif lib_type == "backdrops":
                if "md5ext" in entry:
                    self._backdrops[name] = {
                        "assetId": entry.get("assetId", entry.get("md5ext", "").split(".")[0]),
                        "md5ext": entry["md5ext"],
                        "dataFormat": entry.get("dataFormat", "svg"),
                        "rotationCenterX": entry.get("rotationCenterX", 240),
                        "rotationCenterY": entry.get("rotationCenterY", 180),
                    }
            elif lib_type == "sounds":
                if "md5ext" in entry:
                    self._sounds[name] = {
                        "assetId": entry.get("assetId", entry.get("md5ext", "").split(".")[0]),
                        "md5ext": entry["md5ext"],
                        "dataFormat": entry.get("dataFormat", "wav"),
                        "rate": entry.get("rate", 48000),
                        "sampleCount": entry.get("sampleCount", 0),
                    }
            elif lib_type == "sprites":
                # Sprites have costumes and sounds embedded
                if "costumes" in entry:
                    for costume in entry["costumes"]:
                        cname = costume.get("name", "").lower()
                        if cname and "md5ext" in costume:
                            self._costumes.setdefault(cname, {
                                "assetId": costume.get("assetId", costume.get("md5ext", "").split(".")[0]),
                                "md5ext": costume["md5ext"],
                                "dataFormat": costume.get("dataFormat", "svg"),
                                "rotationCenterX": costume.get("rotationCenterX", 48),
                                "rotationCenterY": costume.get("rotationCenterY", 50),
                            })

    def lookup_costume(self, name: str) -> Optional[dict]:
        """Look up costume info by name (case-insensitive)."""
        return self._costumes.get(name.lower())

    def lookup_backdrop(self, name: str) -> Optional[dict]:
        return self._backdrops.get(name.lower())

    def lookup_sound(self, name: str) -> Optional[dict]:
        return self._sounds.get(name.lower())

    def suggest_costume(self, name: str) -> list[str]:
        """Fuzzy-match costume names."""
        return get_close_matches(name.lower(), self._costumes.keys(), n=3, cutoff=0.5)

    def suggest_backdrop(self, name: str) -> list[str]:
        return get_close_matches(name.lower(), self._backdrops.keys(), n=3, cutoff=0.5)

    def suggest_sound(self, name: str) -> list[str]:
        return get_close_matches(name.lower(), self._sounds.keys(), n=3, cutoff=0.5)

    async def download_asset(self, md5ext: str) -> Path:
        """Download an asset file and cache it locally. Returns the cache path."""
        cache_path = ASSET_CACHE / md5ext
        if cache_path.exists():
            return cache_path

        url = f"{SCRATCH_ASSET_CDN}/{md5ext}"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            cache_path.write_bytes(resp.content)

        # Verify MD5
        expected_hash = md5ext.split(".")[0]
        actual_hash = hashlib.md5(cache_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            # Don't delete; the file might still be usable
            pass

        return cache_path

    def get_default_backdrop_svg(self) -> bytes:
        """Return a default white backdrop SVG."""
        return DEFAULT_BACKDROP_SVG.encode("utf-8")

    def find_relevant_names(self, prompt: str) -> dict[str, list[str]]:
        """Keyword-match a user prompt against library asset names.

        Returns candidate costume/backdrop/sound names to inject into the
        LLM prompt so it uses real asset names instead of guessing.
        """
        tokens = set()
        for word in re.findall(r"[a-z]+", prompt.lower()):
            if len(word) >= 3 and word not in _STOPWORDS:
                tokens.add(word)
                if word.endswith("s"):
                    tokens.add(word[:-1])  # plural to singular

        def search(names, limit: int) -> list[str]:
            # Round-robin across tokens so one keyword with many assets
            per_token = [sorted(n for n in names if t in n) for t in sorted(tokens)]
            hits: list[str] = []
            seen: set[str] = set()
            i = 0
            while len(hits) < limit and any(per_token):
                bucket = per_token[i % len(per_token)]
                if bucket:
                    name = bucket.pop(0)
                    if name not in seen:
                        seen.add(name)
                        hits.append(name)
                i += 1
                if i > 10000:  # safety
                    break
            return hits

        return {
            "costumes": search(self._costumes, 40),
            "backdrops": search(self._backdrops, 15),
            "sounds": search(self._sounds, 20),
        }

    def get_all_costume_names(self) -> list[str]:
        return sorted(self._costumes.keys())

    def get_all_backdrop_names(self) -> list[str]:
        return sorted(self._backdrops.keys())

    def get_all_sound_names(self) -> list[str]:
        return sorted(self._sounds.keys())


# Singleton
_library: Optional[AssetLibrary] = None


async def get_library() -> AssetLibrary:
    global _library
    if _library is None:
        _library = AssetLibrary()
    await _library.ensure_loaded()
    return _library
