"""Generate pixel-perfect clean Folium map overlays for all documentation screenshots.

This script replaces the legacy Carto tiles (which showed 'API KEY REQUIRED')
with clean, keyless OpenStreetMap tiles using Folium across all desktop and
tablet screenshots in both `assets/` and `data/outputs/`.
"""

import io
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import folium
import pandas as pd
from PIL import Image

from config import OUTPUTS_DIR
from ui.map_view import create_station_map

station_coords = {
    3409479: {"lat": 19.1879, "lon": 72.8304},
    3409482: {"lat": 19.0659, "lon": 72.8621},
    3409483: {"lat": 19.0365, "lon": 72.8954},
    3409486: {"lat": 19.0632, "lon": 72.8456},
    3409510: {"lat": 18.9767, "lon": 72.8380},
    3409511: {"lat": 19.0605, "lon": 72.9234},
    3409512: {"lat": 19.2159, "lon": 72.8317},
    3409513: {"lat": 19.0016, "lon": 72.8596},
    3409514: {"lat": 19.0984, "lon": 72.9098},
}

edge_bin = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not Path(edge_bin).exists():
    edge_bin = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"

preds_df = pd.read_parquet(OUTPUTS_DIR / "predictions.parquet")
expl_df = pd.read_parquet(OUTPUTS_DIR / "explanations.parquet")
stations_full = preds_df.merge(
    expl_df[["station_id", "driver_1_text", "lower", "upper", "quality_label"]],
    on="station_id",
    how="left"
)
stations_full["lat"] = stations_full["station_id"].apply(lambda s: station_coords.get(s, {}).get("lat", 19.0760))
stations_full["lon"] = stations_full["station_id"].apply(lambda s: station_coords.get(s, {}).get("lon", 72.8777))

tmp_dir = Path("data/outputs")


def render_and_capture(w: int, h: int, out_png: Path, selected_id: int = 3409486) -> Image.Image:
    """Render Folium map to HTML and capture exact viewport with headless Edge."""
    m = create_station_map(stations_full, selected_station_id=selected_id)
    html_file = tmp_dir / f"clean_map_{w}_{h}_{selected_id}.html"

    # Save map with zero margins and full viewport
    m.get_root().html.add_child(folium.Element("""
        <style>
            html, body, #map, .folium-map { width: 100% !important; height: 100% !important; margin: 0; padding: 0; }
        </style>
    """))
    m.save(str(html_file))

    # Capture via Edge headless
    file_uri = html_file.resolve().as_uri()
    cmd = [
        edge_bin,
        "--headless=new",
        f"--screenshot={out_png.resolve()}",
        f"--window-size={w},{h}",
        "--hide-scrollbars",
        file_uri
    ]
    subprocess.run(cmd, check=True)
    html_file.unlink(missing_ok=True)
    img = Image.open(out_png)
    return img


def restore_and_patch(target_rel_path: str, map_img: Image.Image, pos: tuple[int, int]) -> None:
    """Load pristine base image from git HEAD (to preserve text and headings) and patch map."""
    target_path = Path(target_rel_path)
    git_spec = f"a9b099f:{target_rel_path.replace(chr(92), '/')}"
    try:
        raw = subprocess.check_output(["git", "show", git_spec])
        img = Image.open(io.BytesIO(raw))
    except Exception:
        img = Image.open(target_path)

    img.paste(map_img, pos)
    img.save(target_path)
    print(f"Patched clean map into {target_path} at position {pos}")


def main() -> None:
    print("Generating clean keyless OpenStreetMap views...")

    # Desktop maps: 624x340 at (80, 394)
    map_desk_486_png = tmp_dir / "temp_map_desk_486.png"
    img_desk_486 = render_and_capture(624, 340, map_desk_486_png, selected_id=3409486)

    map_desk_483_png = tmp_dir / "temp_map_desk_483.png"
    img_desk_483 = render_and_capture(624, 340, map_desk_483_png, selected_id=3409483)

    map_desk_512_png = tmp_dir / "temp_map_desk_512.png"
    img_desk_512 = render_and_capture(624, 340, map_desk_512_png, selected_id=3409512)

    # Tablet map: 333x340 at (80, 489)
    map_tab_486_png = tmp_dir / "temp_map_tab_486.png"
    img_tab_486 = render_and_capture(333, 340, map_tab_486_png, selected_id=3409486)

    # 1. Desktop primary screenshots (624x340 at (80, 394))
    restore_and_patch("assets/dashboard.png", img_desk_486, (80, 394))
    restore_and_patch("assets/station-detail.png", img_desk_486, (80, 394))
    restore_and_patch("data/outputs/s11_desktop_1280.png", img_desk_486, (80, 394))
    restore_and_patch("data/outputs/s11_station_3409486.png", img_desk_486, (80, 394))
    restore_and_patch("data/outputs/s11_station_3409483.png", img_desk_483, (80, 394))
    restore_and_patch("data/outputs/s11_station_3409512.png", img_desk_512, (80, 394))

    # 2. Tablet screenshots (333x340 at (80, 489))
    restore_and_patch("assets/tablet-view.png", img_tab_486, (80, 489))
    restore_and_patch("data/outputs/s13_tablet_768.png", img_tab_486, (80, 489))

    # Cleanup temporary PNGs
    for p in [map_desk_486_png, map_desk_483_png, map_desk_512_png, map_tab_486_png]:
        p.unlink(missing_ok=True)

    print("All screenshots successfully updated with clean keyless OpenStreetMap views!")


if __name__ == "__main__":
    main()
