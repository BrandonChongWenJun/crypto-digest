import csv
import tempfile
import unittest
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

import digest
from digest import (
    buyback_lines,
    change,
    changes_line,
    fmt_milestone,
    fmt_pct,
    fmt_usd,
    oracle_tvs,
    primary_oracles,
    progress_bar,
    trailing_average,
    tvs_lines,
)

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


class OracleTvsTest(unittest.TestCase):
    def test_primary_oracles(self):
        protocol = {
            "oraclesBreakdown": [
                {"name": "Chainlink", "type": "Primary", "chains": [{"chain": "Ethereum"}]},
                {"name": "Chainlink", "type": "Primary", "chains": [{"chain": "Binance"}]},
                {"name": "RedStone", "type": "Primary"},
                {"name": "Pyth", "type": "Fallback"},
                {"name": "Chronicle", "type": "Aggregator"},
                {"name": "Api3", "type": "Primary", "endDate": "2025-01-01"},
            ]
        }
        self.assertEqual(primary_oracles(protocol), {"Chainlink": {"ethereum", "bsc"}, "RedStone": None})

    def test_all_chains_entry_wins(self):
        protocol = {
            "oraclesBreakdown": [
                {"name": "Chainlink", "type": "Primary"},
                {"name": "Chainlink", "type": "Primary", "chains": [{"chain": "Base"}]},
            ]
        }
        self.assertEqual(primary_oracles(protocol), {"Chainlink": None})

    def test_legacy_oracles_field(self):
        self.assertEqual(primary_oracles({"oracles": ["Pyth"]}), {"Pyth": None})
        self.assertEqual(primary_oracles({}), {})

    def test_tvs_counts_only_the_chains_an_oracle_is_used_on(self):
        def tvl(now, day, week, month):
            return {"tvl": now, "tvlPrevDay": day, "tvlPrevWeek": week, "tvlPrevMonth": month}

        protocols = [
            {
                "id": "1",
                "oraclesBreakdown": [
                    {"name": "Chainlink", "type": "Primary", "chains": [{"chain": "Ethereum"}]},
                    {"name": "Pyth", "type": "Primary", "chains": [{"chain": "solana"}]},
                ],
            },
            {"id": "2", "oracles": ["Chainlink", "Internal"]},
            {"id": "3", "oracles": ["Pyth"]},  # missing from the TVL data
        ]
        lite = [
            {
                "defillamaId": "1",
                **tvl(100, 90, 80, 50),
                "chainTvls": {
                    "Ethereum": tvl(70, 60, 50, 30),
                    "Ethereum-borrowed": tvl(999, 999, 999, 999),
                    "Solana": tvl(30, 30, 30, 20),
                },
            },
            {"defillamaId": "2", **tvl(10, 10, None, 5), "chainTvls": {}},
        ]
        tvs, counts = oracle_tvs(protocols, lite)
        self.assertEqual(tvs, {"Chainlink": {0: 80, 1: 70, 7: 50, 30: 35}, "Pyth": {0: 30, 1: 30, 7: 30, 30: 20}})
        self.assertEqual(counts, {"Chainlink": 2, "Pyth": 1})


class TvsLinesTest(unittest.TestCase):
    def test_lead_share_and_runners_up(self):
        tvs = {
            "Chainlink": {0: 30e9, 1: 30e9, 7: 30e9, 30: 25e9},
            "RedStone": {0: 3e9, 1: 2.9e9, 7: 2.5e9, 30: 2e9},
            "Pyth": {0: 2e9, 1: 2e9, 7: 2e9, 30: 2e9},
            "Api3": {0: 1e9, 1: 1e9, 7: 1e9, 30: 1e9},
            "DIA": {0: 0.5e9, 1: 0.5e9, 7: 0.5e9, 30: 0.5e9},
        }
        lines = tvs_lines(tvs, {"Chainlink": 500, "RedStone": 90}, TODAY)
        self.assertEqual(
            lines,
            [
                "Chainlink TVS: $30.0B · #1 · 500 protocols",
                "  1d +0.0% · 7d +0.0% · 30d +20.0%",
                "Closest rival: RedStone $3.00B · 90 protocols",
                "  1d +3.4% · 7d +20.0% · 30d +50.0%",
                "Lead: 10.0x (30d ago 12.5x)",
                "Share of all oracle TVS: 82% (30d ago 82%)",
                "Next: Pyth $2.00B · Api3 $1.00B",
            ],
        )

    def test_alerts_when_the_order_changes(self):
        tvs = {
            "Chainlink": {0: 10e9, 1: 12e9, 7: 12e9, 30: 12e9},
            "RedStone": {0: 11e9, 1: 9e9, 7: 9e9, 30: 9e9},
            "Pyth": {0: 1e9, 1: 10e9, 7: 10e9, 30: 10e9},
        }
        lines = tvs_lines(tvs, Counter(), TODAY)
        self.assertEqual(lines[0], "🚨 RedStone has passed Chainlink as the #1 oracle by TVS")
        self.assertEqual(lines[1], "⚠️ RedStone passed Pyth as the closest rival")
        self.assertEqual(lines[2], "Chainlink TVS: $10.0B · #2 · 0 protocols")


