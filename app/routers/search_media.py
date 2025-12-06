# app/routers/search_media.py
from fastapi import APIRouter, Query
from typing import Optional
from app.utils.tmdb_utils import search_tmdb, search_tmdb_episode

router = APIRouter()


@router.get("/search_media")
async def search_media(
        query: str = Query(..., min_length=2, description="Search query text"),
        media_type: str = Query(..., regex="^(movie|tv|episode|music|unsorted)$", description="Either 'movie', 'tv', 'episode', 'music' or 'unsorted'"),
        year: Optional[int] = Query(None, ge=1900, le=2100),
        season: Optional[int] = Query(None, ge=1),
        episode: Optional[int] = Query(None, ge=1)
):
    """
    Search TMDb for movie, TV show, or specific episode.
    """
    try:
        if media_type == "movie":
            results = search_tmdb(query=query, media_type="movie", year=year)
        elif media_type == "tv":
            results = search_tmdb(query=query, media_type="tv", year=year)
        elif media_type == "episode":
            results = search_tmdb_episode(show_name=query, season=season, episode=episode)
        else:
            results = []
        return {"results": results}
    except Exception as e:
        return {"results": [], "error": str(e)}
