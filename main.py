import config.env  # noqa: F401  # load_dotenv side effect
from time import sleep
import logging.handlers
import requests
import os
import sys
import atexit
import random

from devices.device import create_device, devices
from services.mqtt import init_mqtt, get_mqtt, mqtt_connected
from validation.validators import validate_device_data

logging.basicConfig(
    format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
    handlers=[
        # Prints to sys.stderr
        logging.StreamHandler(),
        # Writes to a log file which rotates every 1mb, or gets overwritten when the app is restarted
        logging.handlers.RotatingFileHandler(
            filename="simulator.log",
            mode='w',
            maxBytes=1024 * 1024,
            backupCount=3
        )
    ],
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BROKER_HOST = os.getenv("BROKER_HOST", "test.mosquitto.org")
BROKER_PORT = int(os.getenv("BROKER_PORT", 1883))

# How many times to attempt a connection request
RETRIES = 5

API_URL = os.getenv("API_URL", default='http://localhost:5200')


@atexit.register
def shutdown() -> None:
    get_mqtt().loop_stop()
    get_mqtt().disconnect()
    if os.path.exists("./status"):
        os.remove("./status")
    logger.info("Shutting down")


def main() -> None:
    with open("./status", "w") as file:
        file.write("healthy\n")

    logger.info("Starting SmartHomeSimulator")

    logger.info("Fetching devices . . .")
    for attempt in range(RETRIES):
        try:
            response = requests.get(API_URL + '/api/devices')
            if 200 <= response.status_code < 400:
                for device_data in response.json():
                    success, reasons = validate_device_data(device_data, new_device=True)
                    if success:
                        create_device(device_data=device_data)
                    else:
                        logger.error(f"Failed to create device, reasons: {reasons}")
                break
            else:
                delay = 2 ** attempt + random.random()
                logger.error(f"Failed to get devices {response.status_code}.")
                logger.error(f"{response.text}")
                logger.error(f"Attempt {attempt + 1}/{RETRIES} failed. Retrying in {delay:.2f} seconds...")
                sleep(delay)
        except requests.exceptions.ConnectionError:
            logger.exception(f"Failed to connect to backend")
            delay = 2 ** attempt + random.random()
            logger.error(f"Attempt {attempt + 1}/{RETRIES} failed. Retrying in {delay:.2f} seconds...")
            sleep(delay)
        except ValueError as e:
            logger.error(f"{str(e)}")

    if not devices:
        logger.error("Failed to fetch devices. Shutting down.")
        sys.exit(1)

    init_mqtt()

    while not mqtt_connected:
        sleep(2)

    logger.info("Connected to MQTT")

    while True:
        sleep(2)
        for device in devices.values():
            device.tick()


if __name__ == "__main__":
    main()
