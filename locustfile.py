from locust import HttpLocust, TaskSet, task
import yaml
import logging
import logging.config
from gevent_bayeux import FanoutClient
import gevent
import time
import random


LOGGING_CONFIG = {
    'formatters': {
        'brief': {
            'format': '[%(asctime)s][%(levelname)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'brief'
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'brief',
            'filename': 'log.log',
            'maxBytes': 1024*1024,
            'backupCount': 3,
        },
    },
    'loggers': {
        'main': {
            'propagate': False,
            'handlers': ['console', 'file'],
            'level': 'INFO'
        }
    },
    'version': 1
}


class CustomTaskSet(TaskSet):

    def __init__(self, parent):
        super(CustomTaskSet, self).__init__(parent)

        self.log = self.parent.log
        if not hasattr(parent, "sender"):
            self.log.error("{}: sender not set!".format(self.__class__.__name__))

        self.headers = {"content-type": "application/json;charset=UTF-8"}
        self.timeout = self.parent.fanout_timeout_cycles
        self.timeout_waits = self.parent.fanout_timeout_waits
        self.subscribed = False

    def post_btn(self, uri, json_data, name, files=None, **kwargs):

        json_data['sender'] = self.parent.sender
        json_data['postback']['payload'] = self.parent.btn_title
        self.log.debug("{}: post_btn: {}".format(name, json_data))

        with self.client.post(uri, json=json_data, headers=self.headers,
                              catch_response=True,
                              files=files) as response:
            self.log.info("{}: post response.status_code: {}, posted json: {}".format(name, response.status_code,
                                                                                  json_data))
            return response

    def post_msg(self, uri, json_data, name, files=None, **kwargs):

        if self.parent.sender:

            json_data['sender'] = self.parent.sender
            self.log.debug("{}: post_msg: {}".format(name, json_data))

            if self.parent.fanout and not self.subscribed:
                self.log.debug("{}: fanout (url, realm): {}, {}".format(name, self.parent.fanout_url,
                                                                        self.parent.fanout_realm))
                self.fc = FanoutClient(self.parent.fanout_url)
                self.fc.subscribe('/' + self.parent.channel_id, 'my_callback')
                self.fc.log = self.log
                self.fc.subscriber = self.parent.channel_id

                gevent.spawn(self.fc._execute_greenlet)
                self.log.info("{}: subscribed by: {} callback: my_callback".format(name, self.parent.channel_id))
                self.subscribed = True
            elif self.subscribed:
                self.log.info("{}: {}: already subscribed".format(name, self.parent.channel_id))
            else:
                self.log.info("{}: {}: fanout disabled".format(name, self.parent.sender))

            with self.client.post(uri, json=json_data, headers=self.headers,
                                  catch_response=True,
                                  files=files) as response:
                self.log.info("{}: post response.status_code: {}, posted json: {}".format(name, response.status_code,
                                                                                      json_data))
            temp_timeout = self.timeout
            if self.parent.fanout:
                while not self.fc.fulfilled:
                    self.log.debug('{}: wait ({}s) for fanout callback, subscriber: {} ({})'.format(name, self.timeout_waits,
                                                                                               self.parent.channel_id, temp_timeout))
                    time.sleep(self.timeout_waits)
                    temp_timeout -= 1
                    if temp_timeout == 0 and not self.fc.calledback:
                        self.log.error("{}: fanout did not respond in time, subscriber: {}".format(name, self.parent.channel_id))
                        break
                    elif temp_timeout == 0 and self.fc.calledback:
                        self.log.info("{}: found no btns to process, subscriber: {}".format(name, self.parent.channel_id))
                        break

                if self.fc.btns:
                    self.log.debug("{}: Processing btns count: {}, subscriber: {}".format(name, len(self.fc.btns),
                                                                                    self.parent.channel_id))

                    json_btn_data = {"postback": {"payload": "{btnTitle}", "title": "title"},
                                     "sender": self.parent.channel_id,
                                     "recipient": {"id": None}
                                }

                    btn = random.choice(self.fc.btns)
                    json_btn_data['postback']['payload'] = btn
                    self.log.info("{}: Processing random btn: {} of choice: {}, subscriber: {}".format(name, btn, self.fc.btns,
                                                                                            self.parent.channel_id))

                    with self.client.post(uri, json=json_btn_data, headers=self.headers,
                                          catch_response=True,
                                          files=files) as response:
                        self.log.info("{}: post response.status_code: {}, posted json_btn_data: {}".format(name, response.status_code,
                                                                                                  json_btn_data))

                    self.fc.btns = []
                    self.fc.fulfilled = False
                    self.fc.calledback = False

        else:
            self.log.debug("{}: sender set to None".format(name))

class Btn(CustomTaskSet):

    @task
    def click_btn(self):

        # e.g. {btnName} = Btn-1
        json = {"postback": {"payload": "{btnName}",
                             "title": "title"},
                "sender": "{sender}",
                "recipient": {"id": None}
                }
        self.post_btn(uri="/send", json_data=json, name=self.__class__.__name__)


class Msg(CustomTaskSet):

    @task
    def send_msg(self):
        json = {"message": {"text": "message", "quick_replies": [], "mid": "mid.1514283239929.941"},
                "sender": "{sender}", "recipient": {"id": None}
                }
        self.post_msg(uri="/send", json_data=json, name=self.__class__.__name__)


class BaseTaskSet(TaskSet):

    # load config
    with open("config.yaml", 'r') as yaml_file:
        yaml_conf = yaml.load(yaml_file)

    # locust tasks
    tasks_conf = yaml_conf['tasks']
    tasks = dict()
    for name, weight in tasks_conf.items():
        if name == "Msg":
            tasks[Msg] = weight
        else:
            tasks[Btn] = weight
            btn_title = name

    # log level, default sender, time out fanout response
    # is fanout enabled
    level = yaml_conf['level']
    fanout_timeout_cycles = yaml_conf['fanout_timeout_cycles']
    fanout_timeout_waits = yaml_conf['fanout_timeout_waits']
    fanout = yaml_conf['fanout']

    def on_start(self):
        self.log = self.parent.log
        self.log.setLevel(level=logging.getLevelName(self.level))
        self.log.debug("{}: tasks: {}".format(self.__class__.__name__, self.tasks_conf))
        self.set_sender()

    def set_sender(self):
        with self.client.post('/start', json=None,
                              catch_response=True) as response:
            if response.status_code != 200:
                self.log.error("{}: /start post response.status_code: {}".format(self.__class__.__name__, response.status_code))
                self.log.error("{}: /start set sender to None - wont continue on")
                self.sender = None
            else:
                response_json = response.json()
                self.sender = response_json['channelId']
                self.log.info("{}: /start sender: {}".format(self.__class__.__name__, self.sender))

                if self.fanout:
                    self.channel_id = response.json()['channelId']
                    self.fanout_realm = response.json()['fanoutRealm']
                    self.fanout_url = 'https://{}.fanoutcdn.com/bayeux'.format(self.fanout_realm)


class Locustio(HttpLocust):
    task_set = BaseTaskSet
    logging.config.dictConfig(LOGGING_CONFIG)
    log = logging.getLogger('main')


class Debug(HttpLocust):
    task_set = BaseTaskSet
    with open("config.yaml", 'r') as yaml_file:
        yaml_conf = yaml.load(yaml_file)
    host = yaml_conf['host']

    logging.config.dictConfig(LOGGING_CONFIG)
    log = logging.getLogger('main')


if __name__ == '__main__':
    Debug().run()