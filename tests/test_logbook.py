import tempfile, unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from models import OperatorProfile, QSO, Repeater
from validators import (band_for_frequency, format_name_input, normalize_callsign,
                        normalize_name, parse_positive, validate_callsign, validate_qso)
from database import Database
from adif_export import adif_record
from utils.maidenhead import coordinates_to_maidenhead, maidenhead_to_coordinates
from services.location_service import LocationService, LocationUnavailableError, LocationTimeoutError
class LogbookTests(unittest.TestCase):
 def qso(self,**changes):
  values=dict(callsign="yo3abc/p",qso_start_utc="2026-01-01T12:00:00+00:00",qso_end_utc="2026-01-01T12:01:00+00:00",frequency_mhz=145.5,mode="FM")
  values.update(changes);return QSO(**values)
 def test_callsign_normalization(self):self.assertEqual(validate_callsign(" yo3abc/m "),"YO3ABC/M")
 def test_live_callsign_formatting(self):self.assertEqual(normalize_callsign("yo8abc/p"),"YO8ABC/P")
 def test_name_formatting(self):
  self.assertEqual(normalize_name("  iON   popescu "),"Ion Popescu")
  self.assertEqual(format_name_input("mihai  "),"Mihai ")
 def test_invalid_frequency(self):
  with self.assertRaises(ValueError):parse_positive("0","Frecvența")
 def test_bands(self):self.assertEqual(band_for_frequency(145.5),"2m");self.assertEqual(band_for_frequency(999),"Unknown")
 def test_time_interval(self):
  with self.assertRaises(ValueError):validate_qso(self.qso(qso_end_utc="2026-01-01T11:00:00+00:00"))
 def test_adif_byte_lengths(self):
  record=adif_record(validate_qso(self.qso(notes="ș")));self.assertIn("<COMMENT:2>ș",record);self.assertIn("<EOR>",record)
 def test_crud_and_duplicate(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Database(Path(tmp)/"test.db");q=validate_qso(self.qso());ident=db.save_qso(q);self.assertEqual(db.get_qso(ident).callsign,"YO3ABC/P");self.assertTrue(db.possible_duplicate(q));q.id=ident;q.notes="edited";db.save_qso(q);self.assertEqual(db.get_qso(ident).notes,"edited");r=Repeater("R0",145.6);rid=db.save_repeater(r);q.repeater_id=rid;db.save_qso(q);db.delete_repeater(rid);self.assertIsNone(db.get_qso(ident).repeater_id);db.delete_qso(ident);self.assertEqual(db.list_qsos(),[])
 def test_operator_profile_save_and_load(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Database(Path(tmp)/"test.db");profile=OperatorProfile(callsign="YO3ABC",full_name="Ion Popescu",default_power_w=25.0,radio_club="Radio Club")
   db.save_operator_profile(profile);loaded=db.get_operator_profile();self.assertEqual(loaded.callsign,"YO3ABC");self.assertEqual(loaded.full_name,"Ion Popescu");self.assertEqual(loaded.default_power_w,25.0)
 def test_profile_location_save_and_load(self):
  with tempfile.TemporaryDirectory() as tmp:
   db=Database(Path(tmp)/"test.db"); db.save_operator_profile(OperatorProfile(latitude=44.4268,longitude=26.1025,location_accuracy_m=20,location_source="Windows Location",location_updated_at="2026-01-01T00:00:00+00:00",grid_square="KN34BK")); p=db.get_operator_profile(); self.assertEqual((p.latitude,p.longitude,p.grid_square),(44.4268,26.1025,"KN34BK"))
 def test_existing_database_migration(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/"old.db"; import sqlite3
   c=sqlite3.connect(path); c.execute("CREATE TABLE operator_profile (id INTEGER PRIMARY KEY, callsign TEXT)"); c.execute("INSERT INTO operator_profile VALUES (1,'YO3OLD')"); c.commit(); c.close()
   db=Database(path); self.assertEqual(db.get_operator_profile().callsign,"YO3OLD")
   with db.connect() as c:self.assertIn("latitude",[r["name"] for r in c.execute("PRAGMA table_info(operator_profile)")])
 def test_maidenhead_precisions_and_hemispheres(self):
  self.assertEqual(coordinates_to_maidenhead(44.4268,26.1025,4),"KN34")
  self.assertEqual(coordinates_to_maidenhead(44.4268,26.1025,6),"KN34bk")
  self.assertEqual(coordinates_to_maidenhead(44.4268,26.1025,8),"KN34bk22")
  self.assertEqual(coordinates_to_maidenhead(0,0),"JJ00aa")
  self.assertEqual(coordinates_to_maidenhead(-33.8688,-151.2093),"BF46jd")
 def test_maidenhead_limits_invalid_and_inverse(self):
  for lat,lon in ((90,180),(-90,-180),(90,-180),(-90,180)): self.assertEqual(len(coordinates_to_maidenhead(lat,lon)),6)
  for lat,lon in ((91,0),(-91,0),(0,181),(0,-181)):
   with self.assertRaises(ValueError): coordinates_to_maidenhead(lat,lon)
  lat,lon=maidenhead_to_coordinates("KN34bk");self.assertAlmostEqual(lat,44.4375);self.assertAlmostEqual(lon,26.125)
  with self.assertRaises(ValueError): maidenhead_to_coordinates("ZZ99zz")
 def test_location_service_unsupported_and_timeout(self):
  import unittest.mock as mock
  with mock.patch("services.location_service.sys.platform","linux"):
   with self.assertRaises(LocationUnavailableError): LocationService().locate()
  with mock.patch("services.location_service.sys.platform","win32"),mock.patch("services.location_service.subprocess.run",side_effect=__import__('subprocess').TimeoutExpired("powershell",12)):
   with self.assertRaises(LocationTimeoutError): LocationService().locate()
if __name__ == "__main__":unittest.main()
