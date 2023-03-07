from flask import (
    Flask,
    request,
    jsonify,
    send_from_directory,
)
from flask_limiter import Limiter
from flask_limiter.util import get_ipaddr
from flask_stache import render_template
from flask_qrcode import QRcode
from bitcoin_rpc_class import RPCHost
import os
import configparser
import json
import requests
import wallycore as wally
from greenaddress import init, Session


app = Flask(__name__, static_url_path='/static')
limiter = Limiter(
    app,
    key_func=get_ipaddr,
    default_limits=["200 per day", "50 per hour"]
)
qrcode = QRcode(app)

config = configparser.RawConfigParser()
config.read('liquid.conf')

liquid_instance = config.get('GENERAL', 'liquid_instance')

rpcHost = config.get(liquid_instance, 'host')
rpcPort = config.get(liquid_instance, 'port')
rpcUser = config.get(liquid_instance, 'username')
rpcPassword = config.get(liquid_instance, 'password')
rpcPassphrase = config.get(liquid_instance, 'passphrase')
rpcWallet = config.get(liquid_instance, 'wallet')

ampUrl =  config.get('AMP', 'url')
ampToken =  config.get('AMP', 'token')
ampUuid = config.get('AMP', 'assetuuid')

gdkMnemonic = config.get('GDK', 'mnemonic')
gdkSubaccount = config.get('GDK', 'subaccount')

if (len(rpcWallet) > 0):
    serverURL = 'http://' + rpcUser + ':' + rpcPassword + '@' + rpcHost + ':' + str(rpcPort) + '/wallet/' + rpcWallet
else:
    serverURL = 'http://' + rpcUser + ':' + rpcPassword + '@' + rpcHost + ':' + str(rpcPort)

host = RPCHost(serverURL)
if (len(rpcPassphrase) > 0):
    result = host.call('walletpassphrase', rpcPassphrase, 60)

@app.route('/.well-known/<path:filename>')
def wellKnownRoute(filename):
    print(app.root_path + '/well-known/' + filename)
    return send_from_directory(app.root_path + '/well-known/', filename, conditional=True)

def stats():
    info = host.call('getblockchaininfo')
    mem = host.call('getmempoolinfo')
    data = {
        'height': info['headers'],
        'mempool': str(mem['size']) + ' tx (' + str(round(mem['size'] / (1024 * 1024), 3)) + ' MB)',
        'space': str(round(info['size_on_disk'] / (1024 * 1024), 3)) + ' MB',
        'uptime': os.popen("uptime").read(),
        'uname': os.popen("uname -a").read(),
    }
    return data


@app.route('/api/stats', methods=['GET'])
@limiter.exempt
def api_stats():
    data = stats()
    return jsonify(data)


@app.route('/', methods=['GET'])
@limiter.exempt
def url_home():
    data = stats()
    return render_template('home', **data)


def explorer(start, last):
    data = []

    for i in range(start, last, -1):
        hash = host.call('getblockhash', i)
        block = host.call('getblock', hash)
        data.append({'id': i, 'hash': hash, 'size': block['size'], 'time': block['time'], 'nTx': block['nTx']})

    return data


@app.route('/api/explorer', methods=['GET'])
@limiter.exempt
def api_explorer():
    elements = 120
    start = request.args.get('start')
    max = host.call('getblockcount')

    try:
        start = int(start)
    except:
        start = max

    if start > max:
        start = max
    last = start - elements

    if (last < 0):
        last = 0

    data = explorer(start, last)
    return jsonify(data)


@app.route('/explorer', methods=['GET'])
@limiter.exempt
def url_explorer():
    elements = 120
    start = request.args.get('start')
    max = host.call('getblockcount')

    try:
        start = int(start)
    except:
        start = max

    if start > max:
        start = max
    last = start - elements

    if (last < 0):
        last = 0

    data = {'blocks_list': explorer(start, last), 'prev': start - elements, 'next': start + elements}
    return render_template('explorer', **data)


def block(height):
    if height is None:
        return {'error': 'missing height'}

    try:
        id = host.call('getblockhash', int(height))
        data = host.call('getblock', id, 2)
    except:
        data = {'error': 'unknown block'}
    return data


