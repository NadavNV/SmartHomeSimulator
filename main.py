from datetime import time
from time import sleep
from typing import Any
import paho.mqtt.client as paho
import json
import logging
import logging.handlers

from device import Device
from device_types import DeviceType

from air_conditioner import AirConditioner, Mode, FanSpeed, Swing
from light import Light
from curtain import Curtain
from door_lock import DoorLock
from water_heater import WaterHeater

BROKER_HOST = "test.mosquitto.org"
BROKER_PORT = 1883
# Temporary local json -> stand in for a future database
DATA_FILE_NAME = "./data.json"

devices: list[Device] = []
logger = logging.getLogger(__name__)


def create_device(device_data: dict, mqtt_client: paho.Client) -> None:
    if validate_device_data(device_data):
        if id_exists(device_data["id"]):
            logger.error("ID already exists")
            return
        try:
            match device_data['type']:
                case DeviceType.WATER_HEATER:
                    new_device = WaterHeater(
                        device_id=device_data['id'],
                        room=device_data['room'],
                        name=device_data['name'],
                        mqtt_client=mqtt_client,
                        logger=logger,
                        status=device_data['status'],
                        temperature=device_data['parameters']['temperature'],
                        target_temperature=device_data['parameters']['target_temperature'],
                        is_heating=device_data['parameters']['is_heating'],
                        timer_enabled=device_data['parameters']['timer_enabled'],
                        scheduled_on=time.fromisoformat(device_data['parameters']['scheduled_on']),
                        scheduled_off=time.fromisoformat(device_data['parameters']['scheduled_off']),
                    )
                case DeviceType.CURTAIN:
                    new_device = Curtain(
                        device_id=device_data['id'],
                        room=device_data['room'],
                        name=device_data['name'],
                        mqtt_client=mqtt_client,
                        logger=logger,
                        status=device_data['status'],
                        position=device_data['parameters']['position'],
                    )
                case DeviceType.DOOR_LOCK:
                    new_device = DoorLock(
                        device_id=device_data['id'],
                        room=device_data['room'],
                        name=device_data['name'],
                        mqtt_client=mqtt_client,
                        logger=logger,
                        status=device_data['status'],
                        auto_lock_enabled=device_data['parameters']['auto_lock_enabled'],
                        battery_level=device_data['parameters']['battery_level'],
                    )
                case DeviceType.LIGHT:
                    new_device = Light(
                        device_id=device_data['id'],
                        room=device_data['room'],
                        name=device_data['name'],
                        mqtt_client=mqtt_client,
                        logger=logger,
                        status=device_data['status'],
                        is_dimmable=device_data['parameters']['is_dimmable'],
                        brightness=device_data['parameters']['brightness'],
                        dynamic_color=device_data['parameters']['dynamic_color'],
                        color=device_data['parameters']['color'],
                    )
                case DeviceType.AIR_CONDITIONER:
                    new_device = AirConditioner(
                        device_id=device_data['id'],
                        room=device_data['room'],
                        name=device_data['name'],
                        mqtt_client=mqtt_client,
                        logger=logger,
                        status=device_data['status'],
                        temperature=device_data['parameters']['temperature'],
                        mode=Mode(value=device_data['parameters']['mode']),
                        fan_speed=FanSpeed(value=device_data['parameters']['fan_speed']),
                        swing=Swing(value=device_data['parameters']['swing']),
                    )
                case _:
                    logger.error(f"Unknown device type {device_data['type']}")
                    return
            if new_device is not None:
                devices.append(new_device)
                logger.info("Device added successfully")
                return
            else:
                logger.error(f"Failed to create device {device_data['id']}")
        except ValueError:
            logger.exception(f"Failed to create device {device_data['id']}")
            return
    logger.error("Missing required field")
    return


# Validates that the request data contains all the required fields
def validate_device_data(new_device):
    required_fields = ['id', 'type', 'room', 'name', 'status', 'parameters']
    for field in required_fields:
        if field not in new_device:
            return False
    return True


# Checks the validity of the device id
def id_exists(device_id):
    for device in devices:
        if device_id == device.id:
            return True
    return False


def on_connect(client, userdata, connect_flags, reason_code, properties):
    logger.info(f'CONNACK received with code {reason_code}.')
    if reason_code == 0:
        client.subscribe("project/home/#")


def on_subscribe(
        client: paho.Client,
        userdata: Any,
        mid: int,
        reason_code_list: list[paho.ReasonCodes],
        properties: paho.Properties,
):
    for rc in reason_code_list:
        logger.info(f"Subscribed with reason code {rc}")


def on_message(
        client: paho.Client,
        userdata: Any,
        message: paho.MQTTMessage,
):
    logger.info(f"MQTT message received on topic {message.topic}")
    try:
        payload = json.loads(message.payload.decode())
        # Ignore self messages
        if "sender" in payload:
            if payload["sender"] == "simulator":
                logger.info("Ignoring self message")
                return
            else:
                payload = payload["contents"]
        else:
            logger.error("Payload missing sender")
            return

        # Extract device_id from topic: expected format project/home/<room>/<device_id>/<method>
        topic_parts = message.topic.split('/')
        if len(topic_parts) >= 5:
            device_id = topic_parts[3]
            method = topic_parts[-1]
            match method:
                case "action" | "update":
                    for device in devices:
                        if device.id == device_id:
                            try:
                                device.update(payload)
                                return
                            except ValueError:
                                logger.exception(f"Failed to update device {device.id}")
                                return
                    logger.error(f"Device ID {device_id} not found")
                case "post":
                    create_device(device_data=payload, mqtt_client=client)
                    return
                case "delete":
                    index_to_delete = None
                    if id_exists(device_id):
                        for index, device in enumerate(devices):
                            if device.id == device_id:
                                index_to_delete = index
                        if index_to_delete is not None:
                            devices.pop(index_to_delete)
                            logger.info("Device deleted successfully")
                            return
                    logger.error("ID not found")
                    return
                case _:
                    logger.error(f"Unknown method: {method}")
                    return
        else:
            logger.error(f"Incorrect topic {message.topic}")
    except UnicodeError:
        logger.exception("Error decoding payload")
    except ValueError:
        logger.exception("Value error")


def main() -> None:
    logging.basicConfig(
        format="[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
        handlers=[
            # Prints to sys.stderr
            logging.StreamHandler(),
            # Writes to a log file which rotates every hour
            logging.handlers.TimedRotatingFileHandler(filename="simulator.log", backupCount=5)],
        level=logging.DEBUG,
    )
    mqtt_client = paho.Client(paho.CallbackAPIVersion.VERSION2)
    mqtt_client.on_message = on_message
    mqtt_client.on_connect = on_connect
    mqtt_client.on_subscribe = on_subscribe

    data = []
    with open(DATA_FILE_NAME, mode="r", encoding="utf-8") as read_file:
        data = json.load(read_file)
    for device_data in data:
        create_device(device_data=device_data, mqtt_client=mqtt_client)

    mqtt_client.connect(BROKER_HOST, BROKER_PORT)

    mqtt_client.loop_start()

    while True:
        sleep(2)
        for device in devices:
            device.tick()


if __name__ == "__main__":
    main()
