### install


* ```pip install locust ```
* ```pip install "requests[security]"```
* [python-bayeux](https://github.com/SalesforceFoundation/python-bayeux/)

#### run:
locust --host=https://xxxx.yyyyy.com/webchat/zwN4p


### locustfile.py

## settings:
* ```fanout: True/False``` - whether to enable or disable fanout
* ```fanout_timeout_cycles: 10, fanout_timeout_waits: 0.5``` - time to wait for fanout to respond with a callback and fulfill (find btns) requirement,
e.g. 10 iterations of 500 ms (5 secs)
* ```tasks:```: set locusts tasks

usual scenario:
send msg, wait for fanout to respond, parse btn, randomly choose one and post it
```
tasks:
  Msg: 100
```

customized scenario:
send msg, wait for fanout to respond, parse btn, randomly choose one and post it,
additionally knowing a button title upfront, for every 10 post messages, post one
btn with title "Book it". We could add more buttons to act upon e.g Btn-1, Btn-2
```
tasks:
  Book it: 1
  Msg: 10
```

### chat_request.py (help file)
* rename config.yaml.template to config.yaml
* in yaml, add bot url e.g. ```host: https://xxxx.yyyyy.com/webchat/zwN4pSUU```


### Run from IDE
Comment in:

```
# class Debug(HttpLocust):
#     task_set = BaseTaskSet
#     with open("config.yaml", 'r') as yaml_file:
#         yaml_conf = yaml.load(yaml_file)
#     host = yaml_conf['host']
#
#     logging.config.dictConfig(LOGGING_CONFIG)
#     log = logging.getLogger('main')
#
#
# if __name__ == '__main__':
#     Debug().run()
```


