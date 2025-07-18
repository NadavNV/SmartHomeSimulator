import unittest
from unittest.mock import patch, MagicMock
from devices.curtain import Curtain, MIN_POSITION, MAX_POSITION, DEFAULT_POSITION, DEFAULT_CURTAIN_STATUS, POSITION_RATE


class TestCurtain(unittest.TestCase):

    def setUp(self):
        self.mock_logger = MagicMock()
        self.device_logger_patcher = patch('devices.device.logging.getLogger', return_value=self.mock_logger)
        self.device_logger_patcher.start()

        self.device = Curtain(
            device_id="curtain1",
            room="Living Room",
            name="Main Curtain",
            status="closed",
            position=(MIN_POSITION + MAX_POSITION) // 2,
        )

    def tearDown(self):
        self.device_logger_patcher.stop()

    # 1. Initialization tests
    def test_initialization_default(self):
        self.device = Curtain(
            device_id="curtain2",
            room="Bedroom",
            name="Bedroom Curtain"
        )
        self.assertEqual(self.device.status, DEFAULT_CURTAIN_STATUS)
        self.assertEqual(self.device.position, DEFAULT_POSITION)

    def test_initialization_valid(self):
        self.assertEqual(self.device.status, "closed")
        self.assertEqual(self.device.position, (MIN_POSITION + MAX_POSITION) // 2)

    def test_initialization_invalid_position_raises(self):
        with self.assertRaises(ValueError):
            Curtain("ac2", "Bedroom", "AC2", position=MAX_POSITION + 1)

    # 2. Property setter tests
    def test_position_setter(self):
        self.device.position = MAX_POSITION - 1
        self.assertEqual(self.device.position, MAX_POSITION - 1)

    # 3. tick behavior (mocking randomness and publish)
    @patch("devices.air_conditioner.random.random")
    @patch.object(Curtain, 'publish_mqtt')
    def test_tick_changes_status(self, mock_publish, mock_random):
        mock_random.return_value = 0.0  # force change
        self.device.tick()
        self.assertEqual(self.device.position, (MIN_POSITION + MAX_POSITION) // 2 + POSITION_RATE)
        self.assertEqual(self.device.status, 'open')
        mock_publish.assert_called_once()


if __name__ == "__main__":
    unittest.main()
