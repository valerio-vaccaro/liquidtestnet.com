#!/bin/sh

# setup green-cli with
#docker run -it -v green-cli:/config green-cli --network testnet-liquid set mnemonic ""
docker run -it -v green-cli:/config green-cli --network testnet-liquid getbalance
docker run -it -v green-cli:/config green-cli --network testnet-liquid getsubaccounts 
