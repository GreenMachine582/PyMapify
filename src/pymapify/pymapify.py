from __future__ import annotations

import logging
from os import path as os_path

import folium

from .version import PROJECT_NAME
from .tools import database
from .utils import Env, file


_logger = logging.getLogger(__name__)


class Map:

    def __init__(self, env: Env):
        self.env: Env = env
        self.env.mapify = self
        self.map: folium.Map | None = None

        # Ensure the database connection is available
        database.connect(env, enforce_version=-1, autocommit=False)

    @property
    def config(self) -> dict:
        return self.env.config[PROJECT_NAME]

    @staticmethod
    def _calculateMeanLocation(latitudes: tuple, longitudes: tuple):
        """Calculate the mean latitude and longitude across all markers."""
        return [sum(latitudes) / len(latitudes), sum(longitudes) / len(longitudes)]

    @staticmethod
    def _getFocusLocation(latitudes: tuple, longitudes: tuple, focus_type: str = "centre") -> list[float, float] | None:
        assert focus_type in ["first", "last", "centre"], f"Invalid value for map_focus: {focus_type}"

        location = None
        match focus_type:
            case "first":
                location = [latitudes[0], longitudes[0]]
            case "last":
                location = [latitudes[-1], longitudes[-1]]
            case "centre":
                location = Map._calculateMeanLocation(latitudes, longitudes)
        return location

    @staticmethod
    def _getFocusSize(focus_size: int | str = 50) -> int:
        if focus_size == "fit":
            focus_size = 10  # Map will be fitted to bounds after creation
        assert isinstance(focus_size, int) and focus_size > 1, f"Invalid value for map_size: {focus_size}"
        return focus_size

    @staticmethod
    def _calculateBounds(latitudes, longitudes):
        """Calculate the bounds to fit all marker locations."""
        return [
            [min(latitudes), min(longitudes)],  # Southwest corner
            [max(latitudes), max(longitudes)]   # Northeast corner
        ]

    def _createIcon(self, marker_icon_id: int) -> folium.Icon:
        """Create icon for marker based on record config."""
        self.env.cur.execute(
            "SELECT colour, icon, prefix FROM marker_icon WHERE id=%s "
            "LIMIT 1;",
            (marker_icon_id,),
        )
        marker_icon = self.env.cur.fetchone()
        return folium.Icon(color=marker_icon[0], icon=marker_icon[1], prefix=marker_icon[2])

    def plotMap(self, map_focus: str = None, map_size: int | str = None):
        # Retrieve markers from the db
        self.env.cur.execute(
            "SELECT * FROM marker;"
        )
        marker_results = self.env.cur.fetchall()
        assert len(marker_results) >= 1, f"Expected 1 or more markers, but got: {len(marker_results)}"

        # Create a map around desired location and focus size
        latitudes, longitudes = list(zip(*marker_results))[2:4]
        location = self._getFocusLocation(latitudes, longitudes, map_focus or self.config["focus_type"])
        zoom_start = self._getFocusSize(map_size or self.config["focus_size"])
        self.map = folium.Map(location=location, zoom_start=zoom_start)

        # Set fit bounds to include all markers
        if (map_size or self.config["focus_size"]) == "fit":
            bounds = self._calculateBounds(latitudes, longitudes)
            self.map.fit_bounds(bounds)

        # Add markers to map
        for marker in marker_results:
            marker_icon = None
            if marker[4]:  # Create icon for marker
                self._createIcon(marker[4])
            folium.Marker(location=marker[2:4], icon=marker_icon, popup=marker[1]).add_to(self.map)
        _logger.info(f"Map created with '{len(marker_results)}' marker{'s' if len(marker_results) > 1 else ''}.")

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

        directory, filename = os_path.split(os_path.abspath(file_path))
        # Ensure filename include extension
        filename = filename if filename.endswith(".html") else filename + ".html"
        file.save(directory, filename, html_map)
        _logger.info(f"Map saved as '{filename}'")
