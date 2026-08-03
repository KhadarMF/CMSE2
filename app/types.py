"""Phase 20D - exact numeric column types.

Money used to be stored as db.Float. Floats cannot represent 0.01 exactly,
so repeated addition drifts: a trial balance that should be 0.00 comes out
as 0.0000000001, and after enough rows that becomes a visible cent that
nobody can trace.

These types store an exact DECIMAL in the database (so SQL SUM() is exact
and Postgres rounds correctly) but hand plain floats back to Python. That
keeps every bit of existing arithmetic in routes, services and templates
working unchanged - this is a retrofit, not a rewrite.

Rounding is ROUND_HALF_UP on the way in, which is what accountants expect;
Python's native round() is banker's rounding and would surprise the Finance
Officer on .005 amounts.
"""
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import Numeric
from sqlalchemy.types import TypeDecorator


class _ExactNumeric(TypeDecorator):
    impl = Numeric
    cache_ok = True

    precision = 14
    scale = 2

    def __init__(self, precision=None, scale=None, **kwargs):
        # precision/scale are accepted (Alembic autogenerate passes them back
        # in) but the class constants always win, so a column cannot silently
        # be created with the wrong scale.
        kwargs.pop("asdecimal", None)
        super().__init__(precision=self.precision, scale=self.scale,
                         asdecimal=True, **kwargs)

    @property
    def _quantum(self):
        return Decimal(1).scaleb(-self.scale)

    def process_bind_param(self, value, dialect):
        if value is None or value == "":
            return None
        try:
            dec = Decimal(str(value))
        except Exception:
            return None
        return dec.quantize(self._quantum, rounding=ROUND_HALF_UP)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return float(value)


class Money(_ExactNumeric):
    """Currency amounts. NUMERIC(14,2) - up to 999,999,999,999.99."""
    precision = 14
    scale = 2


class Quantity(_ExactNumeric):
    """Physical quantities and work days. NUMERIC(14,3)."""
    precision = 14
    scale = 3


class Rate(_ExactNumeric):
    """Exchange rates. NUMERIC(18,6) - SLSH per USD needs the headroom."""
    precision = 18
    scale = 6
