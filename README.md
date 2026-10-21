# Crypto digest

A Telegram message every morning (about 9am Singapore time) covering:

- **Ethena:** USDe supply, its 14-day average, and progress toward the ENA buyback milestones. Also the sUSDe yield and how much USDe is staked.
- **Chainlink:** the total value secured (TVS) by Chainlink oracles, and how far it leads the next biggest oracle.
- **LINK Reserve:** how much LINK the Chainlink Reserve has bought, compared with how much LINK Chainlink has unlocked into circulation.
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

Each run appends a row to `data/history.csv` and commits it. That builds a record of what was reported, and the commit keeps GitHub from pausing the schedule, which it does after 60 days without repo activity.
