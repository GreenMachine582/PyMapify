
import argparse
import logging
import sys
import time
import traceback
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
    args = parser.parse_args()
    instance: str = args.instance
    config_path: str = args.config_path
    logs_dir: str = args.logs_dir

    project_name = pymapify.version.PROJECT_NAME

    if not config_path:
        config_filename = f"{project_name}{'' if not instance else '_' + instance}.conf"
        config_path = f"configs/{config_filename}"
    if not logs_dir:
        logs_instance_folder = f"{project_name}{'' if not instance else '_' + instance}"
        logs_dir = f"logs/{logs_instance_folder}"

    env = pymapify.loadEnv(config_path, project_dir=MODULE_DIR, instance=instance, logs_dir=logs_dir)
    _logger.info(f"Starting {pymapify.version.PROJECT_NAME_TEXT}.")

    try:
        mapify = pymapify.Map(env)
        mapify.loadMapData(MODULE_DIR + "/destinations.csv")
        mapify.plotMap()
        mapify.saveMap(MODULE_DIR + "/map.html")
    except Exception as e:
        _logger.exception(e)
        sys_trace = sys.exc_info()
        error_track = traceback.TracebackException(
            sys_trace[0], sys_trace[1], sys_trace[2], limit=None).stack[0].line
        _logger.error(error_track)
        return Exception(e)
    finally:
        close()


if __name__ == "__main__":
    main()
