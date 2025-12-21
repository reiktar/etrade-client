import asyncio
from etrade_client import ETradeClient

async def main():
    async with ETradeClient.from_env(sandbox=True) as client:
        # First time: authenticate via OAuth
        if not client.load_token():
            request_token = await client.auth.get_request_token()
            print(f"Visit: {request_token.authorization_url}")
            verifier = input("Enter verifier code: ")
            await client.auth.get_access_token(verifier)
            client.save_token()
        else:
            await client.renew_token()

        # List accounts
        accounts = await client.accounts.list_accounts()
        for account in accounts.accounts:
            print(f"{account.account_id_key}: {account.account_desc}")

        # Get quotes
        quotes = await client.market.get_quotes(["AAPL", "MSFT"])
        for quote in quotes.quotes:
            all_data = quote.all_data
            print(f"{quote.product.symbol}: ${all_data.last_trade:,.2f}")

asyncio.run(main())
