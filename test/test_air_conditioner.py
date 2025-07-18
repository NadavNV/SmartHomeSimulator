import unittest
from unittest.mock import patch, MagicMock
from devices.air_conditioner import AirConditioner, Mode, FanSpeed, Swing, MIN_AC_TEMP, MAX_AC_TEMP, DEFAULT_FAN, \
    DEFAULT_MODE, DEFAULT_SWING, DEFAULT_AC_TEMPERATURE, DEFAULT_AC_STATUS


class TestAirConditioner(unittest.TestCase):

    def setUp(self):
        self.mock_logger = MagicMock()
        self.device_logger_patcher = patch('devices.device.logging.getLogger', return_value=self.mock_logger)
        self.device_logger_patcher.start()

        self.device = AirConditioner(
            device_id="ac1",
            room="Living Room",
            name="Main AC",
            status="on",
            temperature=22,
            mode=Mode.HEAT,
            fan_speed=FanSpeed.MEDIUM,
            swing=Swing.AUTO
        )

    def tearDown(self):
        self.device_logger_patcher.stop()

    # 1. Initialization tests
    def test_initialization_default(self):
        self.device = AirConditioner(
            device_id="ac2",
            room="Bedroom",
            name="Bedroom AC"
        )
        self.assertEqual(self.device.status, DEFAULT_AC_STATUS)
        self.assertEqual(self.device.temperature, DEFAULT_AC_TEMPERATURE)
        self.assertEqual(self.device.mode, DEFAULT_MODE)
        self.assertEqual(self.device.fan_speed, DEFAULT_FAN)
        self.assertEqual(self.device.swing, DEFAULT_SWING)

    def test_initialization_valid(self):
        self.assertEqual(self.device.status, "on")
        self.assertEqual(self.device.temperature, 22)
        self.assertEqual(self.device.mode, Mode.HEAT)
        self.assertEqual(self.device.fan_speed, FanSpeed.MEDIUM)
        self.assertEqual(self.device.swing, Swing.AUTO)

    def test_initialization_invalid_temperature_raises(self):
        with self.assertRaises(ValueError):
            AirConditioner("ac2", "Bedroom", "AC2", temperature=10)

    # 2. Property setter tests
    def test_temperature_setter_valid(self):
        self.device.temperature = MIN_AC_TEMP
        self.assertEqual(self.device.temperature, MIN_AC_TEMP)

    def test_temperature_setter_invalid(self):
        with self.assertRaises(ValueError):
            self.device.temperature = MAX_AC_TEMP + 5

    def test_mode_setter(self):
        self.device.mode = Mode.HEAT
        self.assertEqual(self.device.mode, Mode.HEAT)

    def test_fan_speed_setter(self):
        self.device.fan_speed = FanSpeed.HIGH
        self.assertEqual(self.device.fan_speed, FanSpeed.HIGH)

    def test_swing_setter(self):
        self.device.swing = Swing.AUTO
        self.assertEqual(self.device.swing, Swing.AUTO)

    # 3. update_parameters
    def test_update_parameters_all_valid(self):
        params = {
            "temperature": (MIN_AC_TEMP + MAX_AC_TEMP) / 2,
            "mode": "fan",
            "fan_speed": "medium",
            "swing": "on"
        }
        self.device.update_parameters(params)
        self.assertEqual(self.device.temperature, (MIN_AC_TEMP + MAX_AC_TEMP) / 2)
        self.assertEqual(self.device.mode, Mode.FAN)
        self.assertEqual(self.device.fan_speed, FanSpeed.MEDIUM)
        self.assertEqual(self.device.swing, Swing.ON)

    def test_update_parameters_invalid_temperature_raises(self):
        with self.assertRaises(ValueError):
            self.device.update_parameters({"temperature": MAX_AC_TEMP + 1})
        with self.assertRaises(ValueError):
            self.device.update_parameters({"temperature": MIN_AC_TEMP - 1})

    # 4. tick behavior (mocking randomness and publish)
    @patch("devices.air_conditioner.random.random")
    @patch("devices.air_conditioner.random.choice")
    @patch.object(AirConditioner, 'publish_mqtt')
    def test_tick_changes_status(self, mock_publish, mock_choice, mock_random):
        mock_random.return_value = 0.0  # force change
        mock_choice.return_value = 'status'
        self.device.tick()
        self.assertEqual(self.device.status, 'off')
        mock_publish.assert_called_once()

    @patch("devices.air_conditioner.random.random")
    @patch("devices.air_conditioner.random.choice")
    @patch.object(AirConditioner, 'publish_mqtt')
    def test_tick_changes_temperature(self, mock_publish, mock_choice, mock_random):
        mock_random.return_value = 0.0
        mock_choice.side_effect = ['temperature']
        with patch("devices.air_conditioner.random.randint",
                   return_value=MIN_AC_TEMP if self.device.temperature != MIN_AC_TEMP else MIN_AC_TEMP + 1):
            self.device.tick()
        self.assertNotEqual(self.device.temperature, 24)
        mock_publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
