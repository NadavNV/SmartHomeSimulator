import unittest
from unittest.mock import patch, MagicMock
from devices.light import Light, DEFAULT_COLOR, DEFAULT_DYNAMIC_COLOR, DEFAULT_BRIGHTNESS, DEFAULT_DIMMABLE, \
    DEFAULT_LIGHT_STATUS, MIN_BRIGHTNESS, MAX_BRIGHTNESS


class TestLight(unittest.TestCase):

    def setUp(self):
        self.mock_logger = MagicMock()
        self.device_logger_patcher = patch('devices.device.logging.getLogger', return_value=self.mock_logger)
        self.device_logger_patcher.start()

        self.device = Light(
            device_id="ac1",
            room="Living Room",
            name="Main AC",
            status="on",
            is_dimmable=True,
            brightness=MIN_BRIGHTNESS if MIN_BRIGHTNESS != DEFAULT_BRIGHTNESS else MIN_BRIGHTNESS + 1,
            dynamic_color=True,
            color="#123456"
        )

    def tearDown(self):
        self.device_logger_patcher.stop()

    # 1. Initialization tests
    def test_initialization_default(self):
        self.device = Light(
            device_id="ac2",
            room="Bedroom",
            name="Bedroom AC"
        )
        self.assertEqual(self.device.status, DEFAULT_LIGHT_STATUS)
        self.assertEqual(self.device.is_dimmable, DEFAULT_DIMMABLE)
        self.assertEqual(self.device.brightness, DEFAULT_BRIGHTNESS)
        self.assertEqual(self.device.dynamic_color, DEFAULT_DYNAMIC_COLOR)
        self.assertEqual(self.device.color, DEFAULT_COLOR)

    def test_initialization_valid(self):
        self.assertEqual(self.device.status, "on")
        self.assertEqual(self.device.is_dimmable, True)
        self.assertEqual(self.device.brightness,
                         MIN_BRIGHTNESS if MIN_BRIGHTNESS != DEFAULT_BRIGHTNESS else MIN_BRIGHTNESS + 1)
        self.assertEqual(self.device.dynamic_color, True)
        self.assertEqual(self.device.color, "#123456")

    def test_initialization_invalid_brightness_raises(self):
        with self.assertRaises(ValueError):
            Light("ac2", "Bedroom", "AC2", brightness=MIN_BRIGHTNESS - 1)
        with self.assertRaises(ValueError):
            Light("ac2", "Bedroom", "AC2", brightness=MAX_BRIGHTNESS + 1)

    def test_initialization_invalid_color_raises(self):
        with self.assertRaises(ValueError):
            Light("ac2", "Bedroom", "AC2", color="123456")
        with self.assertRaises(ValueError):
            Light("ac2", "Bedroom", "AC2", color="#1234")

    # 2. Property setter tests
    def test_brightness_setter_valid(self):
        self.device.brightness = MIN_BRIGHTNESS
        self.assertEqual(self.device.brightness, MIN_BRIGHTNESS)

    def test_brightness_setter_invalid(self):
        with self.assertRaises(ValueError):
            self.device.brightness = MAX_BRIGHTNESS + 1
        with self.assertRaises(ValueError):
            self.device.brightness = MIN_BRIGHTNESS - 1

    def test_color_setter_valid(self):
        self.device.color = "#234567"
        self.assertEqual(self.device.color, "#234567")

    def test_color_setter_invalid(self):
        with self.assertRaises(ValueError):
            self.device.color = "123456"
        with self.assertRaises(ValueError):
            self.device.color = "#23456"

    # 3. update_parameters
    def test_update_parameters_all_valid(self):
        params = {
            "brightness": (MIN_BRIGHTNESS + MAX_BRIGHTNESS) // 2,
            "color": "#654321"
        }
        self.device.update_parameters(params)
        self.assertEqual(self.device.brightness, (MIN_BRIGHTNESS + MAX_BRIGHTNESS) // 2)
        self.assertEqual(self.device.color, "#654321")

    def test_update_parameters_invalid_brightness_raises(self):
        with self.assertRaises(ValueError):
            self.device.update_parameters({"brightness": MAX_BRIGHTNESS + 1})
        with self.assertRaises(ValueError):
            self.device.update_parameters({"brightness": MIN_BRIGHTNESS - 1})

    def test_update_parameters_invalid_color_raises(self):
        with self.assertRaises(ValueError):
            self.device.update_parameters({"color": "123456"})
        with self.assertRaises(ValueError):
            self.device.update_parameters({"color": "#23456"})

    # 4. tick behavior (mocking randomness and publish)
    @patch("devices.air_conditioner.random.random")
    @patch("devices.air_conditioner.random.choice")
    @patch.object(Light, 'publish_mqtt')
    def test_tick_changes_status(self, mock_publish, mock_choice, mock_random):
        mock_random.return_value = 0.0  # force change
        mock_choice.return_value = 'status'
        self.device.tick()
        self.assertEqual(self.device.status, 'off')
        mock_publish.assert_called_once()

    @patch("devices.air_conditioner.random.random")
    @patch("devices.air_conditioner.random.choice")
    @patch.object(Light, 'publish_mqtt')
    def test_tick_changes_brightness(self, mock_publish, mock_choice, mock_random):
        mock_random.return_value = 0.0
        mock_choice.side_effect = ['brightness']
        with patch("devices.light.random.randint",
                   return_value=MIN_BRIGHTNESS if self.device.brightness != MIN_BRIGHTNESS else MIN_BRIGHTNESS + 1):
            original = self.device.brightness
            self.device.tick()
        self.assertNotEqual(self.device.brightness, original)
        mock_publish.assert_called_once()

    @patch("devices.air_conditioner.random.random")
    @patch("devices.air_conditioner.random.choice")
    @patch.object(Light, 'publish_mqtt')
    def test_tick_changes_color(self, mock_publish, mock_choice, mock_random):
        mock_random.return_value = 0.0
        mock_choice.side_effect = ['color']
        with patch("devices.light.random.randrange",
                   return_value=1):
            self.device.tick()
        self.assertEqual(self.device.color, "#000001")
        mock_publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
