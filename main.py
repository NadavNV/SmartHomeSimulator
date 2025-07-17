import config.env  # noqa: F401  # load_dotenv side effect
from time import sleep
import logging.handlers
import os
import atexit

from core.device_utils import devices, load_devices
from services.mqtt import init_mqtt, get_mqtt, is_mqtt_connected, MQTTNotInitializedError

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


@atexit.register
def shutdown() -> None:
    try:
        get_mqtt().loop_stop()
        get_mqtt().disconnect()
    except MQTTNotInitializedError:
        logger.warning("MQTT not initialized")
    if os.path.exists("./status"):
        os.remove("./status")
    logger.info("Shutting down")


def main() -> None:
    with open("./status", "w") as file:
        file.write("healthy\n")

    logger.info("Starting SmartHomeSimulator")

    logger.info("Fetching devices . . .")
    load_devices()

    init_mqtt()
    while not is_mqtt_connected():
        sleep(2)
    logger.info("Connected to MQTT")

    while True:
        sleep(2)
        for device in devices.values():
            device.tick()


if __name__ == "__main__":
    main()
