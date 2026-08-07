from app.market_data.ohlcv_fetcher import (
    OHLCVFetcher,
)


def main():

    fetcher = OHLCVFetcher()


    df = fetcher.fetch(
        symbol="BTCUSDT",
        timeframe="15m",
        limit=50,
    )


    print(
        "\n========== OHLCV TEST ==========\n"
    )


    if df.empty:

        print(
            "No data received"
        )

    else:

        print(
            df.head()
        )


        print(
            "\nRows:",
            len(df),
        )


        print(
            "\nColumns:",
            list(df.columns),
        )


    print(
        "\n================================\n"
    )



if __name__ == "__main__":

    main()
