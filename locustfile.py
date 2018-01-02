from locust import HttpLocust, TaskSet, task
import yaml
import logging
import logging.config


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
            'maxBytes': 1024,
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
        if hasattr(parent, "sender"):
            self.sender = self.parent.sender
        else:
            self.log.error("{}: sender not set!".format(self.__class__.__name__))

        self.headers = {"content-type": "application/json;charset=UTF-8"}

    def post(self, uri, json_data, name, files=None, **kwargs):

        json_data['sender'] = self.sender
        self.log.debug("{}: {}".format(name, json_data))

        with self.client.post(uri, json=json_data, headers=self.headers,
                              catch_response=True,
                              files=files) as response:
            self.log.info("{}: post response.status_code: {}, content: {}, posted json: {}".format(name, response.status_code,
                                                                                  response.content, json_data))
            # return response


class Btn1(CustomTaskSet):

    @task
    def get_namespace(self):
        json = {"postback": {"payload": "Btn-1",
                             "title": "title"},
                "sender": "{sender}",
                "recipient": {"id": None}
                }
        self.post(uri="/send", json_data=json, name=self.__class__.__name__)


class Btn2(CustomTaskSet):

    @task
    def get_namespace(self):
        json = {"postback": {"payload": "Btn-2",
                             "title": "title",}
                ,"sender": "{sender}",
                "recipient": {"id": None}
                }
        self.post(uri="/send", json_data=json, name=self.__class__.__name__)


class Msg(CustomTaskSet):

    @task
    def get_namespace(self):
        json = {"message": {"text": "message", "quick_replies": [], "mid": "mid.1514283239929.941"},
                "sender": "{sender}", "recipient": {"id": None}
                }
        self.post(uri="/send", json_data=json, name=self.__class__.__name__)


class BaseTaskSet(TaskSet):

    # locust tasks
    with open("config.yaml", 'r') as yaml_file:
        yaml_conf = yaml.load(yaml_file)

    tasks_conf = yaml_conf['tasks']
    tasks = {eval(name): weight for name, weight in tasks_conf.items()}

    # log level
    level = yaml_conf['level']

    # default sender
    default_sender = yaml_conf['sender']

    def on_start(self):
        self.log = self.parent.log
        self.log.setLevel(level=logging.getLevelName(self.level))
        self.set_sender()

    def set_sender(self):
        with self.client.post('/start', json=None,
                              catch_response=True) as response:
            if response.status_code != 200:
                self.log.error("{}: /start post response.status_code: {}".format(self.__class__.__name__, response.status_code))
                self.log.info("{}: set sender to default: {}".format(self.__class__.__name__, self.default_sender))
                self.sender = self.default_sender
            else:
                response_json = response.json()
                self.sender = response_json['channelId']
                self.log.info("{}: sender: {}".format(self.__class__.__name__, self.sender))


class Locustio(HttpLocust):
    task_set = BaseTaskSet
    logging.config.dictConfig(LOGGING_CONFIG)
    log = logging.getLogger('main')


class Debug(HttpLocust):
    task_set = BaseTaskSet
    host = 'https://staging.imblox.com/webchat/qVT8bLp6'

    logging.config.dictConfig(LOGGING_CONFIG)
    log = logging.getLogger('main')


if __name__ == '__main__':
    Debug().run()