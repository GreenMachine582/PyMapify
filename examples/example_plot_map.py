from __future__ import annotations

import argparse
import logging
import sys
import time
from os import path as os_path

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
        # Plot markers to a map from the database
        mapify = pymapify.Map(env)
        mapify.plotMap()
        mapify.saveMap(MODULE_DIR + "/map.html")
    except Exception as e:
        _logger.error(f"An error occurred while loading data from CSV: {e}")
        raise
    finally:
        close()


if __name__ == "__main__":
    main()
