import os
from copy import deepcopy
from typing import List, Dict

IS_DOCKER = os.getenv("DOCKER", "false").lower() == "true"

def create_movie_overlay_yaml(output_file: str, movies: List[Dict], config_sections: Dict[str, Dict]) -> None:
    """Create overlay YAML for movies.

    Parameters
    ----------
    output_file : str
        Name of the file to write to.
    movies : list of dict
        Each dict should at least contain a ``tmdbId`` key.
    config_sections : dict
        Configuration with ``backdrop`` and ``text`` subsections.
    """
    import yaml

    output_dir = "/config/kometa/tssk/" if IS_DOCKER else "kometa/"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, output_file)

    if not movies:
        with open(output_path, "w", encoding="utf-8") as fh:
            fh.write("#No matching movies found")
        return

    tmdb_ids = [m.get("tmdbId") for m in movies if m.get("tmdbId")]
    overlays: Dict[str, Dict] = {}

    # -- Backdrop Block --
    backdrop_cfg = deepcopy(config_sections.get("backdrop", {}))
    if backdrop_cfg.pop("enable", True) and tmdb_ids:
        backdrop_cfg["name"] = "backdrop"
        overlays["backdrop"] = {
            "overlay": backdrop_cfg,
            "tmdb_movie": ", ".join(str(i) for i in sorted(tmdb_ids)),
        }

    # -- Text Block --
    text_cfg = deepcopy(config_sections.get("text", {}))
    if text_cfg.pop("enable", True) and tmdb_ids:
        use_text = text_cfg.pop("use_text", "WATCHED")
        text_cfg.setdefault("font_size", 65)
        text_cfg.setdefault("font_color", "#FFFFFF")
        text_cfg.setdefault("horizontal_align", "center")
        text_cfg.setdefault("horizontal_offset", 0)
        text_cfg.setdefault("vertical_align", "bottom")
        text_cfg.setdefault("vertical_offset", 0)
        text_cfg["name"] = f"text({use_text})"
        overlays["text"] = {
            "overlay": text_cfg,
            "tmdb_movie": ", ".join(str(i) for i in sorted(tmdb_ids)),
        }

    with open(output_path, "w", encoding="utf-8") as fh:
        yaml.dump({"overlays": overlays}, fh, sort_keys=False)