@app.route('/api/block', methods=['GET'])
@limiter.exempt
def api_block():
    height = request.args.get('height')
    data = block(height)
    return jsonify(data)


@app.route('/block', methods=['GET'])
@limiter.exempt
def url_block():
    height = request.args.get('height')
    res_block = block(height)
    data = {'block': height, 'result': json.dumps(res_block, indent=4, sort_keys=True), 'transaction_list': res_block['tx']}
    return render_template('block', **data)


def transaction(txid):
    if txid is None:
        return {'error': 'missing txid'}

    if not len(txid) == 64:
        return {'error': 'txid must be of length 64'}

    try:
        data = host.call('getrawtransaction', txid, True)
    except:
        data = {'error': 'unknown txid'}
    return data


@app.route('/api/transaction', methods=['GET'])
@limiter.exempt
def api_transaction():
    txid = request.args.get('txid')
    data = transaction(txid)
    return jsonify(data)


@app.route('/transaction', methods=['GET'])
@limiter.exempt
def url_transaction():
    txid = request.args.get('txid')
    data = {'txid': txid, 'result': json.dumps(transaction(txid), indent=4, sort_keys=True)}
    return render_template('transaction', **data)


def faucet(address, amount):
    if host.call('validateaddress', address)['isvalid']:
        tx = host.call('sendtoaddress', address, amount)
        data = "Sent " + str(amount) + " LBTC to address " + address + " with transaction " + tx + "."
    else:
        data = "Error"
    return data

def faucet_test(address, amount):
    if host.call('validateaddress', address)['isvalid']:
        tx = host.call('sendtoaddress', address, amount, '', '', False, False, 6, 'economical', False, '38fca2d939696061a8f76d4e6b5eecd54e3b4221c846f24a6b279e79952850a5')
        data = "Sent " + str(amount) + " TEST to address " + address + " with transaction " + tx + "."
    else:
        data = "Error"
    return data

def faucet_amp(gaid, amount):
    global s, subaccount

    if subaccount == -1:
        print('Missing subaccount')
        return 'Missing subaccount'

    result = requests.get(f'{ampUrl}assets/{ampUuid}', headers={'content-type': 'application/json', 'Authorization': f'token {ampToken}'}).json()
    assetid = result['asset_id']

    result = requests.get(f'{ampUrl}gaids/{gaid}/validate', headers={'content-type': 'application/json', 'Authorization': f'token {ampToken}'}).json()
    if not result['is_valid']:
        return 'Invalid GAID'

    result = requests.get(f'{ampUrl}gaids/{gaid}/address', headers={'content-type': 'application/json', 'Authorization': f'token {ampToken}'}).json()

    if result['error'] == '' :
        address = result['address']
    else:
        return 'Error in fetching address'

    tx = {
        'subaccount': subaccount,
        'addressees': [{'satoshi': amount, 'address': address, 'asset_id': assetid}],
    }

    utxo_details = {'subaccount': subaccount, 'num_confs': 0}
    utxos = s.get_unspent_outputs(json.dumps(utxo_details)).resolve()
    tx['utxos'] = utxos['unspent_outputs']
    txc = s.create_transaction(json.dumps(tx)).resolve()

    txg = s.sign_transaction(txc).resolve()
    txs = s.send_transaction(txg).resolve()
    print('Transaction sent!')
    print('txhash: {}'.format(txs["txhash"]))
    data = "Sent " + str(amount) + " AMP to address " + address + " with transaction " + txs["txhash"] + "."
    return data


