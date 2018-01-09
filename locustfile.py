from locust import HttpLocust, TaskSet, task
import yaml
import logging
import logging.config
from gevent_bayeux import FanoutClient
import gevent
import random
from random import randint


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
            self.log.error("%s: sender not set!", self.__class__.__name__)

        self.headers = {"content-type": "application/json;charset=UTF-8"}
        self.timeout = self.parent.fanout_timeout_cycles
        self.timeout_waits = self.parent.fanout_timeout_waits
        self.subscribed = False

    def post_btn(self, uri, json_data, name, files=None, **kwargs):

        json_data['sender'] = self.parent.sender
        json_data['postback']['payload'] = self.parent.btn_title
        self.log.debug("%s: post_btn: %s", name, json_data)

        with self.client.post(uri, json=json_data, headers=self.headers,
                              catch_response=True,
                              files=files) as response:
            self.log.info("%s: post response.status_code: %s, posted json: %s", name, response.status_code, json_data)
            return response

    def process_fanout_callbacks(self, uri, name):

        temp_timeout = self.timeout

        while not self.fc.fulfilled:

            self.log.debug("%s: wait (%d) for fanout callback fulfilled, subscriber: %s, counter: (%d)", name, self.timeout_waits,
                           self.parent.channel_id, temp_timeout)
            self.fc.process_queue_items()

            gevent.sleep(self.timeout_waits)
            temp_timeout -= 1
            if temp_timeout == 0 and not self.fc.calledback:
                self.log.error(
                    "%s: fanout did not respond in time, subscriber: %s", name, self.parent.channel_id)
                break
            elif temp_timeout == 0 and self.fc.calledback:
                self.log.info("%s: found no btns to process, subscriber: %s", name, self.parent.channel_id)
                break

        if self.fc.btns and self.fc.fulfilled:
            self.post_random_btn(uri, name)

    def post_random_btn(self, uri, name):

        self.log.debug("%s: Processing btns count: %d, subscriber: %s", name, len(self.fc.btns),
                                                                              self.parent.channel_id)

        json_btn_data = {"postback": {"payload": "{btnTitle}", "title": "{title}"},
                         "sender": self.parent.channel_id,
                         "recipient": {"id": None}
                         }

        btn = random.choice(self.fc.btns)
        json_btn_data['postback']['payload'] = btn
        json_btn_data['postback']['title'] = btn
        self.log.info("%s: Processing random btn: %s of choice: %s, subscriber: %s", name, btn, self.fc.btns,
                                                                                           self.parent.channel_id)

        with self.client.post(uri, json=json_btn_data, headers=self.headers,
                              catch_response=True) as response:
            self.log.info("%s: post response.status_code: %d, posted json_btn_data: %s", name, response.status_code,
                                                                                     json_btn_data)
        self.fc.btns = []
        self.fc.fulfilled = False

    def post_msg(self, uri, json_data, name, files=None, **kwargs):

        if self.parent.sender:

            json_data['sender'] = self.parent.sender
            self.log.debug("%s: post_msg: %s",name, json_data)

            if self.parent.fanout and not self.subscribed:
                self.log.debug("%s: fanout (url, realm): %s, %s", name, self.parent.fanout_url,
                                                                        self.parent.fanout_realm)
                self.fc = FanoutClient(self.parent.fanout_url)
                self.fc.subscribe('/' + self.parent.channel_id, 'my_callback')
                self.fc.log = self.log
                self.fc.subscriber = self.parent.channel_id

                gevent.spawn(self.fc._execute_greenlet)
                self.log.info("%s: subscribed by: %s callback: my_callback", name, self.parent.channel_id)
                self.subscribed = True
            elif self.subscribed:
                self.log.info("%s: subscriber %s already subscribed", name, self.parent.channel_id)
                self.fc.calledback = False
            else:
                self.log.info("%s: sender: %s: fanout disabled", name, self.parent.sender)

            with self.client.post(uri, json=json_data, headers=self.headers,
                                  catch_response=True,
                                  files=files) as response:
                self.log.info("%s: post response.status_code: %d, posted json: %s", name, response.status_code,
                                                                                      json_data)
            if self.parent.fanout:
                self.process_fanout_callbacks(uri, name)
        else:
            self.log.debug("%s: sender set to None", name)

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
        self.log.info("%s: new user starting", self.__class__.__name__)
        self.log.debug("%s: tasks: %s", self.__class__.__name__, self.tasks_conf)
        self.set_sender()

    def set_sender(self):
        with self.client.post('/start', catch_response=True) as response:
            if response.status_code != 200:
                self.log.error("%s: /start post response.status_code: %s", self.__class__.__name__, response.status_code)
                self.log.error("%s: /start set sender to None, not processing")
                self.sender = None
            else:
                response_json = response.json()
                self.sender = response_json['channelId']
                self.log.info("%s: /start sender: %s", self.__class__.__name__, self.sender)

                if self.fanout:
                    self.channel_id = response.json()['channelId']
                    self.fanout_realm = response.json()['fanoutRealm']
                    self.fanout_url = 'https://{}.fanoutcdn.com/bayeux'.format(self.fanout_realm)


class Locustio(HttpLocust):
    task_set = BaseTaskSet
    logging.config.dictConfig(LOGGING_CONFIG)
    log = logging.getLogger('main')


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