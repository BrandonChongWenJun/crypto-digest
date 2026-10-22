# Crypto digest

A Telegram message every morning (about 9am Singapore time) covering:

- **Ethena:** USDe supply, its 14-day average, and progress toward the ENA buyback milestones. Also the sUSDe yield and how much USDe is staked.
- **Chainlink:** the total value secured (TVS) by Chainlink oracles, and how far it leads the next biggest oracle.
- **LINK Reserve:** how much LINK the Chainlink Reserve has bought, compared with how much LINK Chainlink has unlocked into circulation.
- **Aero:** trading volume, revenue paid to sAERO stakers, and Aero's share of DEX volume against the biggest rival on each chain it runs on.
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

Chainlink
Chainlink TVS: $33.1B · #1 · 532 protocols
  1d +1.0% · 7d −1.3% · 30d −3.9%
Closest rival: Pyth $2.48B · 306 protocols
  1d +1.8% · 7d −2.9% · 30d +0.1%
Lead: 13.3x (30d ago 13.8x)
Share of all oracle TVS: 81% (30d ago 81%)
Next: RedStone $2.11B · Atlas $981.8M

LINK Reserve
Reserve: 6.29M LINK ($77.8M)
  90d +1.35M · 365d +5.77M
Unlocked by Chainlink:
  90d 18.8M · 365d 70.0M
Reserve buys vs unlocks: 7% (90d) · 8% (365d)

Aero
Volume 30d: $16.5B (+18.2% vs prior 30d)
Revenue to sAERO stakers 30d: $8.2M (−43.9% vs prior 30d)
  0.050% of volume (prior 30d 0.104%)
  Annualized $99.3M = 13.9% of AERO market cap ($716.0M)
DEX volume share, 30d (prior 30d):
  All 7 chains $110.7B: Aero 15% (10%) · Uniswap 56% (58%)
  Ethereum $39.7B: Aero 0.0% (0.0%) · Uniswap 59% (56%)
  Robinhood Chain $33.8B: Aero 0.0% (0.0%) · Uniswap 77% (76%)
  Base $29.8B: Aero 53% (48%) · Uniswap 26% (25%)
  Arbitrum $5.05B: Aero 0.0% (0.0%) · Uniswap 70% (75%)
  Arc $1.31B: Aero 4.6% (1.7%) · Uniswap 91% (87%)
  OP Mainnet $876.6M: Aero 58% (57%) · Uniswap 16% (19%)
  Ink $89.6M: Aero 66% (64%) · Uniswap 18% (13%)

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

## Chainlink's TVS

Total value secured is the money in DeFi protocols that would be at risk if an oracle failed. DefiLlama's oracle rankings are behind its paid API, so the bot rebuilds them from DefiLlama's free protocol data using [DefiLlama's method](https://docs.llama.fi/list-your-project/oracles-tvs):

- A protocol's TVL counts toward its **primary** oracle, the one securing most of its funds. Fallback, secondary and aggregated-in oracles don't count.
- If a protocol uses different oracles on different chains, each chain's TVL goes to that chain's oracle.
- A protocol that depends on two oracles counts fully toward both.
- Protocols' in-house prices and DEX prices (TWAPs) aren't oracle providers, so they're left out of the ranking.

The totals land close to DefiLlama's own page, but not exactly on it. The 1d, 7d and 30d changes use today's list of which protocol uses which oracle, so they show whether each oracle's existing clients grew. A protocol switching oracles shows up as a jump in the totals instead.

The digest alerts you if another oracle passes Chainlink, or if a different oracle becomes the closest rival.

## The LINK Reserve

Chainlink converts revenue paid in other tokens (stablecoins, gas tokens, and enterprise payments) into LINK through Payment Abstraction, and puts that LINK into the [Chainlink Reserve](https://chain.link/blog/chainlink-reserve-strategic-link-reserve). The Reserve's balance is read straight from its Ethereum contract, so it's the most direct public sign of Chainlink's revenue.

Against that, Chainlink Labs regularly moves LINK out of the wallets it lists as non-circulating supply, usually about every three months. Its [supply API](https://supply.chain.link/supply) lists those wallets. The bot reads their balances now and roughly 90 and 365 days ago, so "Unlocked by Chainlink" is how much circulating supply grew over that time.

"Reserve buys vs unlocks" divides the first by the second. If it rises toward 100%, the Reserve is buying back as much LINK as is being unlocked.

Past balances need an Ethereum node that keeps old state. If none of the public ones answers, the digest still shows today's Reserve balance.

## Aero

Aerodrome (Base) and Velodrome (OP Mainnet) merged into [Aero](https://www.theblock.co/news/defi/2026-10-21-aerodrome-velodrome-merge-aero-421514) on 21 Oct 2026 and launched on seven chains. Aero pays 100% of its revenue to people who stake AERO (sAERO), and liquidity providers are paid in AERO rewards. A fee-funded token only holds up if trading volume does (SUSHI fell about 95% when 2021's volume dried up), so the section tracks:

- **Volume:** Aero's trading volume over the last 30 days against the 30 days before.
- **Revenue to stakers:** what sAERO stakers earned, how much of each traded dollar that is, and the annualized total as a share of AERO's market cap. If only some AERO is staked, stakers' actual yield is higher than that share.
- **Market share:** Aero's share of all DEX volume on its seven chains, and on each chain against the biggest rival there. Rising share on Ethereum, Arbitrum and Robinhood Chain, where Uniswap dominates, is the sign that the model is pulling volume from bigger exchanges.

DefiLlama groups Aero, Aerodrome and Velodrome under one protocol, so the numbers include the old Aerodrome and Velodrome pools. Volume on a chain only appears once DefiLlama tracks Aero there.

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
- [DefiLlama protocols](https://api-docs.defillama.com/): each protocol's TVL now and 1, 7 and 30 days ago, and the oracles it uses, for Chainlink's TVS
- [Ethena API](https://ethena.fi): sUSDe yield, which Ethena updates about weekly
- Ethereum (public RPC): USDe staked in sUSDe, via the vault's `totalAssets()`, and the LINK balances of the Reserve and the non-circulating wallets
- [Chainlink supply API](https://supply.chain.link/supply): the list of non-circulating LINK wallets
- [DefiLlama DEX volumes and fees](https://defillama.com/dexs): volume by exchange on each of Aero's chains, and revenue to sAERO stakers
- [CoinGecko](https://www.coingecko.com/en/coins/aerodrome-finance): AERO market cap

Each run appends a row to `data/history.csv` and commits it. That builds a record of what was reported, and the commit keeps GitHub from pausing the schedule, which it does after 60 days without repo activity.
