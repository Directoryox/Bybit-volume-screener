import aiohttp

from config import BYBIT_BASE_URL

async def get_symbols(
    session=None,
):

    close_session = False

    if session is None:
        session = aiohttp.ClientSession()
        close_session = True

    url = (
        f"{BYBIT_BASE_URL}"
        "/v5/market/instruments-info"
    )

    params = {
        "category": "linear",
        "limit": 1000,
    }

    try:
        async with session.get(
            url,
            params=params,
        ) as response:

            data = await response.json()

            if data.get(
                "retCode"
            ) != 0:

                return []

            symbols = []

            for item in data[
                "result"
            ][
                "list"
            ]:

                symbol = item[
                    "symbol"
                ]

                if (
                    symbol.endswith(
                        "USDT"
                    )
                    and
                    item.get(
                        "status"
                    )
                    == "Trading"
                ):

                    symbols.append(
                        symbol
                    )

            return symbols

    except Exception:
        return []

    finally:
        if close_session:
            await session.close()

async def get_klines(
    session_or_symbol,
    symbol=None,
    interval="60",
    limit=10,
    start=None,
    end=None,
):

    if isinstance(
        session_or_symbol,
        aiohttp.ClientSession,
    ):

        session = (
            session_or_symbol
        )

        actual_symbol = symbol

        close_session = False

    else:

        session = (
            aiohttp.ClientSession()
        )

        actual_symbol = (
            session_or_symbol
        )

        close_session = True

    if not actual_symbol:

        if close_session:
            await session.close()

        return None

    url = (
        f"{BYBIT_BASE_URL}"
        "/v5/market/kline"
    )

    params = {
        "category": "linear",
        "symbol": actual_symbol,
        "interval": interval,
        "limit": limit,
    }

    if start is not None:
        params[
            "start"
        ] = start

    if end is not None:
        params[
            "end"
        ] = end

    try:
        async with session.get(
            url,
            params=params,
        ) as response:

            data = await response.json()

            if data.get(
                "retCode"
            ) != 0:

                return None

            candles = (
                data[
                    "result"
                ][
                    "list"
                ]
            )

            candles.reverse()
            return candles

    except Exception:
        return None

    finally:
        if close_session:
            await session.close()

async def get_open_interest(
    session_or_symbol,
    symbol=None,
    limit=10,
    start=None,
    end=None,
):

    if isinstance(
        session_or_symbol,
        aiohttp.ClientSession,
    ):

        session = (
            session_or_symbol
        )

        actual_symbol = symbol

        close_session = False

    else:
        session = (
            aiohttp.ClientSession()
        )

        actual_symbol = (
            session_or_symbol
        )

        close_session = True

    if not actual_symbol:
        if close_session:
            await session.close()
        return None

    url = (
        f"{BYBIT_BASE_URL}"
        "/v5/market/open-interest"
    )

    params = {
        "category": "linear",
        "symbol": actual_symbol,
        "intervalTime": "1h",
        "limit": limit,
    }

    if start is not None:
        params[
            "startTime"
        ] = start

    if end is not None:
        params[
            "endTime"
        ] = end

    try:
        async with session.get(
            url,
            params=params,
        ) as response:

            data = await response.json()

            if data.get(
                "retCode"
            ) != 0:

                return None

            oi_list = (
                data[
                    "result"
                ][
                    "list"
                ]
            )

            oi_list.reverse()
            return oi_list

    except Exception:
        return None

    finally:
        if close_session:
            await session.close()

async def get_futures_price(
    session_or_symbol,
    symbol=None,
):

    if isinstance(
        session_or_symbol,
        aiohttp.ClientSession,
    ):

        session = (
            session_or_symbol
        )

        actual_symbol = symbol

        close_session = False

    else:
        session = (
            aiohttp.ClientSession()
        )

        actual_symbol = (
            session_or_symbol
        )

        close_session = True

    if not actual_symbol:
        if close_session:
            await session.close()
        return None

    url = (
        f"{BYBIT_BASE_URL}"
        "/v5/market/tickers"
    )

    params = {
        "category": "linear",
        "symbol": actual_symbol,
    }

    try:
        async with session.get(
            url,
            params=params,
        ) as response:

            data = await response.json()

            if data.get(
                "retCode"
            ) != 0:

                return None

            ticker_list = (
                data[
                    "result"
                ][
                    "list"
                ]
            )

            if not ticker_list:

                return None

            return float(
                ticker_list[0][
                    "lastPrice"
                ]
            )

    except Exception:
        return None

    finally:
        if close_session:
            await session.close()