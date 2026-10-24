# Setup

## 1. Launch it

Upload and launch the plugin as any other. It asks for the `data` role and
storage for its raw responses, and no key.

## 2. License its datasets

On the dashboard's **Data sources** page, the plugin's datasets are listed
with their default licences:

- `<instance>:live`: kept two days.
- `<instance>:outcomes`: kept.

The default says nothing about Polymarket's terms. Set the deployment's
licence there, with a note saying why, as you and the people using the
deployment have settled it. What you enter is what your deployment records.

## 3. Entitle the plugins that read it

On the same page, entitle each reading plugin to the datasets. Prices are
read by the reading roles; quotes by the roles that read at a higher
resolution (signal, portfolio, order and execution plugins); outcomes by the
reading roles and by operations, which explains a payout with them. Nothing reads a
dataset it is not entitled to.

## 4. Complete the tokens' records

The plugin names the tokens your readers ask about from their records, and
offers the token's ID, the class, the type and Polymarket's words where a
record lacks them. Complete each record on the **Instruments** page: its
type, binary event contract, and its payout, one pUSD (Polymarket's
collateral token, the platform's pUSD record).

## Agents

An agent you delegate to can read the plugin's two pages through its tools
(`read_connection`, `read_datasets`); the Data sources and Instruments pages
have tools of their own.

## Sample data

On a development deployment, the plugin's **Sample data** setting makes it
answer from built-in synthetic responses instead of calling Polymarket, to
try it without reaching Polymarket.
