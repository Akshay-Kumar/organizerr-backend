# app/utils/tmdb_utils.py
import os
import requests
from typing import Literal, List, Dict, Optional

TMDB_API_KEY = os.getenv("TMDB_API_KEY")  # set in .env
TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p/w200"


def search_tmdb(query: str, media_type: Literal["movie", "tv"], year: int | None = None) -> List[Dict]:
    """
    Search TMDb for movies or TV shows.
    """
    if not TMDB_API_KEY:
        raise RuntimeError("TMDB_API_KEY not set in environment")

    params = {
        "api_key": TMDB_API_KEY,
        "query": query,
        "include_adult": False,
        "language": "en-US",
    }
    if year:
        if media_type == "movie":
            params["year"] = year
        else:
            params["first_air_date_year"] = year

    url = f"{TMDB_BASE_URL}/search/{media_type}"
    r = requests.get(url, params=params)
    r.raise_for_status()
    data = r.json()

    results = []
    for item in data.get("results", []):
        title = item.get("title") or item.get("name")
        release_date = item.get("release_date") or item.get("first_air_date") or ""
        year_str = release_date.split("-")[0] if release_date else None

        results.append({
            "id": item.get("id"),
            "title": title,
            "year": int(year_str) if year_str and year_str.isdigit() else None,
            "overview": item.get("overview", ""),
            "poster": f"{TMDB_IMAGE_BASE}{item['poster_path']}" if item.get("poster_path") else None,
            "media_type": media_type,
        })

    return results


def search_tmdb_episode(show_name: str, season: Optional[int] = None, episode: Optional[int] = None) -> List[Dict]:
    """
    Search TMDb for a TV show's episode(s) based on show name, season, and episode.
    """
    shows = search_tmdb(show_name, "tv")
    if not shows:
        return []

    show_id = shows[0]["id"]
    show_title = shows[0]["title"]
    results = []

    if season is None:
        # Return just show info if no season provided
        return [{
            "id": show_id,
            "title": show_title,
            "poster": shows[0]["poster"],
            "year": shows[0]["year"],
            "media_type": "tv"
        }]

    # Fetch episodes for that season
    url = f"{TMDB_BASE_URL}/tv/{show_id}/season/{season}"
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    r = requests.get(url, params=params)
    if r.status_code != 200:
        return []

    data = r.json()
    for ep in data.get("episodes", []):
        if episode and ep.get("episode_number") != episode:
            continue

        results.append({
            "id": show_id,
            "title": show_title,
            "season": season,
            "episode": ep.get("episode_number"),
            "episode_title": ep.get("name"),
            "overview": ep.get("overview", ""),
            "air_date": ep.get("air_date"),
            "poster": f"{TMDB_IMAGE_BASE}{ep['still_path']}" if ep.get("still_path") else shows[0].get("poster"),
            "tmdb_id": ep.get("id"),
            "media_type": "episode",
        })

    return results
