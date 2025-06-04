from cryptography.hazmat.primitives.asymmetric import ed25519
from urllib.parse import urlparse, urlencode
import urllib
import json
import time 
import os
import requests
from dotenv import load_dotenv

load_dotenv()

######################################################################################################################################

GENERAL_ENDPOINT = "https://coinswitch.co"

######################################################################################################################################

secret_key = os.getenv("SECRET_KEY")
api_key = os.getenv("API_KEY")

######################################################################################################################################

def get_signature(signature_msg):
  request_string = bytes(signature_msg, 'utf-8')
  secret_key_bytes = bytes.fromhex(secret_key)
  secret_key_second = ed25519.Ed25519PrivateKey.from_private_bytes(secret_key_bytes)
  signature_bytes = secret_key_second.sign(request_string)
  signature = signature_bytes.hex()
  return signature

######################################################################################################################################

def get_signature_post(method, endpoint, params, epoch_time):
  unquote_endpoint = endpoint
  if method == "GET" and len(params) != 0:
      endpoint += ('&', '?')[urlparse(endpoint).query == ''] + urlencode(params)
      unquote_endpoint = urllib.parse.unquote_plus(endpoint)

  signature_msg = method + unquote_endpoint + epoch_time

  request_string = bytes(signature_msg, 'utf-8')
  secret_key_bytes = bytes.fromhex(secret_key)
  secret_key_second = ed25519.Ed25519PrivateKey.from_private_bytes(secret_key_bytes)
  signature_bytes = secret_key_second.sign(request_string)
  signature = signature_bytes.hex()
  return signature
######################################################################################################################################

def api_call(endpoint, method, payload, params):
    signature_msg = method + endpoint + json.dumps(payload, separators=(',', ':'), sort_keys=True)
    signature = get_signature(signature_msg=signature_msg)

    headers = {
        'Content-Type': 'application/json',
        'X-AUTH-SIGNATURE': signature,
        'X-AUTH-APIKEY': api_key,
    }

    url = GENERAL_ENDPOINT + endpoint

    response = requests.request("GET", url, headers=headers, json=payload, params=params)
    return response

######################################################################################################################################

def key_validation():
    endpoint = "/trade/api/v2/validate/keys"
    method = "GET"
    payload = {}
    params = {}
    response = api_call(endpoint=endpoint, method=method, payload=payload, params=params)

    print(response.json())

######################################################################################################################################

def delete_api(order_id):
    payload = {
            "order_id": "698ed406-8ef5-4664-9779-f7978702a447"
        }
    endpoint = "/trade/api/v2/order"
    method = "DELETE"
    
    response = api_call(endpoint=endpoint, params=None, payload=payload, method=method)
    print(response.json())

######################################################################################################################################

def get_order():
    params = {
        "count": 20,
        "from_time": 1600261657954,
        "to_time": 1687261657954,
        "side": "sell",
        "symbols": "btc/inr,eth/inr",
        "exchanges": "coinswitchx,wazirx",
        "type": "limit",
        "open": True
    }

    endpoint = "/trade/api/v2/orders"
    method = "GET"
    payload = {}
    epoch_time = str(int(time.time() * 1000))

    unquote_endpoint = endpoint
    endpoint += ('&', '?')[urlparse(unquote_endpoint).query == ''] + urlencode(params)
    unquote_endpoint = urllib.parse.unquote_plus(endpoint)

    signature_msg = method + unquote_endpoint + epoch_time
    signature = get_signature(signature_msg=signature_msg)
    url = GENERAL_ENDPOINT + endpoint

    headers = {
    'Content-Type': 'application/json',
    'X-AUTH-SIGNATURE': signature,
    'X-AUTH-APIKEY': api_key,
    'X-AUTH-EPOCH': epoch_time
    }

    response = requests.request("GET", url, headers=headers, json=payload)
    print(response.json())

######################################################################################################################################

def ping_test():
    payload = {}
    endpoint = "/trade/api/v2/ping"
    method = "GET"
    url = GENERAL_ENDPOINT + "/trade/api/v2/ping"

    signature_msg = method + endpoint + json.dumps(payload, separators=(',', ':'), sort_keys=True)
    signature = get_signature(signature_msg=signature_msg)

    headers = {
    'Content-Type': 'application/json',
    'X-AUTH-SIGNATURE': signature,
    'X-AUTH-APIKEY': api_key
    }

    response = requests.request("GET", url, headers=headers, json=payload)

    return response.json()['message'] == "OK"

######################################################################################################################################

def get_coins():
    endpoint = "/trade/api/v2/coins"
    params = {
        "exchange": "coinswitchx",
    }
    payload = {}

    endpoint += ('&', '?')[urlparse(endpoint).query == ''] + urlencode(params)

    method = "GET"

    response = api_call(endpoint=endpoint, params=str(params), payload=payload, method=method)
    print(response.json())

######################################################################################################################################

def get_trading_fee():
    endpoint = "/trade/api/v2/tradingFee"
    params = {
        "exchange": "coinswitchx",
    }
    method = "GET"
    payload = {}
    epoch_time = str(int(time.time() * 1000))

    unquote_endpoint = endpoint
    endpoint += ('&', '?')[urlparse(unquote_endpoint).query == ''] + urlencode(params)
    unquote_endpoint = urllib.parse.unquote_plus(endpoint)

    signature_msg = method + unquote_endpoint + epoch_time
    signature = get_signature(signature_msg=signature_msg)
    url = GENERAL_ENDPOINT + endpoint

    headers = {
    'Content-Type': 'application/json',
    'X-AUTH-SIGNATURE': signature,
    'X-AUTH-APIKEY': api_key,
    'X-AUTH-EPOCH': epoch_time
    }

    response = requests.request("GET", url, headers=headers, json=payload)
    print(response.json())

######################################################################################################################################

def create_order(order_type):
    endpoint = "/trade/api/v2/order"

    payload = {
        "side":order_type,
        "symbol":"XRP/INR",
        "type":"limit",
        "price":26000,
        "quantity":0.0009,
        "exchange":"coinswitchx"
    }
    epoch_time = str(int(time.time() * 1000))
    headers = {
        'Content-Type': 'application/json',
        'X-AUTH-SIGNATURE': get_signature_post(method="POST", endpoint=endpoint, params=None, epoch_time=epoch_time),
        'X-AUTH-APIKEY': api_key
    }

    response = requests.request("POST", GENERAL_ENDPOINT + endpoint, headers=headers, json=payload)

    # response = api_call(endpoint=endpoint, params=None, payload=payload, method="POST")
    print(response.json())

create_order("sell")