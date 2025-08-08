import os
import requests
from copy import deepcopy
import yaml

IS_DOCKER = os.getenv("DOCKER", "false").lower() == "true"


def process_radarr_url(base_url, api_key):
    """Validate and normalize the Radarr URL by testing common API paths."""
    base_url = base_url.rstrip("/")
    if base_url.startswith("http"):
        protocol_end = base_url.find("://") + 3
        next_slash = base_url.find("/", protocol_end)
        if next_slash != -1:
            base_url = base_url[:next_slash]
    api_paths = ["/api/v3", "/radarr/api/v3"]
    for path in api_paths:
        test_url = f"{base_url}{path}"
        try:
            headers = {"X-Api-Key": api_key}
            response = requests.get(
                f"{test_url}/system/status", headers=headers, timeout=10
            )
            if response.status_code == 200:
                print(f"Successfully connected to Radarr at: {test_url}")
                return test_url
        except requests.exceptions.RequestException:
            continue
    raise ConnectionError("Unable to establish connection to Radarr.")


def get_radarr_movies(radarr_url, api_key):
    """Return all movies from Radarr."""
    url = f"{radarr_url}/movie"
    headers = {"X-Api-Key": api_key}
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    return response.json()


def _filter_tmdb_movies(tmdb_movies, radarr_movies):
    radarr_tmdb_ids = {m.get("tmdbId") for m in radarr_movies if m.get("tmdbId")}
    radarr_imdb_ids = {m.get("imdbId") for m in radarr_movies if m.get("imdbId")}
    filtered = []
    for movie in tmdb_movies:
        tmdb_id = movie.get("id") or movie.get("tmdbId")
        imdb_id = movie.get("imdb_id") or movie.get("imdbId")
        if tmdb_id in radarr_tmdb_ids or (imdb_id and imdb_id in radarr_imdb_ids):
            filtered.append(movie)
    return filtered


def get_movie_history(tmdb_api_key, radarr_url=None, radarr_api_key=None):
    """Fetch trending movies from TMDb and filter against Radarr library."""
    url = f"https://api.themoviedb.org/3/trending/movie/week?api_key={tmdb_api_key}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    movies = response.json().get("results", [])
    if radarr_url and radarr_api_key:
        radarr_movies = get_radarr_movies(radarr_url, radarr_api_key)
        movies = _filter_tmdb_movies(movies, radarr_movies)
    return [{"title": m.get("title"), "tmdbId": m.get("id")} for m in movies]


def create_movie_overlay_yaml(output_file, movies, config_sections=None):
    """Create overlay YAML for movies using tmdbId identifiers."""
    if config_sections is None:
        config_sections = {}
    output_dir = "/config/kometa/tssk/" if IS_DOCKER else "kometa/"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, output_file)
    if not movies:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("#No matching movies found")
        return
    tmdb_ids = ", ".join(str(m["tmdbId"]) for m in movies if m.get("tmdbId"))
    overlays = {}

    # Backdrop block
    backdrop_config = deepcopy(config_sections.get("backdrop", {}))
    enable_backdrop = backdrop_config.pop("enable", True)
    if enable_backdrop:
        backdrop_config.setdefault("name", "backdrop")
        overlays["backdrop"] = {
            "overlay": backdrop_config,
            "tmdb_movie": tmdb_ids,
        }

    # Text block
    text_config = deepcopy(config_sections.get("text", {}))
    enable_text = text_config.pop("enable", True)
    if enable_text:
        use_text = text_config.pop("use_text", "TRENDING")
        text_config.setdefault("horizontal_align", "center")
        text_config.setdefault("horizontal_offset", 0)
        text_config.setdefault("vertical_align", "bottom")
        text_config.setdefault("vertical_offset", 35)
        text_config.setdefault("font_size", 70)
        text_config.setdefault("font_color", "#FFFFFF")
        text_config["name"] = f"text({use_text})"
        overlays["text"] = {
            "overlay": text_config,
            "tmdb_movie": tmdb_ids,
        }

    data = {"overlays": overlays}
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False)


def create_movie_collection_yaml(output_file, movies, config=None):
    """Create collection YAML for movies using tmdbId identifiers."""
    if config is None:
        config = {}
    output_dir = "/config/kometa/tssk/" if IS_DOCKER else "kometa/"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, output_file)
    tmdb_ids = [m["tmdbId"] for m in movies if m.get("tmdbId")]
    if not tmdb_ids:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("#No matching movies found")
        return
    collection_name = config.get("collection_movie_history", {}).get(
        "collection_name", "Movie History"
    )
    data = {
        "collections": {
            collection_name: {
                "tmdb_movie": tmdb_ids,
                "summary": "Movies from TMDb filtered by Radarr library",
            }
        }
    }
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, sort_keys=False)
