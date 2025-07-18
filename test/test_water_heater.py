import unittest
from datetime import datetime as dt, time, timedelta
from unittest.mock import patch, MagicMock
from devices.water_heater import WaterHeater, DEFAULT_WATER_HEATER_STATUS, DEFAULT_WATER_TEMP, DEFAULT_SCHEDULED_ON, \
    DEFAULT_SCHEDULED_OFF, MIN_WATER_TEMP, MAX_WATER_TEMP, DEFAULT_IS_HEATING, DEFAULT_TIMER_ENABLED, ROOM_TEMPERATURE, \
    HEATING_RATE


class TestAirConditioner(unittest.TestCase):

    def setUp(self):
        self.mock_logger = MagicMock()
        self.device_logger_patcher = patch('devices.device.logging.getLogger', return_value=self.mock_logger)
        self.device_logger_patcher.start()

        self.device = WaterHeater(
            device_id="ac1",
            room="Living Room",
            name="Main AC",
            status="on",
            temperature=MIN_WATER_TEMP,
            target_temperature=(MIN_WATER_TEMP + MAX_WATER_TEMP) // 2,
            is_heating=True,
            timer_enabled=True,
            scheduled_on=time.fromisoformat("08:00"),
            scheduled_off=time.fromisoformat("08:30")
        )

    def tearDown(self):
        self.device_logger_patcher.stop()

    # 1. Initialization tests
    def test_initialization_default(self):
        self.device = WaterHeater(
            device_id="ac2",
            room="Bedroom",
            name="Bedroom AC"
        )
        self.assertEqual(self.device.status, DEFAULT_WATER_HEATER_STATUS)
        self.assertEqual(self.device.temperature, ROOM_TEMPERATURE)
        self.assertEqual(self.device.target_temperature, DEFAULT_WATER_TEMP)
        self.assertEqual(self.device.is_heating, DEFAULT_IS_HEATING)
        self.assertEqual(self.device.timer_enabled, DEFAULT_TIMER_ENABLED)
        self.assertEqual(self.device.scheduled_on, DEFAULT_SCHEDULED_ON)
        self.assertEqual(self.device.scheduled_off, DEFAULT_SCHEDULED_OFF)

    def test_initialization_valid(self):
        self.assertEqual(self.device.status, "on")
        self.assertEqual(self.device.temperature, MIN_WATER_TEMP)
        self.assertEqual(self.device.target_temperature, (MIN_WATER_TEMP + MAX_WATER_TEMP) // 2)
        self.assertEqual(self.device.is_heating, True)
        self.assertEqual(self.device.timer_enabled, True)
        self.assertEqual(self.device.scheduled_on.isoformat(), "08:00:00")
        self.assertEqual(self.device.scheduled_off.isoformat(), "08:30:00")

    def test_initialization_invalid_temperature_raises(self):
        with self.assertRaises(ValueError):
            WaterHeater("ac2", "Bedroom", "AC2", target_temperature=MIN_WATER_TEMP - 1)
        with self.assertRaises(ValueError):
            WaterHeater("ac2", "Bedroom", "AC2", target_temperature=MAX_WATER_TEMP + 1)

    # 2. Property setter tests
    def test_target_temperature_setter_valid(self):
        self.device.target_temperature = MIN_WATER_TEMP
        self.assertEqual(self.device.target_temperature, MIN_WATER_TEMP)

    def test_target_temperature_setter_invalid(self):
        with self.assertRaises(ValueError):
            self.device.target_temperature = MAX_WATER_TEMP + 1

    def test_timer_enabled_setter(self):
        self.device.timer_enabled = False
        self.assertFalse(self.device.timer_enabled)

    def test_scheduled_on_setter(self):
        new_time = time.fromisoformat("09:00")
        self.device.scheduled_on = new_time
        self.assertEqual(self.device.scheduled_on, new_time)

    def test_scheduled_off_setter(self):
        new_time = time.fromisoformat("09:30")
        self.device.scheduled_off = new_time
        self.assertEqual(self.device.scheduled_off, new_time)

    # 3. update_parameters
    def test_update_parameters_sets_multiple_values(self):
        self.device.update_parameters({
            "target_temperature": MIN_WATER_TEMP + 1,
            "timer_enabled": True,
            "scheduled_on": "05:45",
            "scheduled_off": "07:15",
        })
        self.assertEqual(self.device.target_temperature, MIN_WATER_TEMP + 1)
        self.assertTrue(self.device.timer_enabled)
        self.assertEqual(self.device.scheduled_on, time(5, 45))
        self.assertEqual(self.device.scheduled_off, time(7, 15))

    def test_update_parameters_logs_changes(self):
        self.device.update_parameters({
            "target_temperature": MIN_WATER_TEMP + 2
        })
        self.mock_logger.info.assert_any_call(f"Setting parameter 'target_temperature' to value '{MIN_WATER_TEMP + 2}'")

    # 4. tick behavior
    @patch("devices.water_heater.random.random", return_value=1.0)  # Prevent randomness
    @patch("devices.water_heater.WaterHeater.publish_mqtt")
    @patch("devices.water_heater.dt")
    def test_tick_heating_increases_temperature_and_stops_if_target_met(self, mock_dt, mock_publish, _):
        # Simulate current datetime
        fake_now = dt.combine(dt.today(), time(8, 15))
        mock_dt.now.return_value = fake_now
        mock_dt.combine.side_effect = dt.combine  # ensure combine still works
        mock_dt.today.side_effect = dt.today  # ensure today() works normally

        self.device.target_temperature = self.device.temperature + HEATING_RATE
        self.device.tick()

        # Check temp incremented
        self.assertEqual(self.device.temperature, self.device.target_temperature)
        # Should stop heating since target met
        self.assertFalse(self.device.is_heating)
        mock_publish.assert_called_once()

    @patch("devices.water_heater.dt")
    @patch("devices.water_heater.WaterHeater.publish_mqtt")
    @patch("devices.water_heater.random.random", return_value=1.0)
    def test_tick_turns_on_and_off_by_schedule(self, _, mock_publish, mock_dt):
        # Simulate current datetime
        fake_now = dt.combine(dt.today(), time(8, 0))
        mock_dt.now.return_value = fake_now
        mock_dt.combine.side_effect = dt.combine  # ensure combine still works
        mock_dt.today.side_effect = dt.today  # ensure today() works normally

        # Turn ON test
        self.device.status = "off"
        self.device.scheduled_on = (fake_now - timedelta(seconds=3)).time()
        self.device.scheduled_off = (fake_now + timedelta(seconds=10)).time()
        self.device.tick()
        self.assertEqual(self.device.status, "on")
        mock_publish.assert_called_once()

        # Turn OFF test
        mock_publish.reset_mock()
        self.device.status = "on"
        self.device.scheduled_on = (fake_now - timedelta(minutes=1)).time()
        self.device.scheduled_off = (fake_now - timedelta(seconds=2)).time()
        self.device.tick()
        self.assertEqual(self.device.status, "off")
        mock_publish.assert_called_once()

    @patch("devices.water_heater.random.random", return_value=0.0)  # Force random change
    @patch("devices.water_heater.random.choice", return_value="target_temperature")
    @patch("devices.water_heater.random.randint", return_value=MIN_WATER_TEMP + 6)
    @patch("devices.water_heater.WaterHeater.publish_mqtt")
    def test_tick_applies_random_target_temperature_change(self, _, mock_publish, *__):
        self.device._target_temperature = MIN_WATER_TEMP + 5
        self.device.tick()
        self.assertEqual(self.device.target_temperature, MIN_WATER_TEMP + 6)
        mock_publish.assert_called_once()

    # 5. fix_time_string
    def test_fix_time_string_valid_formats(self):
        self.assertEqual(WaterHeater.fix_time_string("8:5"), "08:05")
        self.assertEqual(WaterHeater.fix_time_string("8:5:2"), "08:05:02")

    def test_fix_time_string_invalid(self):
        with self.assertRaises(ValueError):
            WaterHeater.fix_time_string("invalid")


if __name__ == "__main__":
    unittest.main()
