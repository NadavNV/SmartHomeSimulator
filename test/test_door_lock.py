import unittest
from unittest.mock import patch, MagicMock
from devices.door_lock import DoorLock, DEFAULT_AUTO_LOCK, DEFAULT_BATTERY, MIN_BATTERY, MAX_BATTERY, \
    DEFAULT_LOCK_STATUS, BATTERY_DRAIN


class TestDoorLock(unittest.TestCase):

    def setUp(self):
        self.mock_logger = MagicMock()
        self.device_logger_patcher = patch('devices.device.logging.getLogger', return_value=self.mock_logger)
        self.device_logger_patcher.start()

        self.device = DoorLock(
            device_id="ac1",
            room="Living Room",
            name="Main AC",
            status="locked",
            auto_lock_enabled=True,
            battery_level=(MIN_BATTERY + MAX_BATTERY) // 2
        )

    def tearDown(self):
        self.device_logger_patcher.stop()

    # 1. Initialization tests
    def test_initialization_default(self):
        self.device = DoorLock(
            device_id="ac2",
            room="Bedroom",
            name="Bedroom AC"
        )
        self.assertEqual(self.device.status, DEFAULT_LOCK_STATUS)
        self.assertEqual(self.device.auto_lock_enabled, DEFAULT_AUTO_LOCK)
        self.assertEqual(self.device.battery_level, DEFAULT_BATTERY)

    def test_initialization_valid(self):
        self.assertEqual(self.device.status, "locked")
        self.assertEqual(self.device.auto_lock_enabled, True)
        self.assertEqual(self.device.battery_level, (MIN_BATTERY + MAX_BATTERY) // 2)

    def test_initialization_invalid_battery_raises(self):
        with self.assertRaises(ValueError):
            DoorLock("ac2", "Bedroom", "AC2", battery_level=MAX_BATTERY + 1)
        with self.assertRaises(ValueError):
            DoorLock("ac2", "Bedroom", "AC2", battery_level=MIN_BATTERY - 1)

    # 2. Property setter tests
    def test_auto_lock_enabled_setter(self):
        self.device.auto_lock_enabled = False
        self.assertEqual(self.device.auto_lock_enabled, False)

    def test_battery_setter_valid(self):
        self.device.battery_level = MAX_BATTERY - 1
        self.assertEqual(self.device.battery_level, MAX_BATTERY - 1)

    def test_battery_setter_invalid(self):
        with self.assertRaises(ValueError):
            self.device.battery_level = MAX_BATTERY + 1
        with self.assertRaises(ValueError):
            self.device.battery_level = MIN_BATTERY - 1

    # 3. update_parameters
    def test_update_parameters_all_valid(self):
        params = {
            "auto_lock_enabled": False,
        }
        self.device.update_parameters(params)
        self.assertEqual(self.device.auto_lock_enabled, False)

    # 4. tick behavior (mocking randomness and publish)
    @patch("devices.air_conditioner.random.random")
    @patch.object(DoorLock, 'publish_mqtt')
    def test_tick_changes_status(self, mock_publish, mock_random):
        mock_random.return_value = 0.0  # force change
        self.device.tick()
        self.assertEqual(self.device.battery_level, (MIN_BATTERY + MAX_BATTERY) // 2 - BATTERY_DRAIN)
        self.assertEqual(self.device.status, 'unlocked')
        mock_publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
