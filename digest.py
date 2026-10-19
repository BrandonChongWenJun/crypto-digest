"""Daily crypto digest on Telegram.

Sends one Telegram message a day with:
- Ethena: USDe supply and its progress toward the ENA buyback milestones,
  sUSDe yield, and how much USDe is staked.
- Whole market: total stablecoin supply and DeFi TVL, as adoption signals.

Meant to run once a day from GitHub Actions. Uses only the standard library.

  python digest.py              fetch, record today's snapshot, and send
  python digest.py --dry-run    print the message instead of sending it
  python digest.py --find-chat  show the chat ID of whoever messaged the bot
"""

import csv
import html
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"
HISTORY_FILE = BASE_DIR / "data" / "history.csv"

SGT = timezone(timedelta(hours=8))
USER_AGENT = "Mozilla/5.0 (compatible; crypto-digest/1.0)"

USDE_CHART_URL = "https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=146"
ALL_STABLECOINS_CHART_URL = "https://stablecoins.llama.fi/stablecoincharts/all"
DEFI_TVL_URL = "https://api.llama.fi/v2/historicalChainTvl"
ETHENA_YIELD_URL = "https://ethena.fi/api/yields/protocol-and-staking-yield"
ETH_RPC_URLS = ["https://ethereum-rpc.publicnode.com", "https://eth.drpc.org"]
SUSDE_ADDRESS = "0x9D39A5DE30e57443BfF2A8307A4256c8797A3497"
TOTAL_ASSETS_SELECTOR = "0x01e1d114"  # ERC-4626 totalAssets()

# ENA buyback milestones approved in Sep 2026
# (https://gov.ethenafoundation.com/t/ena-fee-switch-activation/830):
# (USDe supply, % of protocol revenue used to buy back ENA). The vote doesn't
# define how supply is measured; the Risk Committee recommends a 14-day average.
BUYBACK_MILESTONES = [(7.5e9, 5), (10e9, 10), (15e9, 15), (20e9, 20), (25e9, 25)]
AVG_DAYS = 14
TREND_DAYS = 30

SNAPSHOT_FIELDS = [
    "date",
    "usde_supply",
    "usde_avg14",
    "susde_yield_30d",
    "susde_staked",
    "stablecoins_total",
    "defi_tvl",
]


def log(message):
    print(message, file=sys.stderr)


# --- Formatting and series math (unit tested) ---------------------------------


def fmt_usd(value):
    if value >= 10e9:
        return f"${value / 1e9:.1f}B"
    if value >= 1e9:
        return f"${value / 1e9:.2f}B"
    return f"${value / 1e6:.1f}M"


def fmt_milestone(value):
    return f"${value / 1e9:g}B"


def fmt_pct(fraction, decimals=1):
    if fraction is None:
        return "n/a"
    sign = "+" if fraction >= 0 else "−"
    return f"{sign}{abs(fraction) * 100:.{decimals}f}%"


def progress_bar(fraction, width=10):
    filled = max(0, min(width, int(fraction * width)))
    return "▓" * filled + "░" * (width - filled)


def value_on_or_before(series, day):
    for d, value in reversed(series):
        if d <= day:
            return value
    return None


def change(series, days):
    """Fractional change of the latest value versus `days` days earlier."""
    latest_day, latest = series[-1]
    old = value_on_or_before(series, latest_day - timedelta(days=days))
    return latest / old - 1 if old else None


def changes_line(series, spans=(1, 7, 30)):
    return " · ".join(f"{days}d {fmt_pct(change(series, days))}" for days in spans)


def trailing_average(series, days, end_offset=0):
    """Average of the `days` daily points ending `end_offset` points before the latest."""
    end = len(series) - end_offset
    window = [value for _, value in series[max(0, end - days) : end]]
    return sum(window) / len(window) if window else None


def buyback_tier(avg):
    """The highest (supply, take %) milestone reached, or None."""
    reached = [m for m in BUYBACK_MILESTONES if avg >= m[0]]
    return reached[-1] if reached else None


