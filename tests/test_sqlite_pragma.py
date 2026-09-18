import unittest
from unittest.mock import call, patch

from backend.core.config_manager import _get_conn


class SqlitePragmaTest(unittest.TestCase):
    @patch('backend.core.config_manager.sqlite3.connect')
    def test_sqlite_pragmas(self, mock_connect):
        mock_conn = mock_connect.return_value
        _get_conn()
        
        mock_conn.execute.assert_has_calls([
            call("PRAGMA journal_mode=WAL;"),
            call("PRAGMA synchronous=NORMAL;"),
            call("PRAGMA busy_timeout=5000;")
        ], any_order=True)

if __name__ == '__main__':
    unittest.main()
