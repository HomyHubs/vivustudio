import json
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

from licensing import (
    activation_code_for,
    activation_expiry,
    format_activation_code,
    is_activated,
    is_valid_activation_code,
    save_activation,
)


class LicensingTests(unittest.TestCase):
    REQUEST_ID = "0123-4567-89AB-CDEF-0123"

    def test_code_is_16_digits_and_bound_to_request(self):
        expiry = date(2030, 12, 31)
        code = activation_code_for(self.REQUEST_ID, expiry)
        self.assertRegex(code, r"^\d{16}$")
        self.assertEqual(activation_expiry(code), expiry)
        self.assertTrue(is_valid_activation_code(self.REQUEST_ID, format_activation_code(code), date(2030, 1, 1)))
        self.assertFalse(is_valid_activation_code("FFFF-4567-89AB-CDEF-0123", code, date(2030, 1, 1)))

    def test_expired_code_is_rejected(self):
        code = activation_code_for(self.REQUEST_ID, date(2029, 1, 31))
        self.assertTrue(is_valid_activation_code(self.REQUEST_ID, code, date(2029, 1, 31)))
        self.assertFalse(is_valid_activation_code(self.REQUEST_ID, code, date(2029, 2, 1)))

    def test_activation_is_saved_and_rechecked(self):
        data_dir = MagicMock(spec=Path)
        destination = MagicMock(spec=Path)
        temporary = MagicMock(spec=Path)
        destination.with_suffix.return_value = temporary
        code = activation_code_for(self.REQUEST_ID, date(2099, 12, 31))
        with patch("licensing.license_path", return_value=destination), patch("licensing.os.replace"):
            save_activation(data_dir, self.REQUEST_ID, code)
            temporary.write_text.assert_called_once()
            destination.read_text.return_value = json.dumps(
                {"request_id": self.REQUEST_ID, "activation_code": code}
            )
            self.assertTrue(is_activated(data_dir, self.REQUEST_ID))
            self.assertFalse(is_activated(data_dir, "FFFF-4567-89AB-CDEF-0123"))


if __name__ == "__main__":
    unittest.main()
