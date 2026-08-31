from __future__ import annotations

import argparse
import calendar
from datetime import date

from licensing import activation_code_for, format_activation_code


def add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    day = min(start.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a VIVU STUDIO activation code.")
    parser.add_argument("request_id", help="Request ID copied from the customer's app")
    parser.add_argument(
        "--duration",
        required=True,
        choices=("1m", "3m", "1y"),
        help="License duration: 1 month, 3 months, or 1 year",
    )
    args = parser.parse_args()
    try:
        months = {"1m": 1, "3m": 3, "1y": 12}[args.duration]
        expires_on = add_months(date.today(), months)
        code = activation_code_for(args.request_id, expires_on)
        print(f"Activation code: {format_activation_code(code)}")
        print(f"Expires on:      {expires_on.strftime('%d/%m/%Y')}")
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
