from datetime import datetime
import requests

payload = str(datetime.utcnow()).encode("utf-8").hex()
r = requests.get(
    f'https://liquidtestnet.com/api/utils?command=opreturn&text={payload}&action=send')
print(r.json())
