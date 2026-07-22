"""Headless tests for NOAA parsing/cache and locally generated map images."""
import tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock
from propagation_models import PropagationMapRequest, SpaceWeatherData
from services.propagation_cache import PropagationCache
from services.propagation_map_service import PropagationMapService, evaluate_band_conditions
from services.space_weather_service import SpaceWeatherError, SpaceWeatherService

class WeatherTests(unittest.TestCase):
 def test_noaa_values_are_parsed_from_mocked_json(self):
  with tempfile.TemporaryDirectory() as d:
   service=SpaceWeatherService(PropagationCache(Path(d)))
   payloads=[ [{"kp_index":"3.3"}], [{"flux":"155","sunspot_number":"88"}], [{"a_index":"12"}], [{"message":"R2 RADIO BLACKOUT"}] ]
   service._get=Mock(side_effect=payloads)
   value=service.fetch()
   self.assertEqual((value.kp_index,value.solar_flux,value.a_index,value.sunspot_number,value.radio_blackout_level),(3.3,155.,12.,88.,"R2"))
 def test_failure_does_not_create_fake_values(self):
  with tempfile.TemporaryDirectory() as d:
   service=SpaceWeatherService(PropagationCache(Path(d)));service._get=Mock(side_effect=SpaceWeatherError("timeout"))
   with self.assertRaises(SpaceWeatherError):service.fetch()

class MapTests(unittest.TestCase):
 def setUp(self):self.weather=SpaceWeatherData(2,8,150,None,None,"fixture",datetime.now(timezone.utc),datetime.now(timezone.utc))
 def test_hf_and_vhf_pngs_are_generated_headlessly(self):
  with tempfile.TemporaryDirectory() as d:
   renderer=PropagationMapService(PropagationCache(Path(d)))
   for band in ("20m","2m","70cm"):
    request=PropagationMapRequest(45,25,"KN35",band,None,None,50,datetime.now(timezone.utc)); result=renderer.generate(request,self.weather)
    self.assertTrue(Path(result.image_path).exists());self.assertTrue(Path(result.image_path).read_bytes().startswith(b"\x89PNG"))
 def test_band_algorithms_warn_as_expected(self):
  self.assertIn("Sporadic", " ".join(evaluate_band_conditions("6m",self.weather,datetime.now(timezone.utc),0,0).warnings))
  self.assertIn("line-of-sight", " ".join(evaluate_band_conditions("2m",self.weather,datetime.now(timezone.utc),0,0).warnings))
 def test_cache_key_is_stable(self):
  self.assertEqual(PropagationCache.key({"band":"20m"}),PropagationCache.key({"band":"20m"}))
  self.assertNotEqual(PropagationCache.key({"band":"20m"}),PropagationCache.key({"band":"40m"}))
if __name__ == '__main__':unittest.main()
