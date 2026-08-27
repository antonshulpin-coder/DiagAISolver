import unittest
from unittest.mock import patch, call

from src.router import route


class TestRoute(unittest.TestCase):

    @patch("src.router.learn")
    def test_route_1_calls_learn(self, mock_learn):
        result = route("1")
        mock_learn.assert_called_once()
        self.assertTrue(result)

    @patch("src.router.solve_flow")
    def test_route_2_calls_solve_flow(self, mock_solve_flow):
        result = route("2")
        mock_solve_flow.assert_called_once()
        self.assertTrue(result)

    @patch("src.router.build")
    def test_route_3_calls_build(self, mock_build):
        result = route("3")
        mock_build.assert_called_once()
        self.assertTrue(result)

    @patch("src.router.knowledge")
    def test_route_4_calls_knowledge(self, mock_knowledge):
        result = route("4")
        mock_knowledge.assert_called_once()
        self.assertTrue(result)

    def test_route_0_returns_false(self):
        result = route("0")
        self.assertFalse(result)

    def test_route_invalid_returns_true(self):
        result = route("999")
        self.assertTrue(result)

    def test_route_empty_string_returns_true(self):
        result = route("")
        self.assertTrue(result)


if __name__ == "__main__":
    unittest.main()
