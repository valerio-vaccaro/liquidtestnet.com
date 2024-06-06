from flask import (
    Flask,
    request,
    jsonify,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_stache import render_template
from flask_qrcode import QRcode
from bitcoin_rpc_class import RPCHost
import os
import configparser
import json
import requests
import wallycore as wally
from lwk import *


app = Flask(__name__, static_url_path='/static')
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
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

ampUrl = config.get('AMP', 'url')
ampToken = config.get('AMP', 'token')
ampUuid = config.get('AMP', 'assetuuid')

lwkMnemonic = config.get('LWK', 'mnemonic')

if (len(rpcWallet) > 0):
    serverURL = 'http://' + rpcUser + ':' + rpcPassword + '@' + \
        rpcHost + ':' + str(rpcPort) + '/wallet/' + rpcWallet
else:
    serverURL = 'http://' + rpcUser + ':' + \
        rpcPassword + '@' + rpcHost + ':' + str(rpcPort)

host = RPCHost(serverURL)
if (len(rpcPassphrase) > 0):
    result = host.call('walletpassphrase', rpcPassphrase, 60)


@app.route('/.well-known/<path:filename>')
def wellKnownRoute(filename):
    assetid = filename[19:]
    data = "Authorize linking the domain name liquidtestnet.com to the Liquid asset " + assetid
    return data


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
        data.append({'id': i, 'hash': hash,
                    'size': block['size'], 'time': block['time'], 'nTx': block['nTx']})

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

    data = {'blocks_list': explorer(
        start, last), 'prev': start - elements, 'next': start + elements}
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
    data = {'block': height, 'result': json.dumps(
        res_block, indent=4, sort_keys=True), 'transaction_list': res_block['tx']}
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
    data = {'txid': txid, 'result': json.dumps(
        transaction(txid), indent=4, sort_keys=True)}
    return render_template('transaction', **data)


def faucet(address, amount):
    if host.call('validateaddress', address)['isvalid']:
        # Call LWK
        builder = network.tx_builder()
        builder.add_lbtc_recipient(Address(address), amount)
        unsigned_pset = builder.finish(wollet)
        signed_pset = signer.sign(unsigned_pset)

        finalized_pset = wollet.finalize(signed_pset)
        tx = finalized_pset.extract_tx()
        txid = client.broadcast(tx)
        data = "Sent " + str(amount) + " LBTC to address " + \
            address + " with transaction " + str(txid) + "."
    else:
        data = "Error"
    return data


def faucet_test(address, amount):
    if host.call('validateaddress', address)['isvalid']:
        # Call LWK
        builder = network.tx_builder()
        builder.add_lbtc_recipient(Address(address), amount)
        unsigned_pset = builder.finish(wollet)
        signed_pset = signer.sign(unsigned_pset)

        finalized_pset = wollet.finalize(signed_pset)
        tx = finalized_pset.extract_tx()
        txid = client.broadcast(tx)
        data = "Sent " + str(amount) + " TEST to address " + \
            address + " with transaction " + str(txid) + "."
    else:
        data = "Error"
    return data


def faucet_amp(gaid, amount):
    data = "TBD"
    return data


@app.route('/api/faucet', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute')
def api_faucet():
    balance_amp = 0
    balance = wollet.balance().get(network.policy_asset(), 0)
    balance_test = wollet.balance().get(
        '38fca2d939696061a8f76d4e6b5eecd54e3b4221c846f24a6b279e79952850a5', 0)
    address = request.args.get('address')
    asset = request.args.get('action')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if address is None:
        data = {'result': 'missing address', 'balance': balance,
                'balance_test': balance_test, 'balance_amp': balance_amp}
        return jsonify(data)

    if asset == 'lbtc':
        amount = 100000
        data = {'result': faucet(address, amount), 'balance': balance,
                'balance_test': balance_test, 'balance_amp': balance_amp}
    elif asset == 'test':
        amount = 5000
        data = {'result_test': faucet_test(
            address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
    elif asset == 'amp':
        amount = 1
        data = {'result_amp': faucet_amp(
            address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
    return jsonify(data)


@app.route('/faucet', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute')
def balance_amp = 0
    balance = wollet.balance().get(network.policy_asset(), 0)
    balance_test = wollet.balance().get(
        '38fca2d939696061a8f76d4e6b5eecd54e3b4221c846f24a6b279e79952850a5', 0)
    address = request.args.get('address')
    asset = request.args.get('action')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if address is None:
        data = {'result': 'missing address', 'balance': balance,
                'balance_test': balance_test, 'balance_amp': balance_amp}
        data['form'] = True
        data['form_test'] = True
        data['form_amp'] = True
        return render_template('faucet', **data)

    if asset == 'lbtc':
        amount = 100000
        data = {'result': faucet(address, amount), 'balance': balance,
                'balance_test': balance_test, 'balance_amp': balance_amp}
        data['form'] = False
        data['form_test'] = True
        data['form_amp'] = True
    elif asset == 'test':
        amount = 5000
        data = {'result_test': faucet_test(
            address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
        data['form'] = True
        data['form_test'] = False
        data['form_amp'] = True
    elif asset == 'amp':
        amount = 1
        data = {'result_amp': faucet_amp(
            address, amount), 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
        data['form'] = True
        data['form_test'] = True
        data['form_amp'] = False
    return render_template('faucet', **data)


def issuer(asset_amount, asset_address, token_amount, token_address, issuer_pubkey, name, ticker, precision, domain):
    data = {}
    version = 0  # don't change
    blind = False
    
    asset_amount = int(asset_amount) / 10 ** (8 - int(precision))
    
    data['contract'] = "{}"
    data['asset_id'] = ""
    data['txid'] = ""
     data['registry'] = json.dumps(
            {'asset_id': data['asset_id'], 'contract': json.loads(data['contract'])})

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
        data = issuer(asset_amount, asset_address, token_amount,
                      token_address, issuer_pubkey, name, ticker, precision, domain)
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
        data = issuer(asset_amount, asset_address, token_amount,
                      token_address, issuer_pubkey, name, ticker, precision, domain)
        data['form'] = False
        data['domain'] = domain
        data['name'] = name
    else:
        data = {}
        data['form'] = True
    return render_template('issuer', **data)


def opreturn(text):
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
    mnemonic = Mnemonic(str(lwkMnemonic))
    network = Network.testnet()
    client = network.default_electrum_client()

    signer = Signer(mnemonic, network)
    desc = signer.wpkh_slip77_descriptor()

    wollet = Wollet(network, desc, datadir=None)
    update = client.full_scan(wollet)
    wollet.apply_update(update)

    app.import_name = '.'
    app.run(host='0.0.0.0', port=8123)
