from datetime import time
from time import sleep
from typing import Any
import paho.mqtt.client as paho
import json
import logging
import logging.handlers
import requests
import os
import sys
import atexit
import socket
import random

from device import Device
from device_types import DeviceType

from air_conditioner import AirConditioner, Mode, FanSpeed, Swing
from light import Light
from curtain import Curtain
from door_lock import DoorLock
from water_heater import WaterHeater

BROKER_HOST = "test.mosquitto.org"
BROKER_PORT = 1883

# How many times to attempt a connection request
RETRIES = 5

API_URL = os.getenv("API_URL", default='http://localhost:5200')

devices: list[Device] = []
logger = logging.getLogger(__name__)


def create_device(device_data: dict) -> None:
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
                return
        except ValueError:
            logger.exception(f"Failed to create device {device_data['id']}")
    logger.error("Missing required field")


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
        with open("./status", "a") as file:
            file.write("ready\n")
        logger.info("Connected successfully")
        client.subscribe("project/home/#")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    if reason_code == 0:
        logger.warning(f"Disconnected from broker.")
    else:
        logger.warning(f"Disconnected from broker with reason: {reason_code}")
    with open("./status", "w") as file:
        file.write("healthy\n")


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

        # Extract device_id from topic: expected format project/home/<device_id>/<method>
        topic_parts = message.topic.split('/')
        if len(topic_parts) == 4:
            device_id = topic_parts[2]
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
                    create_device(device_data=payload)
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


mqtt_client = paho.Client(paho.CallbackAPIVersion.VERSION2)
mqtt_client.on_message = on_message
mqtt_client.on_connect = on_connect
mqtt_client.on_disconnect = on_disconnect
mqtt_client.on_subscribe = on_subscribe


@atexit.register
def shutdown() -> None:
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    if os.path.exists("./status"):
        os.remove("./status")
    logger.info("Shutting down")


def main() -> None:
    with open("./status", "w") as file:
        file.write("healthy\n")
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
    logger.info("Starting SmartHomeSimulator")

    logger.info("Fetching devices . . .")
    for attempt in range(RETRIES):
        try:
            response = requests.get(API_URL + '/api/devices')
            if 200 <= response.status_code < 400:
                for device_data in response.json():
                    create_device(device_data=device_data)
                break
            else:
                delay = 2 ** attempt + random.random()
                logger.error(f"Failed to get devices {response.status_code}.")
                logger.error(f"Attempt {attempt + 1}/{RETRIES} failed. Retrying in {delay:.2f} seconds...")
                sleep(delay)
        except requests.exceptions.ConnectionError:
            logger.error(f"Failed to connect to backend")
            delay = 2 ** attempt + random.random()
            logger.error(f"Attempt {attempt + 1}/{RETRIES} failed. Retrying in {delay:.2f} seconds...")
            sleep(delay)

    if not devices:
        logger.error("Failed to fetch devices. Shutting down.")
        sys.exit(1)

    mqtt_client.connect_async(BROKER_HOST, BROKER_PORT, 60)
    mqtt_client.loop_start()

    while True:
        sleep(2)
        for device in devices:
            device.tick()


if __name__ == "__main__":
    main()
