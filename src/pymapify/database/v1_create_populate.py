import logging

_logger = logging.getLogger(__name__)


def populateLookupTables(env):
    """ Populate lookup tables with initial data. """
    icons = [
        ("blue", "circle", "fa"),
        ("blue", "location-dot", "fa"),
        ("green", "location-dot", "fa"),
    ]
    for icon in icons:
        env.cur.execute(
            "INSERT INTO marker_icon (colour, icon, prefix) VALUES (%s, %s, %s);",
            icon
        )


def populate(env):
    """ Populate the database with initial data. """
    _logger.info("Populating the database lookup tables with initial data...")
    populateLookupTables(env)

    _logger.info("Initial data population completed.")