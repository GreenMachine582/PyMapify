from __future__ import annotations

import argparse
import logging
import sys
import time
from os import path as os_path

import pandas as pd
from geopy.distance import geodesic

from src import pymapify

_logger = logging.getLogger(__name__)

MODULE_DIR = os_path.dirname(os_path.abspath(__file__))

parser = argparse.ArgumentParser()
parser.add_argument("--instance", default="", help="instance name will be used to locate config (default: '')")
parser.add_argument("--config_path", default="", help="path to desired config (default: '')")
parser.add_argument("--logs_dir", default="", help="directory to desired logs (default: '')")


def close():
    _logger.info("Closing")
    time.sleep(2)
    sys.exit(f"Thanks for using {pymapify.version.PROJECT_NAME_TEXT}")


def _getPlaceHTMLName(name: str, open_time, close_time) -> str:
    html = f"<span><b>{name}</b></span>"
    if open_time and close_time:
        html = f"<span><b>{name}</b> {open_time}–{close_time}</span>"
    return html


def getMarker(env, row: pd.Series, threshold: float = 0.005) -> int | None:
    """ Find suitable marker group and update it or create a new one. """
    marker_id = None
    name = _getPlaceHTMLName(row['place_name'], row['open_time'], row['close_time'])
    env.cur.execute(
        "SELECT id, name, latitude, longitude FROM marker;"
    )
    marker_results = env.cur.fetchall()
    for marker in marker_results:
        distance = geodesic(
            (row['latitude'], row['longitude']),
            (marker[2], marker[3])
        ).km
        if distance > threshold:
            continue  # Place too far from group marker
        marker_id = marker[0]
        env.cur.execute(
            "SELECT latitude, longitude FROM place WHERE marker_id = %s;"
        , (marker_id,))
        place_results = env.cur.fetchall()
        latitudes, longitudes = zip(*place_results, (marker[2], marker[3]))
        mean_latitude = sum(latitudes) / len(latitudes)
        mean_longitude = sum(longitudes) / len(longitudes)
        merged_name = marker[1] + "<br><br>" + name
        env.cur.execute(
            "UPDATE marker SET name = %s, latitude = %s, longitude = %s WHERE id = %s;",
            (merged_name, mean_latitude, mean_longitude, marker_id)
        )
        break  # Place can only be related to one marker group

    # Create new marker for place
    if marker_id is None:
        icon_id = 2 if row['marker_colour'] != 'green' else 3
        env.cur.execute(
            "INSERT INTO marker (name, latitude, longitude, icon_id) VALUES (%s, %s, %s, %s) "
            "RETURNING id;",
            (name, row['latitude'], row['longitude'], icon_id)
        )
        marker_id = env.cur.fetchone()[0]
    return marker_id

def loadDataFromCSV(env, csv_file_path: str, target_version: int):
    """Load data from an CSV file and insert it into the database with transaction rollback on error."""
    conn, cur = None, None
    csv_file_path = os_path.abspath(csv_file_path)
    try:
        # Ensure the database connection is available
        try:
            conn, cur = pymapify.database.connect(env, enforce_version=target_version, autocommit=False)
        except pymapify.DatabaseNotFoundError:
            pymapify.database.createDatabase(env, target_version)
            conn, cur = pymapify.database.connect(env, autocommit=False)

        # Load the CSV file, ensuring all data is read as strings
        df = pd.read_csv(csv_file_path, dtype=str, engine='python', sep=";;")
        df = df.dropna(subset=['link'])  # Filter rows with valid links
        df = df.fillna('')  # Replace NaN values with empty strings

        _logger.info("CSV file loaded successfully.")

        # Loop through each row in the DataFrame and insert the data into the database
        for index, row in df.iterrows():
            row['latitude'], row['longitude'] = pymapify.google_maps.extractCoordinates(row['link'])
            row['place_name'] = row['place_name'] or pymapify.google_maps.extractPlaceName(row['link'])
            # SQL Time type can't be an empty str
            if not row['open_time']:
                row['open_time'] = None
            if not row['close_time']:
                row['close_time'] = None

            # Relate to existing marker group or create one
            marker_id = getMarker(env, row, env.config['pymapify']['group_threshold'])

            # Insert the row into the place table
            cur.execute(
                "INSERT INTO place (link, latitude, longitude, name, open_time, close_time, marker_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (link) DO NOTHING;"
            , (row['link'], row['latitude'], row['longitude'], row['place_name'], row['open_time'], row['close_time'],
               marker_id))

        # Commit the transaction after all rows are inserted
        conn.commit()
        _logger.info(f"Data from CSV has been successfully loaded into the database v{target_version}.")

    except Exception as e:
        _logger.error(f"An error occurred while loading data from CSV: {e}")
        if conn:
            _logger.debug("Rolling back the transaction due to error.")
            conn.rollback()  # Rollback the transaction if any error occurs
        raise
    finally:
        if conn:
            conn.close()  # Ensure the connection is closed
            _logger.debug("Database connection closed.")



def main():
    """
    Main function to load the environment, parse command-line arguments, and execute the data loading process.
    """
    args = parser.parse_args()
    instance: str = args.instance
    config_path: str = args.config_path
    logs_dir: str = args.logs_dir

    project_name = pymapify.version.PROJECT_NAME

    # Determine default config and logs paths if not provided
    if not config_path:
        config_filename = f"{project_name}{'' if not instance else '_' + instance}.conf"
        config_path = f"configs/{config_filename}"
    if not logs_dir:
        logs_instance_folder = f"{project_name}{'' if not instance else '_' + instance}"
        logs_dir = f"logs/{logs_instance_folder}"

    config_path = os_path.abspath(config_path)
    logs_dir = os_path.abspath(logs_dir)

    # Load environment and configurations
    env = pymapify.loadEnv(config_path, project_dir=MODULE_DIR, instance=instance, logs_dir=logs_dir)
    _logger.info(f"Starting {env.project_name_text}.")


    try:
        # Load data from CSV into the version 1 database
        loadDataFromCSV(env, MODULE_DIR + "/destinations.csv", 1)
    except Exception as e:
        raise
    finally:
        close()


if __name__ == "__main__":
    main()
