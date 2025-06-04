from requests import Request, Session
from requests.exceptions import ConnectionError, Timeout, TooManyRedirects
import json
from datetime import datetime
import os
import sqlite3
import schedule
import time
from dotenv import load_dotenv

load_dotenv()

coin_market_api = os.getenv("COIN_MARKET_API")

def get_quotes():
    url = 'https://pro-api.coinmarketcap.com/v2/cryptocurrency/quotes/latest'
    parameters = {
    'slug':'bitcoin,ethereum,solana,xrp',
    'convert':"INR"
    }
    headers = {
    'Accepts': 'application/json',
    'X-CMC_PRO_API_KEY': coin_market_api
    }

    session = Session()
    session.headers.update(headers)

    try:
        response = session.get(url, params=parameters)
        data = response.json()['data']
        conn = sqlite3.connect("crypto_data.db")
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS crypto (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                max_supply REAL,
                circulating_supply REAL,
                total_supply REAL,
                price REAL,
                percent_change_1h REAL,
                percent_change_24h REAL,
                percent_change_7d REAL,
                percent_change_30d REAL,
                percent_change_60d REAL,
                percent_change_90d REAL,
                timestamp TEXT
            )
        ''')
        for key in data.keys():
            crypto = data[str(key)]
            quote = crypto['quote']['INR']

            cursor.execute('''
                INSERT INTO crypto (
                    name, max_supply, circulating_supply, total_supply, price,
                    percent_change_1h, percent_change_24h, percent_change_7d,
                    percent_change_30d, percent_change_60d, percent_change_90d, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                crypto['name'],
                0.0 if crypto['max_supply'] is None else float(crypto['max_supply']),
                float(crypto['circulating_supply']),
                float(crypto['total_supply']),
                float(quote['price']),
                float(quote['percent_change_1h']),
                float(quote['percent_change_24h']),
                float(quote['percent_change_7d']),
                float(quote['percent_change_30d']),
                float(quote['percent_change_60d']),
                float(quote['percent_change_90d']),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ))
            conn.commit()


    except (ConnectionError, Timeout, TooManyRedirects) as e:
        print(e)

    conn.close()


def scheduled_task():
    get_quotes()

# Schedule: every 30 minutes
schedule.every(30).minutes.do(scheduled_task)


if __name__ == "__main__":
    print("Scheduler started. Will run every 30 minutes.")
    while True:
        schedule.run_pending()
        time.sleep(1)