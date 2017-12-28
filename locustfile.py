from locust import HttpLocust, TaskSet, task
import json


class CustomTaskSet(TaskSet):

    def __init__(self, parent):
        super(CustomTaskSet, self).__init__(parent)
        if hasattr(parent, "debug"):
            self.debug = self.parent.debug
        if hasattr(parent, "sender"):
            self.sender = self.parent.sender
        else:
            print("{}: sender not set!".format(self.__class__.__name__))

        self.headers = {"content-type": "application/json;charset=UTF-8"}

    def post(self, uri, json_data, name, files=None, **kwargs):
        if self.debug:
            json_data['sender'] = self.sender
            print("{}: {}".format(name, json_data))

        with self.client.post(uri, json=json_data, headers=self.headers,
                              catch_response=True,
                              files=files) as response:
            if self.debug:
                print("{}: response.status_code: {}, content: {}".format(name, response.status_code, response.content))
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
        json = {"message":{"text": "message", "quick_replies": [], "mid": "mid.1514283239929.941"},
                "sender":"{sender}", "recipient": {"id": None}
                }
        self.post(uri="/send", json_data=json, name=self.__class__.__name__)


class BaseTaskSet(TaskSet):
    debug = True
    # locust tasks
    tasks = {
        Btn1: 6,
        Btn2: 12,
        Msg: 3,
    }

    def on_start(self):
        self.set_sender()

    def set_sender(self):
        with self.client.post('/start', json=None,
                              catch_response=True) as response:
            # print(response.status_code, response.content)
            if response.status_code != 200:
                print("{}: /start response.status_code: {}".format(self.__class__.__name__, response.status_code))
                print("{}: set sender to: {}".format(self.__class__.__name__, self.parent.default_sender))
                self.sender = self.parent.default_sender
            else:
                response_json = response.json()
                self.sender = response_json['channelId']
                print("{}: sender: {}".format(self.__class__.__name__, self.sender))


class Locustio(HttpLocust):
    task_set = BaseTaskSet
    # to get default_sender run: chat_request.py
    default_sender = "2670c032-0795-43fa-9f2e-ad01622d1626"


# class Debug(HttpLocust):
#     task_set = BaseTaskSet
#     host = 'https://staging2.imblox.com/webchat/zwN4pSUU'
#
#     # to get default_sender run: chat_request.py
#     default_sender = "2670c032-0795-43fa-9f2e-ad01622d1626"
#
#
# if __name__ == '__main__':
#     Debug().run()