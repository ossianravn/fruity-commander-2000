"""Real SQLite and local WAV checks for owned-only search and file reuse."""

import hashlib
from pathlib import Path
import sqlite3
import tempfile
import unittest
import soundfile
from scripts.splice_library import SpliceSearch, search_owned, owned_sample
from scripts.splice_download import download


class SpliceLibraryTest(unittest.TestCase):
    def test_owned_cloud_search_literal_tags_and_verified_local_reuse(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            wav = root / "Owned.wav"
            soundfile.write(wav, [.1, -.1], 44100)
            digest = hashlib.sha256(wav.read_bytes()).hexdigest()
            db = root / "sounds.db"
            connection = sqlite3.connect(db)
            connection.executescript("CREATE TABLE packs(uuid TEXT,name TEXT);"
                "CREATE TABLE samples(id INTEGER,filename TEXT,file_hash TEXT,purchased_at INTEGER,"
                "pack_uuid TEXT,audio_key TEXT,chord_type TEXT,bpm REAL,sample_type TEXT,"
                "duration REAL,tags TEXT,local_path TEXT);")
            rows = [(1, "100% kick.wav", "cloud", 1, "p", None, None, 117, "oneshot", 1, "kick,drums", None),
                    (2, "Unowned.wav", "unowned", None, "p", None, None, 117, "oneshot", 1, "kick", None),
                    (3, "Other.wav", "other", 2, "p", None, None, 117, "oneshot", 1, "kickbox", None),
                    (4, "Owned.wav", digest, 3, "p", None, None, 117, "oneshot", 1, "kick", str(wav))]
            connection.executemany("INSERT INTO samples VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", rows)
            connection.commit()
            connection.close()
            result = search_owned(SpliceSearch(tags=["kick"], availability="cloud", database_path=str(db)))
            self.assertEqual([r["file_hash"] for r in result["results"]], ["cloud"])
            result = search_owned(SpliceSearch(query="%", database_path=str(db)))
            self.assertEqual(result["total_matches"], 1)
            with self.assertRaisesRegex(ValueError, "not in this owned"):
                owned_sample("unowned", str(db))
            result = download(digest, database_path=str(db))
            self.assertEqual(result["status"], "available")
            self.assertEqual(result["file"]["path"], str(wav))
            self.assertTrue(result["hash_matches_catalog"])
            self.assertFalse(result["credits_checked"])
