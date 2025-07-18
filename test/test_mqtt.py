import os
import unittest
import random
from collections import namedtuple

import json
from unittest import TestCase
from unittest.mock import MagicMock, patch, call
from paho.mqtt.properties import Properties
from paho.mqtt.packettypes import PacketTypes
from copy import deepcopy

import services.mqtt
from core.device_utils import get_devices, create_device
from services.mqtt import on_connect, on_disconnect, on_message, publish_mqtt
from validation.validators import (
    MIN_WATER_TEMP, MAX_WATER_TEMP,
)

VALID_TOPIC = f"nadavnv-smart-home/devices/"
CLIENT_ID = f"simulator-{os.getenv('HOSTNAME')}"


class MessageQueueMatcher:

    def __init__(self, lst):
        self.list = lst

    def __eq__(self, other):
        if len(self.list) != len(other):
            return False
        for i in range(len(self.list)):
            try:
                if not (
                        self.list[i]["args"] == other[i]["args"] and
                        self.list[i]["kwargs"]["qos"] == other[i]["kwargs"]["qos"] and
                        dict(self.list[i]["kwargs"]["properties"].UserProperty) == dict(other[i]["kwargs"][
                                                                                            "properties"].UserProperty)
                ):
                    return False
            except KeyError as e:
                return False
        return True


def fake_mqtt_client(*_args, **_kwargs):
    mock_client = MagicMock()
    mock_client.connect_async.return_value = None
    mock_client.disconnect.return_value = None
    mock_client.loop_start.return_value = None
    mock_client.loop_stop.return_value = None
    mock_client.subscribe.return_value = 0
    Info = namedtuple("Info", "rc mid")
    mock_client.publish.side_effect = [Info(1, None), Info(1, None), Info(0, None)]
    return mock_client