class LinkReserveTest(unittest.TestCase):
    def test_encode_aggregate(self):
        word = digest.abi_word
        target = "0x00000000000000000000000000000000000000aa"
        expected = "0x252dba42" + word(32) + word(1) + word(32) + word(0xAA) + word(64) + word(4) + "50d25bcd" + "0" * 56
        self.assertEqual(digest.encode_aggregate([(target, "0x50d25bcd")]), expected)

    def test_decode_aggregate(self):
        word = digest.abi_word
        # (uint256 block, bytes[] results) with two 32-byte results
        result = "0x" + word(123) + word(64) + word(2) + word(64) + word(128) + word(32) + word(7) + word(32) + word(10**18)
        self.assertEqual(digest.decode_aggregate(result), [7, 10**18])

    def test_reserve_lines(self):
        history = {0: (6.29e6, 766.85e6), 90: (4.94e6, 748.1e6), 365: (0.52e6, 696.85e6)}
        self.assertEqual(
            digest.reserve_lines(12.37, history),
            [
                "Reserve: 6.29M LINK ($77.8M)",
                "  90d +1.35M · 365d +5.77M",
                "Unlocked by Chainlink:",
                "  90d 18.8M · 365d 70.0M",
                "Reserve buys vs unlocks: 7% (90d) · 8% (365d)",
            ],
        )

    def test_reserve_lines_without_past_data(self):
        lines = digest.reserve_lines(12.37, {0: (6.29e6, 766.85e6), 365: (0.52e6, 766.85e6)})
        self.assertEqual(lines[1:], ["  365d +5.77M", "Unlocked by Chainlink:", "  365d 0.00M"])
        lines = digest.reserve_lines(12.37, {0: (6.29e6, 766.85e6)})
        self.assertEqual(lines[1:], ["Reserve buys vs unlocks: unavailable"])


class AeroTest(unittest.TestCase):
    def test_parent_volumes_groups_versions(self):
        protocols = [
            {"name": "Aerodrome Slipstream", "parentProtocol": "parent#aero-protocol", "total30d": 10, "total60dto30d": 8},
            {"name": "Aerodrome V1", "parentProtocol": "parent#aero-protocol", "total30d": 2, "total60dto30d": None},
            {"name": "Tessera V", "total30d": 1, "total60dto30d": 1},
        ]
        self.assertEqual(digest.parent_volumes(protocols), {"parent#aero-protocol": (12, 8), "Tessera V": (1, 1)})

    def test_group_name(self):
        self.assertEqual(digest.group_name("parent#aero-protocol"), "Aero")
        self.assertEqual(digest.group_name("parent#curve-finance"), "Curve Finance")
        self.assertEqual(digest.group_name("parent#1inch"), "1inch")
        self.assertEqual(digest.group_name("Tessera V"), "Tessera V")

    def test_aero_lines(self):
        chains = {
            "Ethereum": {"parent#uniswap": (60e9, 60e9), "parent#fluid": (40e9, 40e9)},
            "Base": {"parent#aero-protocol": (15e9, 10e9), "parent#uniswap": (10e9, 10e9), "Tessera V": (5e9, 5e9)},
        }
        revenue = [0.1e6] * 30 + [0.2e6] * 30
        self.assertEqual(
            digest.aero_lines(chains, revenue, 600e6),
            [
                "Volume 30d: $15.0B (+50.0% vs prior 30d)",
                "Revenue to sAERO stakers 30d: $6.0M (+100.0% vs prior 30d)",
                "  0.040% of volume (prior 30d 0.030%)",
                "  Annualized $73.0M = 12.2% of AERO market cap ($600.0M)",
                "DEX volume share, 30d (prior 30d):",
                "  All 2 chains $130.0B: Aero 12% (8.0%) · Uniswap 54% (56%)",
                "  Ethereum $100.0B: Aero 0.0% (0.0%) · Uniswap 60% (60%)",
                "  Base $30.0B: Aero 50% (40%) · Uniswap 33% (40%)",
            ],
        )

    def test_aero_lines_without_market_cap_or_history(self):
        lines = digest.aero_lines({"Base": {"parent#aero-protocol": (1e9, 0)}}, [1e6] * 10, None)
        self.assertEqual(lines[:2], ["Volume 30d: $1.00B", "Revenue to sAERO stakers 30d: $10.0M"])
        self.assertEqual(lines[-1], "  Base $1.00B: Aero 100% (0.0%)")


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
