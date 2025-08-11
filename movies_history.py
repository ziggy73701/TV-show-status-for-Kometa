import os
from datetime import datetime
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


def get_this_month_in_history(radarr_url, radarr_api_key, tmdb_api_key, country_code):
    """Return movies from Radarr released in the current month of previous years."""
    radarr_movies = get_radarr_movies(radarr_url, radarr_api_key)
    now = datetime.now()
    current_month = now.month
    movies = []
    for movie in radarr_movies:
        tmdb_id = movie.get("tmdbId")
        date_str = None
        if tmdb_id and tmdb_api_key and country_code:
            try:
                url = f"https://api.themoviedb.org/3/movie/{tmdb_id}/release_dates?api_key={tmdb_api_key}"
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    for result in data.get("results", []):
                        if result.get("iso_3166_1") == country_code:
                            rel_dates = result.get("release_dates", [])
                            if rel_dates:
                                date_str = rel_dates[0].get("release_date")
                            break
            except requests.exceptions.RequestException:
                pass
        if not date_str:
            date_str = (
                movie.get("inCinemas")
                or movie.get("physicalRelease")
                or movie.get("digitalRelease")
                or movie.get("releaseDate")
            )
        if not date_str:
            continue
        try:
            date = datetime.fromisoformat(date_str[:10])
        except ValueError:
            continue
        if date.month == current_month and date.year < now.year:
            movies.append({"title": movie.get("title"), "tmdbId": tmdb_id})
    return movies


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
        use_text = text_config.pop("use_text", "THIS MONTH")
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
    from collections import OrderedDict

    if config is None:
        config = {}
    output_dir = "/config/kometa/tssk/" if IS_DOCKER else "kometa/"
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, output_file)
    tmdb_ids = [m["tmdbId"] for m in movies if m.get("tmdbId")]
    collection_config = deepcopy(config.get("collection_this_month_in_history", {}))
    collection_name = collection_config.pop("collection_name", "This Month in History")
    month_name = datetime.now().strftime("%B")
    summary = f"Movies released in {month_name} in previous years"

    class QuotedString(str):
        pass

    def quoted_str_presenter(dumper, data):
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style='"')

    yaml.add_representer(QuotedString, quoted_str_presenter, Dumper=yaml.SafeDumper)

    if not tmdb_ids:
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("#No matching movies found")
        return

    tmdb_ids_str = ", ".join(str(i) for i in sorted(tmdb_ids))
    collection_data = {"summary": summary}
    for key, value in collection_config.items():
        if key == "sort_title":
            collection_data[key] = QuotedString(value)
        else:
            collection_data[key] = value
    collection_data["sync_mode"] = "sync"
    collection_data["tmdb_movie"] = tmdb_ids_str

    ordered = OrderedDict()
    ordered["summary"] = collection_data["summary"]
    if "sort_title" in collection_data:
        ordered["sort_title"] = collection_data["sort_title"]
    for key, value in collection_data.items():
        if key not in ["summary", "sort_title", "sync_mode", "tmdb_movie"]:
            ordered[key] = value
    ordered["sync_mode"] = collection_data["sync_mode"]
    ordered["tmdb_movie"] = collection_data["tmdb_movie"]

    data = {"collections": {collection_name: ordered}}
    with open(output_file, "w", encoding="utf-8") as f:
        yaml.dump(data, f, Dumper=yaml.SafeDumper, sort_keys=False)
