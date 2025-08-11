"""Utilities for movies that are currently playing in theaters.

Functions for historical movie queries are located in ``movies_history``.
"""

import requests
from typing import List, Dict, Optional

from movies_history import get_radarr_movies


def get_in_theaters(
    radarr_url: str,
    radarr_api_key: str,
    tmdb_api_key: str,
    country_code: Optional[str] = None,
) -> List[Dict[str, int]]:
    """Return Radarr movies that are currently playing in theaters.

    The function fetches the TMDb ``now_playing`` list for the provided
    ``country_code`` (if supplied) and filters it against the movies present in
    Radarr. Only titles already tracked by Radarr will be returned.
    """

    radarr_movies = get_radarr_movies(radarr_url, radarr_api_key)
    radarr_tmdb = {
        movie.get("tmdbId"): movie.get("title")
        for movie in radarr_movies
        if movie.get("tmdbId")
    }

    movies: List[Dict[str, int]] = []
    page = 1
    while True:
        url = (
            f"https://api.themoviedb.org/3/movie/now_playing?api_key={tmdb_api_key}&page={page}"
        )
        if country_code:
            url += f"&region={country_code}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                break
            data = response.json()
        except requests.exceptions.RequestException:
            break

        for result in data.get("results", []):
            tmdb_id = result.get("id")
            if tmdb_id in radarr_tmdb:
                movies.append({"title": radarr_tmdb[tmdb_id], "tmdbId": tmdb_id})

        if page >= data.get("total_pages", 1):
            break
        page += 1

    return movies

