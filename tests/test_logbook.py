import tempfile, unittest
from pathlib import Path
from datetime import datetime, timezone, timedelta
from models import QSO, Repeater
from validators import validate_callsign, parse_positive, band_for_frequency, validate_qso
from database import Database
from adif_export import adif_record
class LogbookTests(unittest.TestCase):
 def qso(self,**changes):
  values=dict(callsign="yo3abc/p",qso_start_utc="2026-01-01T12:00:00+00:00",qso_end_utc="2026-01-01T12:01:00+00:00",frequency_mhz=145.5,mode="FM")
  values.update(changes);return QSO(**values)
 def test_callsign_normalization(self):self.assertEqual(validate_callsign(" yo3abc/m "),"YO3ABC/M")
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
if __name__ == "__main__":unittest.main()
