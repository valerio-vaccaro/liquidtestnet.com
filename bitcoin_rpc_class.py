#    MIT License - Valerio Vaccaro 2018
#    Based on open source code

from __future__ import print_function
import time
import requests
import json
import re


class RPCHost(object):
    def __init__(self, url):
        self._session = requests.Session()
        if re.match(r'.*\.onion/*.*', url):
            self._session.proxies = {}
            self._session.proxies['http'] = 'socks5h://localhost:9050'
            self._session.proxies['https'] = 'socks5h://localhost:9050'
        self._url = url
        self._headers = {'content-type': 'application/json'}

    def call(self, rpcMethod, *params):
        payload = json.dumps(
            {"method": rpcMethod, "params": list(params), "jsonrpc": "2.0"})
        tries = 5
        hadConnectionFailures = False
        while True:
            try:
                response = self._session.post(
                    self._url, headers=self._headers, data=payload)
            except requests.exceptions.ConnectionError:
                tries -= 1
                if tries == 0:
                    raise Exception(
                        'Failed to connect for remote procedure call.')
                hadConnectionFailures = True
                print("Couldn't connect for remote procedure call, will sleep for five seconds and then try again ({} more tries)".format(tries))
                time.sleep(10)
            else:
                if hadConnectionFailures:
                    print('Connected for remote procedure call after retry.')
                break
        if response.status_code not in (200, 500):
            raise Exception('RPC connection failure: ' +
                            str(response.status_code) + ' ' + response.reason)
        responseJSON = response.json()
        if 'error' in responseJSON and responseJSON['error'] is not None:
            raise Exception('Error in RPC call: ' + str(responseJSON['error']))
        return responseJSON['result']