@app.route('/api/faucet', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute')
def api_faucet():
    balance_amp = 0
    global s, subaccount
    try:
        balance_amp = s.get_balance({'subaccount': subaccount, 'num_confs': 0}).resolve()[assetid]
    except:
        pass
    
    balance = host.call('getbalance')['bitcoin']
    balance_test = host.call('getbalance')['38fca2d939696061a8f76d4e6b5eecd54e3b4221c846f24a6b279e79952850a5'] * 100000
    address = request.args.get('address')
    asset = request.args.get('action')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if address is None:
        data = {'result': 'missing address', 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
        return jsonify(data)

    if asset == 'lbtc':
        amount = 0.001
        data = {'result': faucet(address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
    elif asset == 'test':
        amount = 0.00005000
        data = {'result_test': faucet_test(address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
    elif asset == 'amp':
        amount = 1
        data = {'result_amp': faucet_amp(address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
    return jsonify(data)

@app.route('/faucet', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute')
def url_faucet():
    balance_amp = 0
    global s, subaccount
    try:
        result = requests.get(f'{ampUrl}assets/{ampUuid}', headers={'content-type': 'application/json', 'Authorization': f'token {ampToken}'}).json()
        assetid = result['asset_id']
        #balance_amp = s.get_balance({'subaccount': subaccount, 'num_confs': 0}).resolve()[assetid]
        balance_amp = 0
    except Exception as e:
        pass
    balance = host.call('getbalance')['bitcoin']
    balance_test = host.call('getbalance')['38fca2d939696061a8f76d4e6b5eecd54e3b4221c846f24a6b279e79952850a5'] * 100000
    address = request.args.get('address')
    asset = request.args.get('action')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if address is None:
        data = {'result': 'missing address', 'balance': balance, 'balance_test':balance_test, 'balance_amp': balance_amp}
        data['form'] = True
        data['form_test'] = True
        data['form_amp'] = True
        return render_template('faucet', **data)

    if asset == 'lbtc':
        amount = 0.001
        data = {'result': faucet(address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
        data['form'] = False
        data['form_test'] = True
        data['form_amp'] = True
    elif asset == 'test':
        amount = 0.00005000
        data = {'result_test': faucet_test(address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
        data['form'] = True
        data['form_test'] = False
        data['form_amp'] = True
    elif asset == 'amp':
        amount = 1
        data = {'result_amp': faucet_amp(address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
        data['form'] = True
        data['form_test'] = True
        data['form_amp'] = False 
    return render_template('faucet', **data)


def issuer(asset_amount, asset_address, token_amount, token_address, issuer_pubkey, name, ticker, precision, domain):
    data = {}
    version = 0  # don't change
    blind = False
    feerate = 0.00003000

    asset_amount = int(asset_amount) / 10 ** (8 - int(precision))
    token_amount = int(token_amount) / 10 ** (8 - int(precision))

    # Create funded base tx
    base = host.call('createrawtransaction', [], [{'data': '00'}])
    funded = host.call('fundrawtransaction', base, {'feeRate': feerate})

    # Create the contact and calculate the asset id (Needed for asset registry!)
    contract = json.dumps({'name': name,
                           'ticker': ticker,
                           'precision': int(precision),
                           'entity': {'domain': domain},
                           'issuer_pubkey': issuer_pubkey,
                           'version': version}, separators=(',', ':'), sort_keys=True)
    contract_hash = wally.hex_from_bytes(wally.sha256(contract.encode('ascii')))
    data['contract'] = contract

    # Create the rawissuance transaction
    contract_hash_rev = wally.hex_from_bytes(wally.hex_to_bytes(contract_hash)[::-1])
    rawissue = host.call('rawissueasset', funded['hex'], [{'asset_amount': asset_amount,
                                                           'asset_address': asset_address,
                                                           'token_amount': token_amount,
                                                           'token_address': token_address,
                                                           'blind': blind,
                                                           'contract_hash': contract_hash_rev}])

    # Blind the transaction
    blind = host.call('blindrawtransaction', rawissue[0]['hex'], True, [], False)

    # Sign transaction
    signed = host.call('signrawtransactionwithwallet', blind)
    decoded = host.call('decoderawtransaction', signed['hex'])
    data['asset_id'] = decoded['vin'][0]['issuance']['asset']

    # Test transaction
    test = host.call('testmempoolaccept', [signed['hex']])
    if test[0]['allowed'] is True:
        txid = host.call('sendrawtransaction', signed['hex'])
        data['txid'] = txid
        data['registry'] = json.dumps({'asset_id': data['asset_id'], 'contract': json.loads(data['contract'])})

    return data


@app.route('/api/issuer', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute')
def api_issuer():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    command = request.args.get('command')
    if command == 'asset':
        asset_amount = int(request.args.get('asset_amount'))
        asset_address = request.args.get('asset_address')
        token_amount = int(request.args.get('token_amount'))
        token_address = request.args.get('token_address')
        issuer_pubkey = request.args.get('pubkey')
        name = request.args.get('name')
        ticker = request.args.get('ticker')
        precision = request.args.get('precision')
        domain = request.args.get('domain')
        data = issuer(asset_amount, asset_address, token_amount, token_address, issuer_pubkey, name, ticker, precision, domain)
        data['domain'] = domain
        data['name'] = name
    else:
        data = {}
    return jsonify(data)


@app.route('/issuer', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute')
def url_issuer():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    command = request.args.get('command')
    if command == 'asset':
        asset_amount = int(request.args.get('asset_amount'))
        asset_address = request.args.get('asset_address')
        token_amount = int(request.args.get('token_amount'))
        token_address = request.args.get('token_address')
        issuer_pubkey = request.args.get('pubkey')
        name = request.args.get('name')
        ticker = request.args.get('ticker')
        precision = request.args.get('precision')
        domain = request.args.get('domain')
        data = issuer(asset_amount, asset_address, token_amount, token_address, issuer_pubkey, name, ticker, precision, domain)
        data['form'] = False
        data['domain'] = domain
        data['name'] = name
    else:
        data = {}
        data['form'] = True
    return render_template('issuer', **data)


def opreturn(text):
    base = host.call('createrawtransaction', [], [{'data': text}])
    funded = host.call('fundrawtransaction', base)
    blind = host.call('blindrawtransaction', funded['hex'], True, [], False)
    signed = host.call('signrawtransactionwithwallet', blind)
    test = host.call('testmempoolaccept', [signed['hex']])
    if test[0]['allowed'] is True:
        return host.call('sendrawtransaction', signed['hex'])
    return


def test(tx):
    return host.call('testmempoolaccept', [tx])


def broadcast(tx):
    test = host.call('testmempoolaccept', [tx])
    if test[0]['allowed'] is True:
        return host.call('sendrawtransaction', tx)
    return


@app.route('/api/utils', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute')
def api_utils():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    command = request.args.get('command')
    if command == 'opreturn':
        text = request.args.get('text')
        data = {'result_opreturn': opreturn(text)}
    elif command == 'test':
        tx = request.args.get('tx')
        data = {'result_test': test(tx)}
    elif command == 'broadcast':
        tx = request.args.get('tx')
        data = {'result_broadcast': broadcast(tx)}
    else:
        data = {}
    return jsonify(data)


@app.route('/utils', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute')
def url_utils():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    command = request.args.get('command')
    if command == 'opreturn':
        text = request.args.get('text')
        data = {'result_opreturn': opreturn(text)}
        data['form_opreturn'] = False
        data['form_test'] = True
        data['form_broadcast'] = True

    elif command == 'test':
        tx = request.args.get('tx')
        data = {'result_test': test(tx)}
        data['form_opreturn'] = True
        data['form_test'] = False
        data['form_broadcast'] = True

    elif command == 'broadcast':
        tx = request.args.get('tx')
        data = {'result_broadcast': broadcast(tx)}
        data['form_opreturn'] = True
        data['form_test'] = True
        data['form_broadcast'] = False

    else:
        data = {}
        data['form_opreturn'] = True
        data['form_test'] = True
        data['form_broadcast'] = True

    return render_template('utils', **data)


def about():
    data = {}
    return data


@app.route('/api/about', methods=['GET'])
@limiter.exempt
def api_about():
    data = about()
    return jsonify(data)


@app.route('/about', methods=['GET'])
@limiter.exempt
def url_about():
    data = about()
    return render_template('about', **data)


if __name__ == '__main__':
    init({})

    s = Session({"name":"testnet-liquid", "log_level":"info"})
    s.login_user({}, {'mnemonic': gdkMnemonic}).resolve()
    s.change_settings({"unit":"sats"}).resolve()
    subaccount = -1
    subaccounts = s.get_subaccounts().resolve()
    for sub in subaccounts['subaccounts']:
        if sub['name'] == gdkSubaccount:
            if sub['type'] != '2of2_no_recovery':
                pass
            subaccount = sub['pointer']
            break

    app.import_name = '.'
    app.run(host='0.0.0.0', port=8123)
