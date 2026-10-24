"""Spotify OAuth setup.

Uses spotipy's Authorization Code flow. Credentials come from the environment
(``SPOTIPY_CLIENT_ID`` / ``SPOTIPY_CLIENT_SECRET`` / ``SPOTIPY_REDIRECT_URI``),
which spotipy reads automatically. The refresh token is cached to
``~/.spotify-mcp/token.json`` so the browser auth only happens once.

Scopes are deliberately minimal: playlist read + modify, plus read-only access
to the Liked Songs library (local patch, 2026-10-24, for export_liked_tracks).
No playback, no library writes, no profile data.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

import spotipy
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth

SCOPES = "playlist-read-private playlist-modify-private playlist-modify-public user-library-read"

_CACHE_DIR = Path.home() / ".spotify-mcp"
_DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"

_client: spotipy.Spotify | None = None
_client_lock = threading.Lock()


class _SerializedOAuth(SpotifyOAuth):
    """SpotifyOAuth that fetches tokens one caller at a time.

    The MCP SDK runs sync tools on worker threads, so tool calls can overlap.
    Unserialized, concurrent first calls would each start the browser flow and
    concurrent refreshes would race on the token cache file.
    """

    _token_lock = threading.Lock()

    def get_access_token(self, *args, **kwargs):
        with self._token_lock:
            return super().get_access_token(*args, **kwargs)


def get_client() -> spotipy.Spotify:
    """Return a cached, authenticated Spotify client (creates it on first call)."""
    global _client
    with _client_lock:
        if _client is not None:
            return _client
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        auth = _SerializedOAuth(
            scope=SCOPES,
            redirect_uri=os.environ.get("SPOTIPY_REDIRECT_URI", _DEFAULT_REDIRECT_URI),
            cache_handler=CacheFileHandler(cache_path=str(_CACHE_DIR / "token.json")),
            open_browser=True,
        )
        _client = spotipy.Spotify(auth_manager=auth)
        return _client


def current_user_id() -> str:
    """Return the authenticated user's Spotify ID."""
    return get_client().current_user()["id"]