class TestMQTT(TestCase):

    def setUp(self):
        # Patch the loggers
        self.mock_logger = MagicMock()
        self.mqtt_logger_patcher = patch('services.mqtt.logger', self.mock_logger)
        self.validators_logger_patcher = patch('validation.validators.logger', self.mock_logger)
        self.device_utils_logger_patcher = patch('core.device_utils.logger', self.mock_logger)
        self.device_logger_patcher = patch('devices.device.logging.getLogger', return_value=self.mock_logger)
        self.mqtt_logger_patcher.start()
        self.device_utils_logger_patcher.start()
        self.validators_logger_patcher.start()
        self.device_logger_patcher.start()

        self.mock_mqtt_client = fake_mqtt_client()

        self.get_mqtt_patch = patch('services.mqtt.get_mqtt', return_value=self.mock_mqtt_client)
        self.get_mqtt_patch.start()

        self.valid_water_heater = {
            "id": "main-water-heater",
            "type": "water_heater",
            "name": "Main Water Heater",
            "room": "Main Bath",
            "status": "off",
            "parameters": {
                "temperature": 40,
                "target_temperature": (MIN_WATER_TEMP + MAX_WATER_TEMP) / 2,
                "is_heating": False,
                "timer_enabled": True,
                "scheduled_on": "06:30",
                "scheduled_off": "08:00"
            }
        }

    def tearDown(self):
        get_devices().pop(self.valid_water_heater["id"], None)
        self.mqtt_logger_patcher.stop()
        self.get_mqtt_patch.stop()
        self.device_utils_logger_patcher.stop()
        self.validators_logger_patcher.stop()
        self.device_logger_patcher.stop()

    def test_on_connect_success(self):
        client = MagicMock()
        on_connect(client, None, {}, 0)
        calls = [call('CONNACK received with code 0.'), call("Connected successfully")]
        self.mock_logger.info.assert_has_calls(calls, any_order=False)
        client.subscribe.assert_called_with("$share/simulator/nadavnv-smart-home/devices/#")

    def test_on_connect_failure(self):
        client = MagicMock()
        on_connect(client=client, _userdata=None, _connect_flags={}, reason_code=1)
        calls = [call('CONNACK received with code 1.')]
        self.mock_logger.info.assert_has_calls(calls, any_order=False)
        client.subscribe.assert_not_called()

    def test_on_disconnect_random(self):
        reason_code = random.randint(0, 23)
        on_disconnect(None, None, None, reason_code)
        self.mock_logger.warning.assert_called_with(f"Disconnected from broker with reason: {reason_code}")

    def test_on_message_invalid_method(self):
        fake_msg = MagicMock()
        fake_msg.payload = json.dumps(deepcopy(self.valid_water_heater)).encode()
        fake_msg.topic = VALID_TOPIC + f"{self.valid_water_heater["id"]}/steve"

        on_message(None, None, fake_msg)
        self.mock_logger.error.assert_called_with(f"Unknown method: steve")
        self.mock_logger.info.assert_called_with(f"MQTT Message Received on {fake_msg.topic}")

    def test_on_message_invalid_topic(self):
        fake_msg = MagicMock()
        fake_msg.payload = json.dumps(deepcopy(self.valid_water_heater)).encode()
        fake_msg.topic = VALID_TOPIC + f"{self.valid_water_heater["id"]}/post/extra"

        on_message(None, None, fake_msg)
        self.mock_logger.error.assert_called_with(f"Incorrect topic {fake_msg.topic}")
        self.mock_logger.info.assert_called_with(f"MQTT Message Received on {fake_msg.topic}")

    def test_on_message_valid_post_no_props(self):
        fake_msg = MagicMock()
        fake_msg.payload = json.dumps(deepcopy(self.valid_water_heater)).encode()
        fake_msg.topic = VALID_TOPIC + f"{self.valid_water_heater["id"]}/post"

        on_message(None, None, fake_msg)
        error_calls = [call("Message missing sender"), call("Message missing sender group")]
        info_calls = [
            call(f"MQTT Message Received on {fake_msg.topic}"),
            call("Device added successfully"),
        ]
        self.mock_logger.info.assert_has_calls(info_calls)
        self.mock_logger.error.assert_has_calls(error_calls)
        self.assertEqual(self.valid_water_heater,
                         get_devices()[self.valid_water_heater["id"]].to_dict())

    def test_on_message_valid_post_backend_group(self):
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_group', 'backend')]

        fake_msg = MagicMock()
        fake_msg.payload = json.dumps(deepcopy(self.valid_water_heater)).encode()
        fake_msg.topic = VALID_TOPIC + f"{self.valid_water_heater["id"]}/post"
        fake_msg.properties = props

        on_message(None, None, fake_msg)
        self.mock_logger.error.assert_called_with("Message missing sender")

    def test_on_message_invalid_ignored(self):
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID), ('sender_group', 'simulator')]

        fake_msg = MagicMock()
        fake_msg.payload = json.dumps(deepcopy(self.valid_water_heater)).encode()
        fake_msg.topic = VALID_TOPIC + f"{self.valid_water_heater["id"]}/post"
        fake_msg.properties = props

        on_message(None, None, fake_msg)
        self.mock_logger.info.assert_not_called()

    def test_on_message_invalid_post_id_exists(self):
        create_device(self.valid_water_heater)
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID + "2"), ('sender_group', 'backend')]

        fake_msg = MagicMock()
        fake_msg.payload = json.dumps(deepcopy(self.valid_water_heater)).encode()
        fake_msg.topic = VALID_TOPIC + f"{self.valid_water_heater["id"]}/post"
        fake_msg.properties = props
        with self.assertRaisesRegex(ValueError, f"ID {self.valid_water_heater["id"]} already exists"):
            on_message(None, None, fake_msg)

    def test_on_message_invalid_post_id_mismatch(self):
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID + "2"), ('sender_group', 'backend')]

        fake_msg = MagicMock()
        fake_msg.payload = json.dumps(deepcopy(self.valid_water_heater)).encode()
        fake_msg.topic = VALID_TOPIC + f"steve/post"
        fake_msg.properties = props

        on_message(None, None, fake_msg)
        self.mock_logger.error.assert_called_with(
            f"ID mismatch: ID in URL: steve, ID in payload: {self.valid_water_heater["id"]}"
        )

    def test_on_message_invalid_post_bad_data(self):
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID + "2"), ('sender_group', 'backend')]

        fake_msg = MagicMock()
        device = deepcopy(self.valid_water_heater)
        device["status"] = "steve"
        fake_msg.payload = json.dumps(device).encode()
        fake_msg.topic = VALID_TOPIC + f"{device["id"]}/post"
        fake_msg.properties = props

        on_message(None, None, fake_msg)
        reasons = [f"'{device["status"]}' is not a valid value for 'status'. Must be one of { {'on', 'off'} }."]
        self.mock_logger.error.assert_called_with(
            f"Failed to create device, reasons: {reasons}"
        )

    def test_on_message_valid_update(self):
        create_device(self.valid_water_heater)
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID + "2"), ('sender_group', 'backend')]

        fake_msg = MagicMock()
        device = deepcopy(self.valid_water_heater)
        device["parameters"]["target_temperature"] = (MIN_WATER_TEMP + MAX_WATER_TEMP) / 2 - 1
        fake_msg.payload = json.dumps(
            {"parameters": {"target_temperature": (MIN_WATER_TEMP + MAX_WATER_TEMP) / 2 - 1}}).encode()
        fake_msg.topic = VALID_TOPIC + f"{device["id"]}/update"
        fake_msg.properties = props

        on_message(None, None, fake_msg)
        calls = [
            call(f"MQTT Message Received on {fake_msg.topic}"),
            call(f"Setting parameter 'target_temperature' to value '{(MIN_WATER_TEMP + MAX_WATER_TEMP) / 2 - 1}'"),
            call(f"Device {device["id"]} updated successfully"),
        ]
        self.mock_logger.info.assert_has_calls(calls)
        self.assertEqual(device, get_devices()[self.valid_water_heater["id"]].to_dict())

    def test_on_message_invalid_update_missing_id(self):
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID + "2"), ('sender_group', 'backend')]

        fake_msg = MagicMock()
        device_id = self.valid_water_heater
        fake_msg.payload = json.dumps({"parameters": {"temperature": (MIN_WATER_TEMP + MAX_WATER_TEMP) / 2}}).encode()
        fake_msg.topic = VALID_TOPIC + f"{device_id}/update"
        fake_msg.properties = props

        on_message(None, None, fake_msg)
        self.mock_logger.info.assert_called_with(f"MQTT Message Received on {fake_msg.topic}")
        self.mock_logger.error.assert_called_with(f"Device ID {device_id} not found")

    def test_on_message_invalid_update_bad_data(self):
        create_device(self.valid_water_heater)
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID + "2"), ('sender_group', 'backend')]

        fake_msg = MagicMock()
        fake_msg.payload = json.dumps({"parameters": {"target_temperature": MAX_WATER_TEMP + 1}}).encode()
        fake_msg.topic = VALID_TOPIC + f"{self.valid_water_heater["id"]}/update"
        fake_msg.properties = props

        on_message(None, None, fake_msg)
        self.mock_logger.info.assert_called_with(f"MQTT Message Received on {fake_msg.topic}")
        reasons = [f"'target_temperature' must be between {MIN_WATER_TEMP} and"
                   f" {MAX_WATER_TEMP}, got {MAX_WATER_TEMP + 1} instead."]
        self.mock_logger.error.assert_called_with(f"Failed to update device, reasons: {reasons}")

    def test_on_message_valid_delete(self):
        create_device(self.valid_water_heater)
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID + "2"), ('sender_group', 'backend')]

        fake_msg = MagicMock()
        device_id = self.valid_water_heater["id"]
        fake_msg.payload = json.dumps({}).encode()
        fake_msg.topic = VALID_TOPIC + f"{device_id}/delete"
        fake_msg.properties = props

        on_message(None, None, fake_msg)
        calls = [
            call(f"MQTT Message Received on {fake_msg.topic}"),
            call(f"Device {self.valid_water_heater["id"]} deleted successfully")
        ]
        self.mock_logger.info.assert_has_calls(calls)
        self.assertNotIn(self.valid_water_heater["id"], get_devices())

    def test_on_message_invalid_delete_missing_id(self):
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID + "2"), ('sender_group', 'backend')]

        fake_msg = MagicMock()
        device_id = self.valid_water_heater["id"]
        fake_msg.payload = json.dumps({}).encode()
        fake_msg.topic = VALID_TOPIC + f"{device_id}/delete"
        fake_msg.properties = props

        on_message(None, None, fake_msg)
        self.mock_logger.info.assert_called_with(f"MQTT Message Received on {fake_msg.topic}")
        self.mock_logger.error.assert_called_with(f"Device ID {device_id} not found")

    def test_publish_failure(self):
        payload = {"key": "value"}
        publish_mqtt(update=payload, device_id="steve")
        self.mock_logger.error.assert_called_with("Error trying to publish, reason code: 1.")
        props = Properties(PacketTypes.PUBLISH)
        props.UserProperty = [('sender_id', CLIENT_ID), ('sender_group', 'simulator')]
        msg = {
            "args": [VALID_TOPIC + "steve/update", json.dumps(payload).encode("utf-8")],
            "kwargs": {
                "qos": 2,
                "properties": props,
            }
        }
        self.assertEqual(MessageQueueMatcher([msg]), services.mqtt.message_queue)
        on_connect(self.mock_mqtt_client, None, None, 0, None)
        self.assertEqual(MessageQueueMatcher([msg]), services.mqtt.message_queue)
        on_connect(self.mock_mqtt_client, None, None, 0, None)
        self.assertEqual(services.mqtt.message_queue, [])


if __name__ == "__main__":
    unittest.main()
