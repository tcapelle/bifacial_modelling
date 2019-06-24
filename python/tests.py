#test files
import unittest
from pathlib import Path

from utils import *
from parallel_run import *

PATH = Path('../data_Comparison_Static-Tracking_for_Kais')
tmy_file = PATH/'Cadarache.csv'


class TestParallelRun(unittest.TestCase):
    def test_run(self):
        return

class Test_read_pvgis(unittest.TestCase):
    def my_file(self):
        gps_data, months_year, weather = read_pvgis(tmy_file, 2018)
        assert len(months_year)==12, "TMY file wrong, please use a TMY file from PVGis"
        return