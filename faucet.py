from flask import (
    Flask,
    request,
    jsonify,
    Response,
    send_from_directory,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_stache import render_template as _render_template
from flask_qrcode import QRcode
from bitcoin_rpc_class import RPCHost
import os
import configparser
import json
import requests
import subprocess
import time
from lwk import *
from werkzeug.middleware.proxy_fix import ProxyFix


def get_version():
    try:
        return subprocess.check_output(
            ['git', 'describe', '--tags', '--exact-match'],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        return 'dev'


APP_VERSION = get_version()


def render_template(template, **context):
    context.setdefault('app_version', APP_VERSION)
    return _render_template(template, **context)


app = Flask(__name__, static_url_path='/static')
app.wsgi_app = ProxyFix(
    app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1
)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

qrcode = QRcode(app)

PUBLIC_ORIGIN = 'https://liquidtestnet.com'
INDEXABLE_PATHS = ('/', '/explorer', '/mempool', '/faucet', '/issuer', '/utils', '/apidocs', '/about')

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

amp0_user = config.get('GDK', 'amp0_user')
amp0_password = config.get('GDK', 'amp0_password')
amp0_assetid = config.get('GDK', 'amp0_assetid')
amp0_mnemonic = config.get('GDK', 'mnemonic')

lwkMnemonic = config.get('LWK', 'mnemonic')
lwkAddress = config.get('LWK', 'address')
assetid = config.get('LWK', 'assetid')

if (len(rpcWallet) > 0):
    serverURL = 'http://' + rpcUser + ':' + rpcPassword + '@' + \
        rpcHost + ':' + str(rpcPort) + '/wallet/' + rpcWallet
else:
    serverURL = 'http://' + rpcUser + ':' + \
        rpcPassword + '@' + rpcHost + ':' + str(rpcPort)

host = RPCHost(serverURL)
if (len(rpcPassphrase) > 0):
    result = host.call('walletpassphrase', rpcPassphrase, 60)

def index_ratelimit_error_responder(request_limit):
    return jsonify({"error": "rate_limit_exceeded"})


@app.errorhandler(429)
def ratelimit_handler(e):
    if request.path.startswith('/api/'):
        return jsonify({"error": "rate_limit_exceeded", "message": e.description}), 429
    return render_template(
        'error',
        title='Too many requests',
        message='You have made too many requests (limit: %s). Please wait a moment and try again.' % e.description,
    ), 429


@app.route('/robots.txt')
@limiter.exempt
def robots_txt():
    r = Response(response="""User-agent: *
Allow: /
Disallow: /api/
Disallow: /block
Disallow: /transaction
Disallow: /openapi.json

Sitemap: https://liquidtestnet.com/sitemap.xml
""", status=200, mimetype="text/plain")
    r.headers["Content-Type"] = "text/plain; charset=utf-8"
    return r


@app.route('/sitemap.xml')
@limiter.exempt
def sitemap_xml():
    urls = ''.join(
        '  <url><loc>{}{}</loc></url>\n'.format(PUBLIC_ORIGIN, path)
        for path in INDEXABLE_PATHS
    )
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           '{}'
           '</urlset>\n').format(urls)
    return Response(xml, mimetype='application/xml')


@app.route('/site.webmanifest')
@limiter.exempt
def webmanifest():
    return send_from_directory(app.static_folder, 'site.webmanifest', mimetype='application/manifest+json')


@app.route('/favicon.ico')
@limiter.exempt
def favicon():
    return send_from_directory(app.static_folder, 'favicon.ico', mimetype='image/x-icon')


@app.after_request
def search_engine_headers(response):
    """Keep API responses and parameterized explorer pages out of search results."""
    if (request.path.startswith('/api/') or request.path in ('/block', '/transaction', '/openapi.json')
            or (request.path in ('/faucet', '/issuer', '/utils') and request.args)):
        response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    elif request.path in INDEXABLE_PATHS and not request.args:
        response.headers.add('Link', '<{}{}>; rel="canonical"'.format(PUBLIC_ORIGIN, request.path))
    return response


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


def mempool():
    data = host.call('getrawmempool')
    return data


@app.route('/api/mempool', methods=['GET'])
@limiter.exempt
def api_mempool():
    data = mempool()
    return jsonify(data)


@app.route('/mempool', methods=['GET'])
@limiter.exempt
def url_mempool():
    height = request.args.get('height')
    mem = mempool()
    data = {'transaction_list': mem}
    return render_template('mempool', **data)


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


def sync():
    global last_update_or_tx
    if time.time() - last_update_or_tx > 2:
        update = client.full_scan(wollet)
        wollet.apply_update(update)
        last_update_or_tx = time.time()


def faucet_asset(address, amount, asset):
    validate_res = host.call('validateaddress', address)
    if validate_res['isvalid']:
        # Call LWK
        sync()
        builder = network.tx_builder()
        if validate_res['confidential_key'] == '':
            builder.add_explicit_recipient(Address(address), amount, asset)
        else:
            builder.add_recipient(Address(address), amount, asset)
        unsigned_pset = builder.finish(wollet)
        signed_pset = signer.sign(unsigned_pset)

        finalized_pset = wollet.finalize(signed_pset)
        tx = finalized_pset.extract_tx()
        txid = client.broadcast(tx)
        wollet.apply_transaction(tx)
        message = "Sent " + str(amount) + " sats to address " + \
            address + " with transaction " + str(txid) + "."
        return {"success": True, "message": message, "txid": str(txid)}
    else:
        return {"success": False, "message": "Error"}


def faucet_amp(gaid, amount):
    result = requests.get(f'{ampUrl}gaids/{gaid}/validate', headers={
                          'content-type': 'application/json', 'Authorization': f'token {ampToken}'}).json()
    if not result['is_valid']:
        return {"success": False, "message": "Invalid GAID"}
    result = requests.get(f'{ampUrl}gaids/{gaid}/address', headers={
                          'content-type': 'application/json', 'Authorization': f'token {ampToken}'}).json()
    if result['error'] == '':
        address = result['address']
    else:
        return {"success": False, "message": "Error in fetching address"}

    # Update amp0 wallet
    last_index = amp0.last_index()
    update = amp0_client.full_scan_to_index(amp0_wollet, last_index)
    amp0_wollet.apply_update(update)

    # Create transaction
    builder = network.tx_builder()
    builder.add_recipient(Address(address), amount, amp0_assetid)
    amp0pset = builder.finish_for_amp0(amp0_wollet)
   
    # Create the signer
    amp0_signer = Signer(Mnemonic(amp0_mnemonic), network)
    
    # Sign with the user key
    pset = amp0pset.pset()
    pset = amp0_signer.sign(pset)

    # Ask AMP0 to cosign
    amp0pset = Amp0Pset(pset, amp0pset.blinding_nonces())
    tx = amp0.sign(amp0pset)

    # Broadcast
    txid = amp0_client.broadcast(tx)

    message = "Sent " + str(amount) + " AMP ASSET to address " + \
        address + " with transaction " + str(txid)  + "."
    return {"success": True, "message": message, "txid": str(txid)}


@app.route('/api/faucet', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute',  on_breach=index_ratelimit_error_responder)
def api_faucet():
    balance_amp = amp0_wollet.balance().get(amp0_assetid, 0)
    balance = wollet.balance().get(network.policy_asset(), 0)
    balance_test = wollet.balance().get(assetid, 0)
    address = request.args.get('address')
    asset = request.args.get('action')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    if address is None:
        data = {'result': 'missing address', 'balance': balance,
                'balance_test': balance_test, 'balance_amp': balance_amp}
        return jsonify(data)

    try:
        if asset == 'lbtc':
            amount = 100000
            res = faucet_asset(address, amount, network.policy_asset())
            data = {'result': res['message'], 'balance': balance,
                    'balance_test': balance_test, 'balance_amp': balance_amp}
            if 'txid' in res: data['txid'] = res['txid']

        elif asset == 'test':
            amount = 5000
            res = faucet_asset(address, amount, assetid)
            data = {'result_test': res['message'], 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
            if 'txid' in res: data['txid'] = res['txid']

        elif asset == 'amp':
            amount = 1
            res = faucet_amp(address, amount)
            data = {'result_amp': res['message'], 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
            if 'txid' in res: data['txid'] = res['txid']
        return jsonify(data)
    except Exception as e:
        data = {'result': 'error', 'error': str(e)}
        return jsonify(data)


@app.route('/faucet', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute')
def url_faucet():
    balance_amp = amp0_wollet.balance().get(amp0_assetid, 0)
    balance = wollet.balance().get(network.policy_asset(), 0)
    balance_test = wollet.balance().get(assetid, 0)
    address = request.args.get('address')
    asset = request.args.get('action')
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)

    try:
        if address is None:
            data = {'result': 'missing address', 'balance': balance,
                    'balance_test': balance_test, 'balance_amp': balance_amp}
            data['form'] = True
            data['form_test'] = True
            data['form_amp'] = True
            data['assetid'] = assetid
            data['amp0_assetid'] = amp0_assetid
            data['return_address'] = return_address
            data['amp0_return_address'] = amp0_return_address
            return render_template('faucet', **data)

        if asset == 'lbtc':
            amount = 100000
            res = faucet_asset(address, amount, network.policy_asset())
            data = {'result': res['message'], 'balance': balance,
                    'balance_test': balance_test, 'balance_amp': balance_amp}
            data['faucet_success'] = res['success']
            data['form'] = False
            data['form_test'] = True
            data['form_amp'] = True
        elif asset == 'test':
            amount = 5000
            res = faucet_asset(address, amount, assetid)
            data = {'result_test': res['message'], 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
            data['faucet_success'] = res['success']
            data['form'] = True
            data['form_test'] = False
            data['form_amp'] = True
        elif asset == 'amp':
            amount = 1
            res = faucet_amp(address, amount)
            data = {'result_amp': res['message'], 'balance': balance, 'balance_test': balance_test, 'balance_amp': balance_amp}
            data['faucet_success'] = res['success']
            data['form'] = True
            data['form_test'] = True
            data['form_amp'] = False

        data['assetid'] = assetid
        data['amp0_assetid'] = amp0_assetid
        data['return_address'] = return_address
        data['amp0_return_address'] = amp0_return_address
        return render_template('faucet', **data)
    except Exception as e:
        data = {'result': 'error ' + str(e), 'balance': balance,
                    'balance_test': balance_test, 'balance_amp': balance_amp}
        data['form'] = True
        data['form_test'] = True
        data['form_amp'] = True
        data['assetid'] = assetid
        data['amp0_assetid'] = amp0_assetid
        data['return_address'] = return_address
        data['amp0_return_address'] = amp0_return_address
        return render_template('faucet', **data)


def issuer(asset_amount, asset_address, token_amount, token_address, issuer_pubkey, name, ticker, precision, domain):
    data = {}
    version = 0  # don't change
    blind = False

    # Convert amount in satoshi
    asset_amount = int(asset_amount) * 10 ** int(precision)

    # Call LWK
    sync()

    contract = Contract(domain=domain, issuer_pubkey=issuer_pubkey,
                        name=name, precision=int(precision), ticker=ticker, version=version)
    issued_asset = asset_amount
    reissuance_tokens = token_amount
    builder = network.tx_builder()
    builder.issue_asset(int(issued_asset), Address(asset_address),
                        int(reissuance_tokens), Address(token_address), contract)
    unsigned_pset = builder.finish(wollet)
    signed_pset = signer.sign(unsigned_pset)
    finalized_pset = wollet.finalize(signed_pset)
    tx = finalized_pset.extract_tx()
    txid = client.broadcast(tx)
    wollet.apply_transaction(tx)

    asset_id = signed_pset.inputs()[0].issuance_asset()
    token_id = signed_pset.inputs()[0].issuance_token()

    data['contract'] = str(contract)
    data['asset_id'] = str(asset_id)
    data['token_id'] = str(token_id)
    data['txid'] = str(txid)
    data['registry'] = json.dumps(
        {'asset_id': data['asset_id'], 'contract': json.loads(data['contract'])})

    return data


@app.route('/api/issuer', methods=['GET'])
@limiter.limit('1000/day;100/hour;3/minute',  on_breach=index_ratelimit_error_responder)
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
@limiter.exempt
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


RATE_LIMIT_RESPONSE = {
    'description': 'Rate limit exceeded',
    'content': {
        'application/json': {
            'schema': {
                'type': 'object',
                'properties': {
                    'error': {'type': 'string', 'example': 'rate_limit_exceeded'},
                    'message': {'type': 'string', 'example': '3 per 1 minute'},
                },
            }
        }
    },
}


def build_openapi_spec():
    return {
        'openapi': '3.0.3',
        'info': {
            'title': 'Liquid testnet API',
            'description': 'Read-only explorer data and faucet/issuer actions for the Liquid testnet.',
            'version': APP_VERSION,
            'license': {'name': 'MIT', 'url': 'https://github.com/valerio-vaccaro/liquidtestnet.com/blob/main/LICENSE'},
        },
        'servers': [{'url': request.url_root.rstrip('/')}],
        'paths': {
            '/api/stats': {
                'get': {
                    'summary': 'Node statistics',
                    'tags': ['General'],
                    'responses': {
                        '200': {
                            'description': 'Chain and host statistics',
                            'content': {'application/json': {'schema': {
                                'type': 'object',
                                'properties': {
                                    'height': {'type': 'integer', 'example': 2521389},
                                    'mempool': {'type': 'string', 'example': '4 tx (0.0 MB)'},
                                    'space': {'type': 'string', 'example': '4400.69 MB'},
                                    'uptime': {'type': 'string'},
                                    'uname': {'type': 'string'},
                                },
                            }}},
                        }
                    },
                }
            },
            '/api/explorer': {
                'get': {
                    'summary': 'List recent blocks',
                    'tags': ['Explorer'],
                    'parameters': [
                        {
                            'name': 'start',
                            'in': 'query',
                            'required': False,
                            'schema': {'type': 'integer'},
                            'description': 'Block height to start from (descending). Defaults to the current tip.',
                        }
                    ],
                    'responses': {
                        '200': {
                            'description': 'Up to 120 blocks, newest first',
                            'content': {'application/json': {'schema': {
                                'type': 'array',
                                'items': {
                                    'type': 'object',
                                    'properties': {
                                        'id': {'type': 'integer'},
                                        'hash': {'type': 'string'},
                                        'size': {'type': 'integer'},
                                        'time': {'type': 'integer'},
                                        'nTx': {'type': 'integer'},
                                    },
                                },
                            }}},
                        }
                    },
                }
            },
            '/api/block': {
                'get': {
                    'summary': 'Get a block by height',
                    'tags': ['Explorer'],
                    'parameters': [
                        {
                            'name': 'height',
                            'in': 'query',
                            'required': True,
                            'schema': {'type': 'integer'},
                        }
                    ],
                    'responses': {
                        '200': {
                            'description': 'Block data (Elements `getblock` verbosity 2), or an error object',
                            'content': {'application/json': {'schema': {'type': 'object', 'additionalProperties': True}}},
                        }
                    },
                }
            },
            '/api/mempool': {
                'get': {
                    'summary': 'List mempool transaction ids',
                    'tags': ['Explorer'],
                    'responses': {
                        '200': {
                            'description': 'Raw mempool txids',
                            'content': {'application/json': {'schema': {'type': 'array', 'items': {'type': 'string'}}}},
                        }
                    },
                }
            },
            '/api/transaction': {
                'get': {
                    'summary': 'Get a transaction by txid',
                    'tags': ['Explorer'],
                    'parameters': [
                        {
                            'name': 'txid',
                            'in': 'query',
                            'required': True,
                            'schema': {'type': 'string', 'minLength': 64, 'maxLength': 64},
                        }
                    ],
                    'responses': {
                        '200': {
                            'description': 'Transaction data (Elements `getrawtransaction` verbose), or an error object',
                            'content': {'application/json': {'schema': {'type': 'object', 'additionalProperties': True}}},
                        }
                    },
                }
            },
            '/api/faucet': {
                'get': {
                    'summary': 'Request testnet L-BTC, the TEST asset, or an AMP asset',
                    'tags': ['Faucet'],
                    'parameters': [
                        {
                            'name': 'address',
                            'in': 'query',
                            'required': False,
                            'schema': {'type': 'string'},
                            'description': 'Destination address. Omit to only fetch current faucet balances.',
                        },
                        {
                            'name': 'action',
                            'in': 'query',
                            'required': False,
                            'schema': {'type': 'string', 'enum': ['lbtc', 'test', 'amp']},
                            'description': 'lbtc: 100000 sats. test: 5000 sats of the TEST asset. amp: 1 unit of the AMP asset (address is a GAID).',
                        },
                    ],
                    'responses': {
                        '200': {
                            'description': 'Balances plus a result message, and a txid on success',
                            'content': {'application/json': {'schema': {
                                'type': 'object',
                                'properties': {
                                    'result': {'type': 'string'},
                                    'result_test': {'type': 'string'},
                                    'result_amp': {'type': 'string'},
                                    'balance': {'type': 'integer'},
                                    'balance_test': {'type': 'integer'},
                                    'balance_amp': {'type': 'integer'},
                                    'txid': {'type': 'string'},
                                },
                            }}},
                        },
                        '429': RATE_LIMIT_RESPONSE,
                    },
                }
            },
            '/api/issuer': {
                'get': {
                    'summary': 'Issue a new Liquid testnet asset',
                    'tags': ['Issuer'],
                    'parameters': [
                        {'name': 'command', 'in': 'query', 'required': True, 'schema': {'type': 'string', 'enum': ['asset']}},
                        {'name': 'asset_amount', 'in': 'query', 'required': True, 'schema': {'type': 'integer'}},
                        {'name': 'asset_address', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'token_amount', 'in': 'query', 'required': True, 'schema': {'type': 'integer'}},
                        {'name': 'token_address', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'pubkey', 'in': 'query', 'required': True, 'schema': {'type': 'string'}, 'description': 'Issuer public key'},
                        {'name': 'name', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'ticker', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                        {'name': 'precision', 'in': 'query', 'required': True, 'schema': {'type': 'integer'}},
                        {'name': 'domain', 'in': 'query', 'required': True, 'schema': {'type': 'string'}},
                    ],
                    'responses': {
                        '200': {
                            'description': 'The issued asset/token ids and registry entry, or an empty object if `command` was omitted',
                            'content': {'application/json': {'schema': {
                                'type': 'object',
                                'properties': {
                                    'contract': {'type': 'string'},
                                    'asset_id': {'type': 'string'},
                                    'token_id': {'type': 'string'},
                                    'txid': {'type': 'string'},
                                    'registry': {'type': 'string'},
                                    'domain': {'type': 'string'},
                                    'name': {'type': 'string'},
                                },
                            }}},
                        },
                        '429': RATE_LIMIT_RESPONSE,
                    },
                }
            },
            '/api/utils': {
                'get': {
                    'summary': 'Write an OP_RETURN phrase, test-mempool-accept, or broadcast a raw transaction',
                    'tags': ['Utils'],
                    'parameters': [
                        {'name': 'command', 'in': 'query', 'required': True, 'schema': {'type': 'string', 'enum': ['opreturn', 'test', 'broadcast']}},
                        {'name': 'text', 'in': 'query', 'required': False, 'schema': {'type': 'string'}, 'description': 'Hex phrase, used with command=opreturn'},
                        {'name': 'tx', 'in': 'query', 'required': False, 'schema': {'type': 'string'}, 'description': 'Raw transaction hex, used with command=test or command=broadcast'},
                    ],
                    'responses': {
                        '200': {
                            'description': 'Result of the requested command, or an empty object if `command` was omitted',
                            'content': {'application/json': {'schema': {'type': 'object', 'additionalProperties': True}}},
                        }
                    },
                }
            },
            '/api/about': {
                'get': {
                    'summary': 'About endpoint (reserved)',
                    'tags': ['General'],
                    'responses': {
                        '200': {
                            'description': 'Currently always an empty object',
                            'content': {'application/json': {'schema': {'type': 'object'}}},
                        }
                    },
                }
            },
        },
    }


@app.route('/openapi.json', methods=['GET'])
@limiter.exempt
def openapi_json():
    return jsonify(build_openapi_spec())


@app.route('/apidocs', methods=['GET'])
@limiter.exempt
def url_apidocs():
    return render_template('apidocs')


@app.route('/about', methods=['GET'])
@limiter.exempt
def url_about():
    data = about()
    return render_template('about', **data)


if __name__ == '__main__':
    mnemonic = Mnemonic(str(lwkMnemonic))
    network = Network.testnet()
    b = EsploraClientBuilder(
        base_url="https://waterfalls.liquidwebwallet.org/liquidtestnet/api",
        network=network,
        waterfalls=True,
        utxo_only=True,
    )
    client = EsploraClient.from_builder(b)

    signer = Signer(mnemonic, network)
    desc = signer.wpkh_slip77_descriptor()

    wollet = Wollet(network, desc, datadir="./.lwk_data")
    update = client.full_scan(wollet)
    wollet.apply_update(update)
    # here we initialize a global variable (since we're in "main")
    # that will be updated later
    last_update_or_tx = time.time()

    return_address = str(wollet.address(1).address())

    print(wollet.balance())

    # amp0 wallet
    amp_id = ""
    amp0 = Amp0(network, amp0_user, amp0_password, amp_id)

    amp0_desc =  amp0.wollet_descriptor()
    amp0_wollet = Wollet(network, amp0_desc, datadir='./.lwk_data_amp0')
    b2 = EsploraClientBuilder(
        base_url="https://waterfalls.liquidwebwallet.org/liquidtestnet/api",
        network=network,
        waterfalls=True,
        utxo_only=True,
    )
    amp0_client = EsploraClient.from_builder(b2)
    last_index = amp0.last_index()
    update = amp0_client.full_scan_to_index(amp0_wollet, last_index)
    amp0_wollet.apply_update(update)

    amp0_return_address = str(amp0.address(1).address())

    print(amp0_wollet.balance())

    # Start app
    app.import_name = '.'
    app.run(host='0.0.0.0', port=8123)