def buyback_lines(avg_now, avg_prev, avg_month_ago, today):
    tier = buyback_tier(avg_now)
    lines = []
    if avg_prev is not None:
        prev_tier = buyback_tier(avg_prev)
        if tier != prev_tier:
            if tier and (prev_tier is None or tier[0] > prev_tier[0]):
                lines.append(f"🚨 14-day avg just crossed {fmt_milestone(tier[0])}: buybacks now {tier[1]}% of revenue")
            else:
                now = f"{tier[1]}% of revenue" if tier else "off"
                lines.append(f"⚠️ 14-day avg fell below {fmt_milestone(prev_tier[0])}: buybacks now {now}")
    if tier:
        lines.append(f"🎯 ENA buybacks: {tier[1]}% of revenue (14-day avg ≥ {fmt_milestone(tier[0])})")

    upcoming = next((m for m in BUYBACK_MILESTONES if avg_now < m[0]), None)
    if upcoming is None:
        lines.append("Top buyback milestone reached.")
        return lines
    target, rate = upcoming
    if tier:
        lines.append(f"Next: {rate}% at {fmt_milestone(target)}")
    else:
        lines.append(f"🎯 ENA buybacks start at a {fmt_milestone(target)} 14-day avg ({rate}% of revenue)")
    needed = target - avg_now
    lines.append(f"{progress_bar(avg_now / target)} {avg_now / target:.0%}, needs +{fmt_usd(needed)} ({fmt_pct(needed / avg_now, 0)})")
    lines.append(eta_line(avg_now, avg_month_ago, needed, today))
    return lines


def eta_line(avg_now, avg_month_ago, needed, today):
    """Linear ETA from how much the 14-day average moved over the last TREND_DAYS."""
    if not avg_month_ago:
        return "ETA: not enough history yet"
    per_day = (avg_now - avg_month_ago) / TREND_DAYS
    if per_day <= 0:
        return f"ETA: none, the 14-day avg hasn't grown over the last {TREND_DAYS} days"
    days = needed / per_day
    pace = f"ETA at the last {TREND_DAYS} days' pace"
    if days > 3 * 365:
        return f"{pace}: 3+ years"
    span = f"~{round(days)} days" if days < 60 else f"~{round(days / 30.4)} months"
    return f"{pace}: {span} (≈ {today + timedelta(days=days):%b %Y})"


# --- Data sources --------------------------------------------------------------


def get_json(url, payload=None, timeout=60):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp)


def utc_day(timestamp):
    return datetime.fromtimestamp(int(timestamp), timezone.utc).date()


def stablecoin_series(url):
    """Daily [(date, USD value)] from a DefiLlama stablecoin chart, all pegs summed."""
    return [(utc_day(p["date"]), sum(p["totalCirculatingUSD"].values())) for p in get_json(url) if p.get("totalCirculatingUSD")]


def defi_tvl_series():
    return [(utc_day(p["date"]), p["tvl"]) for p in get_json(DEFI_TVL_URL)]


