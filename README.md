### locust 


* ```pip install locust ```
* ```pip install "requests[security]"```

#### run:
locust --host=https://xxxx.yyyyy.com/webchat/zwN4p


### chat_request.py
* rename config.yaml.template to config.yaml
* in yaml, add bot url e.g. url: https://xxxx.yyyyy.com/webchat/zwN4pSUU
* to get default_sender run: chat_request.py
