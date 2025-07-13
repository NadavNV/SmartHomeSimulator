from datetime import time
from time import sleep
from typing import Any, cast
import paho.mqtt.client as paho
import json
import logging
import logging.handlers
import requests
import os
import sys
import atexit
import random

from device import Device
from device_types import DeviceType

from air_conditioner import AirConditioner, Mode, FanSpeed, Swing
from light import Light
from curtain import Curtain
from door_lock import DoorLock
from water_heater import WaterHeater

BROKER_HOST = os.getenv("BROKER_HOST", "test.mosquitto.org")
BROKER_PORT = int(os.getenv("BROKER_PORT", 1883))

# How many times to attempt a connection request
RETRIES = 5

API_URL = os.getenv("API_URL", default='http://localhost:5200')

devices: list[Device] = []
logger = logging.getLogger(__name__)


def create_device(device_data: dict) -> None:
    required_fields = {'id', 'room', 'name', 'type'}
    if not required_fields <= device_data.keys():
        logger.error(f"Missing required field(s): {required_fields - device_data.keys()} ")
        return
    if id_exists(device_data["id"]):
        logger.error("ID already exists")
        return
    kwargs = {
        'device_id': device_data['id'],
        'room': device_data['room'],
        'name': device_data['name'],
        'mqtt_client': mqtt_client,
        'logger': logger,
    }
    parameters = device_data.get("parameters", {})
    if 'status' in device_data:
        kwargs['status'] = device_data['status']
    try:
        match device_data['type']:
            case DeviceType.WATER_HEATER:
                if 'temperature' in parameters:
                    kwargs['temperature'] = parameters['temperature']
                if 'target_temperature' in parameters:
                    kwargs['target_temperature'] = parameters['target_temperature']
                if 'is_heating' in parameters:
                    kwargs['is_heating'] = parameters['is_heating']
                if 'timer_enabled' in parameters:
                    kwargs['timer_enabled'] = parameters['timer_enabled']
                if 'scheduled_on' in parameters:
                    kwargs['scheduled_on'] = time.fromisoformat(
                        WaterHeater.fix_time_string(parameters['scheduled_on'])
                    )
                if 'scheduled_off' in parameters:
                    kwargs['scheduled_off'] = time.fromisoformat(
                        WaterHeater.fix_time_string(parameters['scheduled_off'])
                    )
                new_device = WaterHeater(**kwargs)
            case DeviceType.CURTAIN:
                if 'position' in parameters:
                    kwargs['position'] = parameters['position']
                new_device = Curtain(**kwargs)
            case DeviceType.DOOR_LOCK:
                if 'auto_lock_enabled' in parameters:
                    kwargs['auto_lock_enabled'] = parameters['auto_lock_enabled']
                if 'battery_level' in parameters:
                    kwargs['battery_level'] = parameters['battery_level']
                new_device = DoorLock(**kwargs)
            case DeviceType.LIGHT:
                if 'is_dimmable' in parameters:
                    kwargs['is_dimmable'] = parameters['is_dimmable']
                if 'brightness' in parameters:
                    kwargs['brightness'] = parameters['brightness']
                if 'dynamic_color' in parameters:
                    kwargs['dynamic_color'] = parameters['dynamic_color']
                if 'color' in parameters:
                    kwargs['color'] = parameters['color']
                new_device = Light(**kwargs)
            case DeviceType.AIR_CONDITIONER:
                if 'temperature' in parameters:
                    kwargs['temperature'] = parameters['temperature']
                if 'mode' in parameters:
                    kwargs['mode'] = Mode(parameters['mode'])
                if 'fan_speed' in parameters:
                    kwargs['fan_speed'] = FanSpeed(parameters['fan_speed'])
                if 'swing' in parameters:
                    kwargs['swing'] = Swing(parameters['swing'])
                new_device = AirConditioner(**kwargs)
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


# Checks the validity of the device id
def id_exists(device_id):
    for device in devices:
        if device_id == device.id:
            return True
    return False


def on_connect(client, _userdata, _connect_flags, reason_code, _properties):
    logger.info(f'CONNACK received with code {reason_code}.')
    if reason_code == 0:
        with open("./status", "a") as file:
            file.write("ready\n")
        logger.info("Connected successfully")
        client.subscribe("project/home/#")


def on_disconnect(_client, _userdata, _disconnect_flags, reason_code, _properties=None):
    if reason_code == 0:
        logger.warning(f"Disconnected from broker.")
    else:
        logger.warning(f"Disconnected from broker with reason: {reason_code}")
    with open("./status", "w") as file:
        file.write("healthy\n")


def on_subscribe(
        _client: paho.Client,
        _userdata: Any,
        _mid: int,
        reason_code_list: list[paho.ReasonCodes],
        _properties: paho.Properties,
):
    for rc in reason_code_list:
        logger.info(f"Subscribed with reason code {rc}")


def on_message(
        _client: paho.Client,
        _userdata: Any,
        msg: paho.MQTTMessage,
):
    sender_id = None
    props = msg.properties
    user_props = getattr(props, "UserProperty", None)
    if user_props is not None:
        sender_id = dict(user_props).get("sender_id")

    if sender_id is None:
        logger.error("Message missing sender")

    if sender_id == client_id:
        return

    logger.info(f"MQTT Message Received on {msg.topic}")
    payload = cast(bytes, msg.payload)
    try:
        payload = json.loads(payload.decode("utf-8"))

        # Extract device_id from topic: expected format project/home/<device_id>/<method>
        topic_parts = msg.topic.split('/')
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
            logger.error(f"Incorrect topic {msg.topic}")
    except UnicodeError:
        logger.exception("Error decoding payload")
    except ValueError:
        logger.exception("Value error")


client_id = f"simulator-{os.getenv('HOSTNAME')}"
mqtt_client = paho.Client(paho.CallbackAPIVersion.VERSION2, protocol=paho.MQTTv5, client_id=client_id)
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
                logger.error(f"{response.text}")
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
