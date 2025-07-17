import os
import sys
import requests
import random
import logging
from time import sleep
from datetime import time
from validation.validators import validate_device_data

# How many times to attempt a connection request
RETRIES = 5

API_URL = os.getenv("API_URL", default='http://localhost:5200')

devices = {}
logger = logging.getLogger("smart-home.core")


# TODO: docstrings
def create_device(device_data: dict) -> None:
    from devices.device_types import DeviceType
    from devices.light import Light
    from devices.curtain import Curtain
    from devices.door_lock import DoorLock
    from devices.water_heater import WaterHeater
    from devices.air_conditioner import AirConditioner, Mode, FanSpeed, Swing
    success, reasons = validate_device_data(device_data, new_device=True)
    if not success:
        raise ValueError(f"{reasons}")
    if device_data["id"] in devices:
        raise ValueError(f"ID {device_data["id"]} already exists")
    kwargs = {
        'device_id': device_data['id'],
        'room': device_data['room'],
        'name': device_data['name'],
    }
    parameters = device_data.get("parameters", {})
    if 'status' in device_data:
        kwargs['status'] = device_data['status']
    kwargs.update(parameters)
    match device_data['type']:
        case DeviceType.WATER_HEATER:
            if 'scheduled_on' in kwargs:
                kwargs['scheduled_on'] = time.fromisoformat(
                    WaterHeater.fix_time_string(kwargs['scheduled_on'])
                )
            if 'scheduled_off' in kwargs:
                kwargs['scheduled_off'] = time.fromisoformat(
                    WaterHeater.fix_time_string(kwargs['scheduled_off'])
                )
            new_device = WaterHeater(**kwargs)
        case DeviceType.CURTAIN:
            new_device = Curtain(**kwargs)
        case DeviceType.DOOR_LOCK:
            new_device = DoorLock(**kwargs)
        case DeviceType.LIGHT:
            new_device = Light(**kwargs)
        case DeviceType.AIR_CONDITIONER:
            if 'mode' in kwargs:
                kwargs['mode'] = Mode(kwargs['mode'])
            if 'fan_speed' in kwargs:
                kwargs['fan_speed'] = FanSpeed(kwargs['fan_speed'])
            if 'swing' in kwargs:
                kwargs['swing'] = Swing(kwargs['swing'])
            new_device = AirConditioner(**kwargs)
        case _:
            raise ValueError(f"Unknown device type {device_data['type']}")
    if new_device is not None:
        devices[new_device.id] = new_device
        logger.info("Device added successfully")
        return
    else:
        logger.error(f"Failed to create device {device_data['id']}")
        return


def load_devices():
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