def susde_total_assets():
    """USDe staked in sUSDe, read from Ethereum."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "eth_call",
        "params": [{"to": SUSDE_ADDRESS, "data": TOTAL_ASSETS_SELECTOR}, "latest"],
    }
    last_error = None
    for rpc in ETH_RPC_URLS:
        try:
            result = get_json(rpc, payload, timeout=30)
            return int(result["result"], 16) / 1e18
        except (OSError, ValueError, KeyError) as e:
            last_error = e
            log(f"RPC {rpc} failed: {e}")
    raise last_error


# --- Sections --------------------------------------------------------------------
# Each section returns (message lines, snapshot values). To add a metric, write a
# section function and list it in SECTIONS.


def ethena_section(today):
    usde = stablecoin_series(USDE_CHART_URL)
    supply = usde[-1][1]
    avg_now = trailing_average(usde, AVG_DAYS)
    avg_month_ago = trailing_average(usde, AVG_DAYS, end_offset=TREND_DAYS) if len(usde) >= AVG_DAYS + TREND_DAYS else None
    avg_trend = f" ({TREND_DAYS}d {fmt_pct(avg_now / avg_month_ago - 1)})" if avg_month_ago else ""
    lines = [
        f"USDe supply: {fmt_usd(supply)}",
        f"  {changes_line(usde)}",
        f"  14-day avg: {fmt_usd(avg_now)}{avg_trend}",
        "",
        *buyback_lines(avg_now, trailing_average(usde, AVG_DAYS, end_offset=1), avg_month_ago, today),
        "",
    ]
    values = {"usde_supply": supply, "usde_avg14": avg_now}

    try:
        y = get_json(ETHENA_YIELD_URL)["avg30dSusdeYield"]
        try:
            as_of = datetime.strptime(y["lastUpdated"], "%d %b %y").strftime("%d %b")
        except ValueError:
            as_of = y["lastUpdated"]
        lines.append(f"sUSDe yield (30d avg): {y['value']:.2f}% (as of {as_of})")
        values["susde_yield_30d"] = y["value"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        log(f"sUSDe yield unavailable: {e}")
        lines.append("sUSDe yield: unavailable")

    try:
        staked = susde_total_assets()
        lines.append(f"Staked as sUSDe: {fmt_usd(staked)} ({staked / supply:.0%} of supply)")
        values["susde_staked"] = staked
    except (OSError, ValueError, KeyError) as e:
        log(f"sUSDe staked unavailable: {e}")
        lines.append("Staked as sUSDe: unavailable")
    return lines, values


def market_section(today):
    stablecoins = stablecoin_series(ALL_STABLECOINS_CHART_URL)
    tvl = defi_tvl_series()
    lines = [
        f"Stablecoin supply: {fmt_usd(stablecoins[-1][1])}",
        f"  {changes_line(stablecoins, spans=(7, 30))}",
        f"DeFi TVL: {fmt_usd(tvl[-1][1])}",
        f"  {changes_line(tvl, spans=(7, 30))}",
    ]
    return lines, {"stablecoins_total": stablecoins[-1][1], "defi_tvl": tvl[-1][1]}


SECTIONS = [
    ("Ethena", ethena_section),
    ("Whole market", market_section),
]


def build_digest(now):
    parts = [f"📊 <b>Crypto digest</b> · {now:%a %d %b %Y}"]
    snapshot = {}
    for title, section in SECTIONS:
        try:
            lines, values = section(now.date())
            snapshot.update(values)
        except Exception as e:  # one broken source shouldn't block the rest of the digest
            log(f"{title} section failed: {e!r}")
            lines = [f"unavailable ({html.escape(str(e))[:150]})"]
        parts.append("\n".join([f"<b>{title}</b>", *lines]).rstrip())
    return "\n\n".join(parts), snapshot


# --- Snapshot history ----------------------------------------------------------


def save_snapshot(day, values):
    """Write today's values to data/history.csv, replacing any row for the same day."""
    rows = []
    if HISTORY_FILE.exists():
        with HISTORY_FILE.open(newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != day.isoformat()]
    row = {"date": day.isoformat()}
    for key, value in values.items():
        row[key] = f"{value:.0f}" if abs(value) >= 1000 else f"{value:.4f}"
    rows.append(row)
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    with HISTORY_FILE.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SNAPSHOT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# --- Telegram ----------------------------------------------------------------------


def load_env():
    """Read KEY=value lines from .env (local runs; GitHub Actions passes secrets as env vars)."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8-sig").splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def telegram(method, **params):
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        sys.exit("Missing TELEGRAM_BOT_TOKEN (GitHub secret, or .env for local runs).")
    try:
        body = get_json(f"https://api.telegram.org/bot{token}/{method}", params, timeout=30)
    except urllib.error.HTTPError as e:
        try:
            description = json.load(e).get("description", str(e))
        except ValueError:
            description = str(e)
        sys.exit(f"Telegram {method} failed: {description}")
    return body["result"]


def send(text):
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not chat_id:
        sys.exit("Missing TELEGRAM_CHAT_ID (GitHub secret, or .env for local runs).")
    telegram(
        "sendMessage",
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        link_preview_options={"is_disabled": True},
    )


def find_chat():
    chats = {}
    for update in telegram("getUpdates"):
        chat = (update.get("message") or {}).get("chat")
        if chat:
            chats[chat["id"]] = chat.get("username") or chat.get("first_name") or chat.get("title")
    if not chats:
        print("No messages yet. Send /start to your bot in Telegram, then run this again.")
    for chat_id, name in chats.items():
        print(f"{chat_id}  ({name})")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_env()
    if "--find-chat" in sys.argv:
        find_chat()
        return
    now = datetime.now(SGT)
    text, snapshot = build_digest(now)
    if "--dry-run" in sys.argv:
        print(text)
        return
    if snapshot:
        save_snapshot(now.date(), snapshot)
    send(text)
    log("Digest sent.")


if __name__ == "__main__":
    main()
