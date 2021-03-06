import requests
import yaml

with open("config.yaml", 'r') as yaml_file:
    yaml_config = yaml.load(yaml_file)

BOT = yaml_config['host']

# get
r = requests.get("{}".format(BOT))
print(r)

# get sender
r = requests.post("{}/start".format(BOT))
print(r)

r_json = r.json()
print("sender: {}".format(r_json['channelId']))

# click btn-1
# json_data = {"postback": {"payload": "Btn-1",
#                           "title": "title"},
#            "sender": r_json['channelId'],
#            "recipient": {"id": None}
#             }

# msg
json_data = {"message": {"text": "message", "quick_replies": [], "mid": "mid.1514283239929.941"},
        "sender": r_json['channelId'], "recipient": {"id": None}
        }

r = requests.post("{}/send".format(BOT), json=json_data)
print(r)



