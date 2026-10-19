# Crypto digest

A Telegram message every morning (about 9am Singapore time) covering:

- **Ethena:** USDe supply, its 14-day average, and progress toward the ENA buyback milestones. Also the sUSDe yield and how much USDe is staked.
- **Whole market:** total stablecoin supply and DeFi TVL, as signals of whether on-chain adoption is growing or shrinking.

It runs on GitHub Actions for free, so your computer doesn't need to be on.

```
📊 Crypto digest · Mon 19 Oct 2026

Ethena
USDe supply: $4.68B
  1d +0.0% · 7d −1.6% · 30d −2.6%
  14-day avg: $4.79B (30d +4.7%)

🎯 ENA buybacks start at a $7.5B 14-day avg (5% of revenue)
▓▓▓▓▓▓░░░░ 64%, needs +$2.71B (+57%)
ETA at the last 30 days' pace: ~12 months (≈ Oct 2027)

sUSDe yield (30d avg): 4.80% (as of 14 Oct)
Staked as sUSDe: $1.22B (26% of supply)

Whole market
Stablecoin supply: $306.4B
  7d −0.5% · 30d +0.4%
DeFi TVL: $89.7B
  7d −2.5% · 30d −2.9%
```

## The ENA buyback milestones

In September 2026, ENA holders [voted to approve](https://gov.ethenafoundation.com/t/ena-fee-switch-activation/830) buybacks that scale with USDe supply:

| USDe supply | $7.5B | $10B | $15B | $20B | $25B+ |
|---|---|---|---|---|---|
| Share of revenue used to buy back ENA | 5% | 10% | 15% | 20% | 25% |

The vote doesn't define how supply is measured. The Risk Committee recommended a 14-day average, so a single large mint can't trigger a milestone, and this bot uses that. When the 14-day average crosses a milestone in either direction, the digest leads with an alert.

## Setup

1. In Telegram, message **@BotFather**, send `/newbot`, and copy the token.
2. Send `/start` to your new bot.
3. Copy `.env.example` to `.env` and paste the token. Then run `py digest.py --find-chat` and paste the number it prints as `TELEGRAM_CHAT_ID`.
4. Add both values as GitHub repository secrets (Settings → Secrets and variables → Actions), or run:
   ```
   gh secret set TELEGRAM_BOT_TOKEN
   gh secret set TELEGRAM_CHAT_ID
   ```
5. To test it, open Actions → Daily digest → **Run workflow**. Tick "Preview only" to see the message in the run log without sending it.

If a run fails, GitHub emails you.

## Local commands

- `py digest.py --dry-run` prints today's message without sending it.
- `py digest.py` sends it, using `.env`.
- `py -m unittest test_digest` runs the tests.

## Adding a metric

Write a function that returns `(lines, snapshot_values)` and add it to `SECTIONS` in `digest.py`. If one section fails, the others still go out.

## Data sources

All of these are free and need no API key.

- [DefiLlama](https://defillama.com/stablecoins): USDe supply history, total stablecoin supply, and DeFi TVL
- [Ethena API](https://ethena.fi): sUSDe yield, which Ethena updates about weekly
- Ethereum (public RPC): USDe staked in sUSDe, via the vault's `totalAssets()`

Each run appends a row to `data/history.csv` and commits it. That builds a record of what was reported, and the commit keeps GitHub from pausing the schedule, which it does after 60 days without repo activity.
