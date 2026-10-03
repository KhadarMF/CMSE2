"""Validate currency input before comparing it with stored balances."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def parse_money(value):
    try:
        amount = Decimal(str(value or 0))
        if not amount.is_finite() or abs(amount) >= Decimal('1000000000000'):
            return 0.0
        rounded = amount.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if abs(rounded) >= Decimal('1000000000000'):
            return 0.0
        return float(rounded)
    except (InvalidOperation, ValueError, TypeError):
        return 0.0
