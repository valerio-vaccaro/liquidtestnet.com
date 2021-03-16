# Liquidtestnet.com

## Install
Create a virtual env and install python requirements.

```
virtualenv -p python3 venv3
. venv3/bin/activate
pip install -r requirements.txt
deactivate
```

## Configure
Create a configuration file called liquid.conf with the following structure and fill with an element node rpc configuration.

```
[GENERAL]
liquid_instance: LIQUID

[LIQUID]
host:
port:
username:
password:
wallet:
passphrase:
```

## Run
Start the faucet.

```
. venv3/bin/activate
python faucet.py
deactivate
```
