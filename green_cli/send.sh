#!/bin/sh

docker run -v green-cli:/config green-cli --network testnet-liquid sendtoaddress --subaccount 1 $1 $2 $3
