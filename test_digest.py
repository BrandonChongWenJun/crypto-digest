import csv
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import digest
from digest import buyback_lines, change, changes_line, fmt_milestone, fmt_pct, fmt_usd, progress_bar, trailing_average

TODAY = date(2026, 10, 19)


def daily(values, end=TODAY):
    """A daily series ending on `end`."""
    start = end - timedelta(days=len(values) - 1)
    return [(start + timedelta(days=i), v) for i, v in enumerate(values)]


class FormattingTest(unittest.TestCase):
    def test_usd(self):
        self.assertEqual(fmt_usd(4.6832e9), "$4.68B")
        self.assertEqual(fmt_usd(306.4e9), "$306.4B")
        self.assertEqual(fmt_usd(22.5e6), "$22.5M")
        self.assertEqual(fmt_milestone(7.5e9), "$7.5B")
        self.assertEqual(fmt_milestone(10e9), "$10B")

    def test_pct(self):
        self.assertEqual(fmt_pct(0.016), "+1.6%")
        self.assertEqual(fmt_pct(-0.026), "−2.6%")
        self.assertEqual(fmt_pct(0.566, 0), "+57%")
        self.assertEqual(fmt_pct(None), "n/a")

    def test_progress_bar(self):
        self.assertEqual(progress_bar(0.639), "▓▓▓▓▓▓░░░░")
        self.assertEqual(progress_bar(0), "░" * 10)
        self.assertEqual(progress_bar(1.5), "▓" * 10)


class SeriesTest(unittest.TestCase):
    def test_change_uses_value_on_or_before(self):
        series = daily([100, 110, 120])
        self.assertAlmostEqual(change(series, 1), 120 / 110 - 1)
        self.assertAlmostEqual(change(series, 2), 0.2)
        self.assertIsNone(change(series, 5))  # no data that far back

    def test_change_skips_missing_day(self):
        series = [(TODAY - timedelta(days=9), 100), (TODAY, 150)]
        self.assertAlmostEqual(change(series, 7), 0.5)

    def test_changes_line(self):
        self.assertEqual(changes_line(daily([100, 110]), spans=(1,)), "1d +10.0%")

    def test_trailing_average(self):
        series = daily([1, 2, 3, 4, 5])
        self.assertEqual(trailing_average(series, 2), 4.5)
        self.assertEqual(trailing_average(series, 2, end_offset=1), 3.5)
        self.assertEqual(trailing_average(series, 10), 3)


class BuybackLinesTest(unittest.TestCase):
    def test_below_first_milestone_and_shrinking(self):
        lines = buyback_lines(4.79e9, 4.80e9, 4.85e9, TODAY)
        self.assertEqual(lines[0], "🎯 ENA buybacks start at a $7.5B 14-day avg (5% of revenue)")
        self.assertEqual(lines[1], "▓▓▓▓▓▓░░░░ 64%, needs +$2.71B (+57%)")
        self.assertEqual(lines[2], "ETA: none, the 14-day avg hasn't grown over the last 30 days")

    def test_growing_trend_gives_eta(self):
        # +$0.6B in 30 days = $20M/day; $2.5B to go = 125 days, about 4 months.
        lines = buyback_lines(5.0e9, 4.98e9, 4.4e9, TODAY)
        self.assertEqual(lines[-1], "ETA at the last 30 days' pace: ~4 months (≈ Feb 2027)")

    def test_slow_trend_is_years_away(self):
        lines = buyback_lines(5.0e9, 5.0e9, 4.99e9, TODAY)
        self.assertEqual(lines[-1], "ETA at the last 30 days' pace: 3+ years")

    def test_crossing_up(self):
        lines = buyback_lines(7.6e9, 7.4e9, 6e9, TODAY)
        self.assertEqual(lines[0], "🚨 14-day avg just crossed $7.5B: buybacks now 5% of revenue")
        self.assertEqual(lines[1], "🎯 ENA buybacks: 5% of revenue (14-day avg ≥ $7.5B)")
        self.assertEqual(lines[2], "Next: 10% at $10B")

    def test_crossing_down(self):
        lines = buyback_lines(7.4e9, 7.6e9, 8e9, TODAY)
        self.assertEqual(lines[0], "⚠️ 14-day avg fell below $7.5B: buybacks now off")

    def test_dropping_a_tier(self):
        lines = buyback_lines(9.9e9, 10.1e9, 10e9, TODAY)
        self.assertEqual(lines[0], "⚠️ 14-day avg fell below $10B: buybacks now 5% of revenue")

    def test_top_milestone(self):
        lines = buyback_lines(26e9, 26e9, 25e9, TODAY)
        self.assertEqual(lines, ["🎯 ENA buybacks: 25% of revenue (14-day avg ≥ $25B)", "Top buyback milestone reached."])


class BuildDigestTest(unittest.TestCase):
    def test_failed_section_does_not_block_others(self):
        def broken(today):
            raise OSError("boom <html>")

        def working(today):
            return ["ok"], {"defi_tvl": 1.0}

        with mock.patch.object(digest, "SECTIONS", [("Broken", broken), ("Working", working)]):
            text, snapshot = digest.build_digest(digest.datetime(2026, 10, 19, 9, tzinfo=digest.SGT))
        self.assertIn("<b>Broken</b>\nunavailable (boom &lt;html&gt;)", text)
        self.assertIn("<b>Working</b>\nok", text)
        self.assertEqual(snapshot, {"defi_tvl": 1.0})


class SnapshotTest(unittest.TestCase):
    def test_replaces_same_day_and_keeps_others(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data" / "history.csv"
            with mock.patch.object(digest, "HISTORY_FILE", path):
                digest.save_snapshot(TODAY - timedelta(days=1), {"usde_supply": 4.7e9})
                digest.save_snapshot(TODAY, {"usde_supply": 4.6e9, "susde_yield_30d": 4.8012})
                digest.save_snapshot(TODAY, {"usde_supply": 4.68e9, "susde_yield_30d": 4.8})
            with path.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        self.assertEqual([r["date"] for r in rows], ["2026-10-18", "2026-10-19"])
        self.assertEqual(rows[1]["usde_supply"], "4680000000")
        self.assertEqual(rows[1]["susde_yield_30d"], "4.8000")
        self.assertEqual(rows[0]["susde_yield_30d"], "")


if __name__ == "__main__":
    unittest.main()
