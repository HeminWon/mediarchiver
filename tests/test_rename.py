import unittest

import os

from src.rename.rename import live_photo_match_image

class TestCal(unittest.TestCase):
    def test_init(self):
        print(os.path)


    def test_live_photo_match_image(self):
        file_image = live_photo_match_image('~/nas/', "1011")
        print(file_image)
        self.assertIsNotNone(file_image)