# etrade-cli Reference

Command-line interface for E\*Trade API.

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Global Options](#global-options)
4. [Commands](#commands)
   - [auth](#auth---authentication)
   - [accounts](#accounts---account-information)
   - [market](#market---market-data)
   - [orders](#orders---order-management)
   - [alerts](#alerts---alert-management)
   - [transactions](#transactions---transaction-history)

## Installation

```bash
# Install globally
uv tool install "git+ssh://git@github.com/reiktar/etrade-client.git"

# Or run directly without installing
uvx --from "git+ssh://git@github.com/reiktar/etrade-client.git" etrade-cli --help

# Update to latest version
uv tool upgrade etrade-client
```

## Configuration

The CLI uses XDG-compliant directories with environment-specific configuration:

### Directory Structure

```
~/.config/etrade-cli/              # Credentials (XDG_CONFIG_HOME)
├── sandbox.json                   # Sandbox credentials
└── production.json                # Production credentials

~/.local/share/etrade-cli/         # Tokens (XDG_DATA_HOME)
├── sandbox-token.json             # Sandbox OAuth token
└── production-token.json          # Production OAuth token
```

### Config Files

Create environment-specific credential files:

**Sandbox** (`~/.config/etrade-cli/sandbox.json`):
```json
{
    "consumer_key": "your_sandbox_key",
    "consumer_secret": "your_sandbox_secret"
}
```

**Production** (`~/.config/etrade-cli/production.json`):
```json
{
    "consumer_key": "your_production_key",
    "consumer_secret": "your_production_secret"
}
```

### Environment Variables

Environment variables override config file values:

```bash
export ETRADE_CONSUMER_KEY="override_key"
export ETRADE_CONSUMER_SECRET="override_secret"
```

This is useful for:
- CI/CD pipelines
- Testing with different credentials
- Temporary overrides without modifying files

### Loading Priority

1. Load from environment-specific config file (`sandbox.json` or `production.json`)
2. Override individual values with environment variables (if set)

### View Current Paths

```bash
# Show paths for current environment
etrade-cli auth paths

# Show paths for production
etrade-cli --production auth paths
```

## Global Options

```
etrade-cli [OPTIONS] COMMAND

Options:
  -s, --sandbox / -p, --production
                        Use sandbox or production (default) environment
                        [env var: ETRADE_SANDBOX]
  -v, --verbose         Enable verbose output
  -c, --config-dir PATH Config directory for credentials
                        [env var: ETRADE_CLI_CONFIG_DIR]
  -d, --data-dir PATH   Data directory for tokens
                        [env var: ETRADE_CLI_DATA_DIR]
  --help                Show this message and exit
```

### Examples

```bash
# Use production (default)
etrade-cli accounts list

# Use sandbox
etrade-cli --sandbox accounts list

# Custom directories
etrade-cli --config-dir /path/to/config --data-dir /path/to/data accounts list
```

---

## auth - Authentication

Manage OAuth authentication.

### auth login

Authenticate with E\*Trade OAuth.

```bash
etrade-cli auth login [OPTIONS]

Options:
  --no-browser  Don't open browser automatically
```

**Example:**
```bash
# Interactive login (opens browser)
etrade-cli auth login

# Manual URL (no browser)
etrade-cli auth login --no-browser
```

### auth status

Check authentication status.

```bash
etrade-cli auth status
```

**Output:**
```
Environment: sandbox
Token path: /home/user/.config/etrade-cli/token.json
✓ Token found - you are authenticated
Note: Tokens expire at midnight US Eastern time
```

### auth renew

Renew the current access token.

```bash
etrade-cli auth renew
```

### auth logout

Log out and clear saved token.

```bash
etrade-cli auth logout [OPTIONS]

Options:
  --revoke / --no-revoke  Revoke token on server (default: revoke)
```

**Example:**
```bash
# Revoke on server and clear locally
etrade-cli auth logout

# Only clear local token
etrade-cli auth logout --no-revoke
```

### auth paths

Show configuration and data paths for current environment.

```bash
etrade-cli auth paths
```

**Output:**
```
Environment: sandbox

Configuration (credentials):
  Directory: /home/user/.config/etrade-cli
  File: /home/user/.config/etrade-cli/sandbox.json
  Status: exists

Data (tokens):
  Directory: /home/user/.local/share/etrade-cli
  File: /home/user/.local/share/etrade-cli/sandbox-token.json
  Status: exists
```

---

## accounts - Account Information

View accounts, balances, and portfolios.

### accounts list

List all accounts.

```bash
etrade-cli accounts list [OPTIONS]

Options:
  -o, --output [table|json|csv]  Output format [default: table]
```

**Example:**
```bash
etrade-cli accounts list

# Output as JSON
etrade-cli accounts list -o json
```

**Output:**
```
                         Accounts
┏━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ account_id         ┃ name         ┃ type       ┃ mode   ┃ status ┃
┡━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ abc123             │ Individual   │ INDIVIDUAL │ MARGIN │ ACTIVE │
│ def456             │ Retirement   │ IRA        │ CASH   │ ACTIVE │
└────────────────────┴──────────────┴────────────┴────────┴────────┘
```

### accounts balance

Get account balance.

```bash
etrade-cli accounts balance ACCOUNT_ID [OPTIONS]

Arguments:
  ACCOUNT_ID  Account ID key (from 'accounts list')

Options:
  -o, --output [table|json|csv]  Output format [default: table]
```

**Example:**
```bash
etrade-cli accounts balance abc123
```

### accounts portfolio

Get account portfolio positions.

```bash
etrade-cli accounts portfolio ACCOUNT_ID [OPTIONS]

Arguments:
  ACCOUNT_ID  Account ID key

Options:
  -v, --view TEXT      View type: QUICK, PERFORMANCE, FUNDAMENTAL, COMPLETE
                       [default: QUICK]
  -o, --output [table|json|csv]  Output format [default: table]
```

**Example:**
```bash
etrade-cli accounts portfolio abc123

# Detailed view
etrade-cli accounts portfolio abc123 --view COMPLETE
```

### accounts dividends

List dividend transactions for an account.

```bash
etrade-cli accounts dividends ACCOUNT_ID [OPTIONS]

Arguments:
  ACCOUNT_ID  Account ID key

Options:
  -s, --symbol TEXT    Filter by symbol
  --from TEXT          Start date (YYYY-MM-DD). Requires --to.
  --to TEXT            End date (YYYY-MM-DD). Requires --from.
  --ytd                Year to date (Jan 1 to today)
  --alltime            All dividends (full history)
  --by-symbol          Group totals by symbol
  --by-month           Group totals by year-month
  -n, --limit INT      Maximum dividends to return [default: all]
  -o, --output [table|json|csv]  Output format [default: table]
```

**Note:** Shows both cash dividends and DRIP (dividend reinvestment) transactions. DRIP transactions are marked with "Yes" and show shares purchased at the reinvestment price.

**Example:**
```bash
# Recent dividends
etrade-cli accounts dividends abc123

# Year to date
etrade-cli accounts dividends abc123 --ytd

# Specific symbol
etrade-cli accounts dividends abc123 --symbol AAPL --ytd

# Group by symbol (sorted by total amount)
etrade-cli accounts dividends abc123 --ytd --by-symbol

# Group by month
etrade-cli accounts dividends abc123 --ytd --by-month

# Group by both month and symbol
etrade-cli accounts dividends abc123 --ytd --by-symbol --by-month

# Export to CSV
etrade-cli accounts dividends abc123 --alltime -o csv > dividends.csv
```

**Output (default):**
```
                                Dividends
┏━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Date       ┃ Symbol ┃ Amount  ┃ Drip               ┃ Shares ┃ Price  ┃
┡━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ 2025-12-18 │ YBTC   │ $3.40   │ Yes                │ 0.110  │ $30.97 │
│ 2025-12-18 │ YBTC   │ $3.43   │                    │        │        │
│ ---        │ TOTAL  │ $6.83   │ ($3.40 reinvested) │        │        │
└────────────┴────────┴─────────┴────────────────────┴────────┴────────┘
```

**Output (--by-symbol):**
```
                         Dividends by Symbol
┏━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━┓
┃ Symbol ┃ Amount    ┃ Reinvested ┃ Cash    ┃ Count ┃
┡━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━┩
│ SCHD   │ $125.50   │ $125.50    │ $0.00   │ 4     │
│ VTI    │ $98.25    │ $0.00      │ $98.25  │ 4     │
│ AAPL   │ $45.00    │ $45.00     │ $0.00   │ 4     │
│ TOTAL  │ $268.75   │ $170.50    │ $98.25  │       │
└────────┴───────────┴────────────┴─────────┴───────┘
```

**Output (--by-month):**
```
                        Dividends by Month
┏━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━┓
┃ Month   ┃ Amount    ┃ Reinvested ┃ Cash    ┃ Count ┃
┡━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━┩
│ 2025-12 │ $85.50    │ $45.00     │ $40.50  │ 5     │
│ 2025-11 │ $92.25    │ $62.50     │ $29.75  │ 4     │
│ 2025-10 │ $91.00    │ $63.00     │ $28.00  │ 3     │
│ TOTAL   │ $268.75   │ $170.50    │ $98.25  │       │
└─────────┴───────────┴────────────┴─────────┴───────┘
```

The **Cash** column shows dividend amounts that were not automatically reinvested (DRIP'd) and are available in your account balance for manual reinvestment.

---

## market - Market Data

Get quotes and option data.

### market quote

Get quotes for one or more symbols.

```bash
etrade-cli market quote SYMBOLS... [OPTIONS]

Arguments:
  SYMBOLS  One or more ticker symbols (max 25)

Options:
  -d, --detail TEXT    Detail level: ALL, FUNDAMENTAL, INTRADAY, OPTIONS, WEEK_52
                       [default: ALL]
  -o, --output [table|json|csv]  Output format [default: table]
```

**Example:**
```bash
# Single symbol
etrade-cli market quote AAPL

# Multiple symbols
etrade-cli market quote AAPL MSFT GOOGL

# Fundamental data only
etrade-cli market quote AAPL --detail FUNDAMENTAL
```

**Output:**
```
                              Quotes
┏━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━┓
┃ symbol ┃ last      ┃ change  ┃ change_pct ┃ bid       ┃ ask       ┃ volume      ┃
┡━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━┩
│ AAPL   │ $175.00   │ +2.50   │ +1.45%     │ $174.98   │ $175.02   │ 45,234,567  │
│ MSFT   │ $378.25   │ -1.75   │ -0.46%     │ $378.20   │ $378.30   │ 23,456,789  │
└────────┴───────────┴─────────┴────────────┴───────────┴───────────┴─────────────┘
```

### market lookup

Look up securities by name or symbol.

```bash
etrade-cli market lookup SEARCH [OPTIONS]

Arguments:
  SEARCH  Company name or partial symbol to search

Options:
  -o, --output [table|json|csv]  Output format [default: table]
```

**Example:**
```bash
etrade-cli market lookup "Apple"
```

### market options-dates

Get available option expiration dates.

```bash
etrade-cli market options-dates SYMBOL [OPTIONS]

Arguments:
  SYMBOL  Underlying symbol

Options:
  -t, --type TEXT      Expiry type: ALL, MONTHLY, WEEKLY
  -o, --output [table|json|csv]  Output format [default: table]
```

**Example:**
```bash
etrade-cli market options-dates AAPL

# Monthly only
etrade-cli market options-dates AAPL --type MONTHLY
```

### market options-chain

Get options chain for a symbol and expiry date.

```bash
etrade-cli market options-chain SYMBOL EXPIRY [OPTIONS]

Arguments:
  SYMBOL  Underlying symbol
  EXPIRY  Expiry date (YYYY-MM-DD)

Options:
  -t, --type TEXT      Chain type: CALL, PUT, CALLPUT [default: CALLPUT]
  -n, --strikes INT    Number of strikes to return
  -o, --output [table|json|csv]  Output format [default: table]
```

**Example:**
```bash
# Full chain
etrade-cli market options-chain AAPL 2025-01-17

# Calls only, 5 strikes
etrade-cli market options-chain AAPL 2025-01-17 --type CALL --strikes 5
```

---

## orders - Order Management

List and cancel orders.

### orders list

List orders for an account.

```bash
etrade-cli orders list ACCOUNT_ID [OPTIONS]

Arguments:
  ACCOUNT_ID  Account ID key

Options:
  -s, --status TEXT    Filter by status: OPEN, EXECUTED, CANCELLED, EXPIRED, REJECTED
  --symbol TEXT        Filter by symbol
  --from TEXT          Start date (YYYY-MM-DD). Requires --to.
  --to TEXT            End date (YYYY-MM-DD). Requires --from.
  --ytd                Year to date (Jan 1 to today)
  --alltime            All orders (full history)
  -n, --limit INT      Maximum orders to return [default: all]
  -o, --output [table|json|csv]  Output format [default: table]
```

**Note:** Without date filters, only recent orders are returned. Use `--ytd`, `--alltime`, or `--from`/`--to` together for full history.

**Example:**
```bash
# Recent orders (default)
etrade-cli orders list abc123

# Year to date
etrade-cli orders list abc123 --ytd

# Full history
etrade-cli orders list abc123 --alltime

# Open orders only
etrade-cli orders list abc123 --status OPEN

# Date range (both required)
etrade-cli orders list abc123 --from 2024-01-01 --to 2024-12-31
```

### orders cancel

Cancel an open order.

```bash
etrade-cli orders cancel ACCOUNT_ID ORDER_ID
```

**Example:**
```bash
etrade-cli orders cancel abc123 12345
```

---

## alerts - Alert Management

View and delete alerts.

### alerts list

List alerts.

```bash
etrade-cli alerts list [OPTIONS]

Options:
  -c, --category TEXT  Filter by category: STOCK, ACCOUNT
  -s, --status TEXT    Filter by status: READ, UNREAD, DELETED
  --search TEXT        Search in alert subject
  -n, --limit INT      Maximum alerts to return (max 300) [default: all]
  -o, --output [table|json|csv]  Output format [default: table]
```

**Example:**
```bash
# All alerts
etrade-cli alerts list

# Unread stock alerts
etrade-cli alerts list --status UNREAD --category STOCK
```

### alerts get

Get alert details.

```bash
etrade-cli alerts get ALERT_ID [OPTIONS]

Arguments:
  ALERT_ID  Alert ID

Options:
  -o, --output [table|json|csv]  Output format [default: table]
```

### alerts delete

Delete one or more alerts.

```bash
etrade-cli alerts delete ALERT_IDS...

Arguments:
  ALERT_IDS  Alert ID(s) to delete
```

**Example:**
```bash
# Single alert
etrade-cli alerts delete 12345

# Multiple alerts
etrade-cli alerts delete 12345 12346 12347
```

---

## transactions - Transaction History

View transaction history.

### transactions list

List transactions for an account.

```bash
etrade-cli transactions list ACCOUNT_ID [OPTIONS]

Arguments:
  ACCOUNT_ID  Account ID key

Options:
  -s, --symbol TEXT    Filter by symbol
  --from TEXT          Start date (YYYY-MM-DD). Requires --to.
  --to TEXT            End date (YYYY-MM-DD). Requires --from.
  --ytd                Year to date (Jan 1 to today)
  --alltime            All transactions (full history)
  -n, --limit INT      Maximum transactions to return [default: all]
  --sort TEXT          Sort order: ASC or DESC [default: DESC]
  -o, --output [table|json|csv]  Output format [default: table]
```

**Note:** Without date filters, only recent transactions are returned. Use `--ytd`, `--alltime`, or `--from`/`--to` together for full history.

**Example:**
```bash
# Recent transactions (default)
etrade-cli transactions list abc123

# Year to date
etrade-cli transactions list abc123 --ytd

# Full history
etrade-cli transactions list abc123 --alltime

# Filter by symbol
etrade-cli transactions list abc123 --ytd --symbol AAPL

# Date range (both required)
etrade-cli transactions list abc123 --from 2024-01-01 --to 2024-12-31

# Export to CSV
etrade-cli transactions list abc123 --alltime -o csv > transactions.csv
```

---

## Output Formats

All commands support three output formats:

| Format | Flag | Description |
|--------|------|-------------|
| `table` | `-o table` | Formatted table (default) |
| `json` | `-o json` | JSON array |
| `csv` | `-o csv` | CSV format |

**Examples:**
```bash
# Default table output
etrade-cli accounts list

# JSON for scripting
etrade-cli accounts list -o json | jq '.[] | .account_id'

# CSV for spreadsheets
etrade-cli transactions list abc123 -o csv > transactions.csv
```

## Shell Completion

Enable shell completion for bash, zsh, or fish:

```bash
# Bash
etrade-cli --install-completion bash

# Zsh
etrade-cli --install-completion zsh

# Fish
etrade-cli --install-completion fish
```
