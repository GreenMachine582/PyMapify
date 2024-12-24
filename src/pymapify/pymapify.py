from __future__ import annotations

import logging
from collections.abc import Hashable
from concurrent.futures import ThreadPoolExecutor
from os import path as os_path

import folium
import pandas as pd
from geopy.distance import geodesic

from . import google_maps
from .version import PROJECT_NAME
from .utils import Env, file


_logger = logging.getLogger(__name__)


PD_SCHEMA = {
    "required": {
        "open_time": "string",
        "close_time": "string",
        "link": "string"
    },
    "optional": {
        "marker_colour": "string",
        "latitude": "float64",
        "longitude": "float64",
        "place_name": "string",
    }
}


class Map:

    PD_SCHEMA = PD_SCHEMA

    def __init__(self, env: Env):
        self.env: Env = env
        self.env.mapify = self

        self.data: pd.DataFrame | None = None
        self.map: folium.Map | None = None

    @property
    def config(self) -> dict:
        return self.env.config[PROJECT_NAME]

    def _processRow(self, index: Hashable, row: pd.Series):
        # resolved_url = google_maps.resolveShortenedURL(row['link']) or row['link']
        resolved_url = row["link"]
        lat, lon = google_maps.extractCoordinates(resolved_url)

        # Update the DataFrame (requires thread-safe method)
        if lat is not None and lon is not None:
            self.data.at[index, 'latitude'] = lat
            self.data.at[index, 'longitude'] = lon
        if not isinstance(row['place_name'], str) or not row['place_name'].strip():
            self.data.at[index, 'place_name'] = google_maps.extractPlaceName(resolved_url) or "Unknown"
        if not pd.notna(row["marker_colour"]):
            self.data.at[index, 'marker_colour'] = self.config["marker_colour"]

    def _processData(self):
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(self._processRow, index, row)
                for index, row in self.data.iterrows()
            ]

        # Ensure all threads complete
        for future in futures:
            future.result()

        # Filter rows with valid coordinates
        self.data = self.data.dropna(subset=['latitude', 'longitude'])

    def loadMapData(self, file_path: str):
        """Load marker data from CSV file."""
        data = pd.read_csv(os_path.abspath(file_path), engine='python', sep=";;", dtype=PD_SCHEMA["required"])
        for column_name, column_type in self.PD_SCHEMA["optional"].items():
            if column_name not in data.columns:
                data[column_name] = pd.Series([], dtype=column_type)
        self.data = data

        # Filter rows with valid links
        self.data = self.data.dropna(subset=['link'])
        if self.data.empty:
            _logger.warning("No valid destinations to map.")

        self._processData()
        if self.data.empty:
            raise Exception("No valid destinations to map.")

    def _groupLocations(self, threshold=0.01):
        """Group locations by proximity."""
        visited = set()
        group_id = 0

        self.data['group_id'] = pd.Series(dtype='int')

        for index, row in self.data.iterrows():
            if index in visited:
                continue

            # Start a new group with the current location
            self.data.at[index, 'group_id'] = group_id
            visited.add(index)

            # Find nearby locations to merge
            for i, other_row in self.data.iterrows():
                if i in visited:
                    continue
                distance = geodesic(
                    (row['latitude'], row['longitude']),
                    (other_row['latitude'], other_row['longitude'])
                ).km
                if distance < threshold:
                    self.data.at[i, 'group_id'] = group_id
                    visited.add(i)

            group_id += 1

    @staticmethod
    def _calculateMeanLocation(data: pd.DataFrame):
        """Calculate the mean latitude and longitude across all markers."""
        return [sum(data["latitude"]) / len(data["latitude"]), sum(data["longitude"]) / len(data["longitude"])]

    @staticmethod
    def _getFocusLocation(data: pd.DataFrame, focus_type: str = "centre") -> list[float, float] | None:
        assert focus_type in ["first", "last", "centre"], f"Invalid value for map_focus: {focus_type}"

        location = None
        match focus_type:
            case "first":
                location = [data.at[0, "latitude"], data.at[0, "longitude"]]
            case "last":
                location = [data.iloc[-1]["latitude"], data.iloc[-1]["longitude"]]
            case "centre":
                location = Map._calculateMeanLocation(data)
        return location

    @staticmethod
    def _getFocusSize(focus_size: int | str = 50) -> int:
        if focus_size == "fit":
            focus_size = 10  # Map will be fitted to bounds after creation
        assert isinstance(focus_size, int) and focus_size > 1, f"Invalid value for map_size: {focus_size}"
        return focus_size

    @staticmethod
    def _calculateBounds(data):
        """Calculate the bounds to fit all marker locations."""
        return [
            [min(data["latitude"]), min(data["longitude"])],  # Southwest corner
            [max(data["latitude"]), max(data["longitude"])]   # Northeast corner
        ]

    def _createIcon(self, colour: str = "", icon: str = "", prefix: str = "") -> folium.Icon:
        colour = colour or self.config["marker_colour"] or "blue"
        icon = icon or self.config["marker_icon"] or "circle"
        prefix = prefix or self.config["marker_prefix"] or "fa"
        return folium.Icon(color=colour, icon=icon, prefix=prefix)

    def plotMap(self, map_focus: str = None, map_size: int | str = None):
        self._groupLocations(threshold=self.config["group_threshold"])

        # Create a map around desired location and focus size
        location = self._getFocusLocation(self.data, map_focus or self.config["focus_type"])
        zoom_start = self._getFocusSize(map_size or self.config["focus_size"])
        self.map = folium.Map(location=location, zoom_start=zoom_start)

        # Set fit bounds to include all markers
        if (map_size or self.config["focus_size"]) == "fit":
            bounds = self._calculateBounds(self.data)
            self.map.fit_bounds(bounds)

        # Add grouped markers
        grouped_data = self.data.groupby('group_id')
        for group_id, group in grouped_data:
            # Use the first location in the group as the marker location
            first_row = group.iloc[0]
            lat, lon = first_row["latitude"], first_row["longitude"]

            # Merge popup text
            popup_htmls = []
            for _, row in group.iterrows():
                popup_html = f"<span><b>{row['place_name']}</b></span>"
                if pd.notna(row['open_time']) and pd.notna(row['close_time']):
                    popup_html = f"<span><b>{row['place_name']}</b> {row['open_time']}–{row['close_time']}</span>"
                popup_htmls.append(popup_html)
            merged_popup_html = "<br><br>".join(popup_htmls)

            # Add marker
            marker_colour = first_row['marker_colour']
            folium.Marker(
                location=[lat, lon],
                icon=self._createIcon(colour=marker_colour),
                popup=merged_popup_html
            ).add_to(self.map)
        _logger.info(f"Map created with '{len(grouped_data)}' marker{'s' if len(grouped_data) > 1 else ''}.")

    def _renderMap(self, title: str = "") -> str:
        """Render the map into HTML."""
        map_html = str(self.map.get_root().render())
        _logger.debug("Map has been rendered to HTML.")
        modified_html = map_html
        if title:
            modified_html = modified_html.replace("""<head>\n    \n    <meta""",
                                                  f"""<head>\n    \n    <title>{title}</title>\n<meta""")
        # TODO: set favicon

        modified_html = modified_html.replace("""L.popup({\n  "maxWidth": "100%",\n});""",
                                              """L.popup({\n  "width": "100px",\n});""")
        modified_html = modified_html.replace("""</html>""",
                                              """<script>
        document.addEventListener("DOMContentLoaded", function () {
            // Find the element by Class Names and remove it
            const elementToRemove = document.getElementsByClassName('leaflet-control-attribution leaflet-control');
            if (elementToRemove) {
                $('.leaflet-control-attribution').remove();
            }
        });
    </script>\n</html>""")
        _logger.debug("HTML map has been modified.")
        return modified_html

    def saveMap(self, file_path: str):
        html_map = self._renderMap(self.config["title"])

        directory, filename = os_path.split(file_path)
        # Ensure filename include extension
        filename = filename if filename.endswith(".html") else filename + ".html"
        file.save(directory, filename, html_map)
        _logger.info(f"Map saved as '{filename}'")
