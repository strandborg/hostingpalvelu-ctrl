import re
from bs4 import BeautifulSoup
import requests
import json
import sys
import base64
import typer


# Function to decode base64 fields
def decode_base64_fields(obj, alreadyb64 = False):
    if isinstance(obj, dict):
        for key, value in obj.items():
            dob64 = alreadyb64
            if(key.endswith("_b64")):
                dob64 = True
            if isinstance(value, dict) or isinstance(value, list):
                decode_base64_fields(value, dob64)
            elif isinstance(value, str) and dob64:
                obj[key] = base64.b64decode(value).decode("utf-8")
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            if isinstance(item, str):
                obj[index] = base64.b64decode(item).decode("utf-8")
            else:
                decode_base64_fields(item, alreadyb64)


def main(username: str, password: str, zone: str, record: str, value: str):

    session = requests.Session()
    #with requests.Session() as session:
    response = session.get('https://www.hostingpalvelu.fi/asiakkaat/index.php?rp=/login')

    soup = BeautifulSoup(response.text, "html.parser")

    token = ""

    token_input = soup.find("input", {"type": "hidden", "name": "token"})
    if token_input:
        token = token_input["value"]
        print("Found token: " + token)
    else:
        sys.exit("Token input not found.")
        


    # Login
    logindata = { "token": token, "username": username, "password": password }
    response = session.post("https://www.hostingpalvelu.fi/asiakkaat/index.php?rp=/login", data=logindata)

    # Login to cPanel
    response = session.get("https://www.hostingpalvelu.fi/asiakkaat/clientarea.php?action=productdetails&id=45468&dosinglesignon=1")

    cpSession = re.search(r'cpsess(\d+)', response.url).group(1) if re.search(r'cpsess(\d+)', response.url) else sys.exit("cPanel session not found")

    print("Found cpSession: "+cpSession)

    response = session.post("https://cloud30.hostingpalvelu.fi:2083/cpsess"+cpSession+"/execute/DNS/parse_zone", data= {"zone": zone})

    if response.status_code != 200:
        sys.exit("cPanel login failed")

    zoneJson = json.loads(response.text)

    decode_base64_fields(zoneJson)

    soaRecord = next((item for item in zoneJson["data"] if item.get("record_type") == "SOA"), None)
    if soaRecord == None:
        raise Exception("No SOA record found")

    oldSerial = soaRecord["data_b64"][2]
    print("Current serial: " + oldSerial)

    currRecord = next((item for item in zoneJson["data"] if item.get("dname_b64") == record), None)
    if currRecord == None:
        raise Exception("No existing record found with name: " + record)

    editData = {
        "dname" : record,
        "ttl" : currRecord["ttl"],
        "record_type": currRecord["record_type"],
        "line_index": currRecord["line_index"],
        "data": [value]
    }

    response = session.post("https://cloud30.hostingpalvelu.fi:2083/cpsess"+cpSession+"/execute/DNS/mass_edit_zone", data= {"zone": zone, "serial": oldSerial, "edit": json.dumps(editData)})
    if response.status_code != 200:
        sys.exit("Edit zone failed")

    print(response.text)
    #print(json.dumps(zoneJson, indent=4))

if __name__ == "__main__":
    typer.run(main)
