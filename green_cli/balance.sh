#!/bin/sh

docker run -v green-cli:/config green-cli --network testnet-liquid getbalance --subaccount 1 | jq -r .$1
