import gevent
import requests
import python_bayeux
import time
import json
import yaml
from locust import HttpLocust, TaskSet, task
from random import randint
from queue import Queue


class FanoutClient(python_bayeux.BayeuxClient):
    def __init__(self, *args, **kwargs):
        super(FanoutClient, self).__init__(*args, **kwargs)
        self.connect_timeout = None

        self.fulfilled = False
        self.calledback = False
        self.btns = []
        self.log = None
        self.subscriber = None
        self.queue = Queue()

    def _handle_advice(self, advice):
        if 'timeout' in advice:
            self.connect_timeout = advice['timeout'] / 1000.0

    def handshake(self, **kwargs):
        self.message_counter = 1

        handshake_payload = {
            # MUST
            'channel': '/meta/handshake',
            'supportedConnectionTypes': ['long-polling'],
            'version': '1.0',
            # MAY
            'id': None,
            'minimumVersion': '1.0'
        }
        handshake_payload.update(kwargs)
        handshake_response = self._send_message(handshake_payload)

        # TODO: No error checking here
        self.client_id = handshake_response[0]['clientId']

    def _send_message(self, payload, **kwargs):
        if 'id' in payload:
            payload['id'] = str(self.message_counter)
            self.message_counter += 1

        if 'clientId' in payload:
            payload['clientId'] = self.client_id

        python_bayeux.LOG.info('_send_message(): payload: {0}  kwargs: {1}'.format(
            str(payload),
            str(kwargs)
        ))

        response = self.oauth_session.post(
            self.endpoint,
            json=payload,
            **kwargs
        )

        python_bayeux.LOG.info(
            u'_send_message(): response status code: {0}  '
            u'response.text: {1}'.format(
                response.status_code,
                response.text
            )
        )

        res = response.json()

        advice = res[0].get('advice')
        if advice:
            self._handle_advice(advice)

        return res

    def my_callback(self, message):

        try:
            self.log.debug("callback: got called back msg: {}".format(message))
            self.queue.put(message)
            self.calledback = True
        except Exception as err:
            self.log.error('callback: someting went wrong putting callback: {}'.format(err))

    def process_queue_items(self):

        while not self.queue.empty():
            message = self.queue.get()
            d = json.loads(message['data'])
            self.log.debug("callback: %s get item from queue: %s", self.subscriber, d)
            try:
                for btn in d['message']['attachment']['payload']['buttons']:
                    if btn['type'] == "postback":
                        self.log.debug("callback: subscriber fulfilled: {} postback btn found w/ title: {}".
                                       format(self.subscriber, btn['title']))
                        self.btns.append(btn['title'])
                        self.fulfilled = True
            except KeyError:
                self.log.debug("callback: subscriber: %s, btn not found in response", self.subscriber)

            self.queue.task_done()

    def my_test_callback(self, message):

        d = json.loads(message['data'])
        print(d['message'])

        try:
            for btn in d['message']['attachment']['payload']['buttons']:
                if btn['type'] == "postback":
                    print("postback btn found w/ title: {}".format(btn['title']))
                    self.btns.append(btn['title'])
                    self.fulfilled = True
        except KeyError:
            pass

        self.calledback = True


class TestBot(TaskSet):

    @task
    def profile(self):

        resp = self.client.post(host + '/start')
        channel_id = resp.json()['channelId']
        fanout_realm = resp.json()['fanoutRealm']
        fanout_url = 'https://{}.fanoutcdn.com/bayeux'.format(fanout_realm)

        c = FanoutClient(fanout_url)
        c.subscribe('/' + channel_id, 'my_test_callback')
        gevent.spawn(c._execute_greenlet)

        print(fanout_realm, fanout_url)

        for counter in range(10):

            mid = self.get_random_mid()
            mid = "mid.1514283239929.941"
            temp_timeout = 5

            json_data = {"message": {"text": "message", "quick_replies": [], "mid": mid},
                         "sender": channel_id, "recipient": {"id": None}
                         }

            headers = {"content-type": "application/json;charset=UTF-8"}
            r = self.client.post(host + "/send", json=json_data, headers=headers)

            while not c.calledback:
                print('wait for callback processed')
                time.sleep(1)
                temp_timeout -= 1
                if temp_timeout == 0:
                    print('call back timed out')
                    break

            if c.calledback:
                temp_timeout = 5
                while not c.fulfilled:
                    print('wait for fulfilled callback')
                    time.sleep(1)
                    if temp_timeout == 0:
                        break
                    temp_timeout -= 1

            if c.calledback and c.fulfilled:
                print('ok, called back and fulfilled, counter: %d' % counter)
                print(r)
            else:
                print('eh, callback: %s fulfilled: %s, counter: %d' % (c.calledback, c.fulfilled, counter))

            c.fulfilled = False
            c.calledback = False

    def get_random_mid(self):
        return "mid.%d.941" % randint(1111111111111, 9999999999999)


class Locustio(HttpLocust):
    task_set = TestBot
    min_wait = 1000
    max_wait = 1000

    with open("config.yaml", 'r') as yaml_file:
        yaml_conf = yaml.load(yaml_file)
    host = yaml_conf['host']


if __name__ == "__main__":

    with open("config.yaml", 'r') as yaml_file:
        yaml_conf = yaml.load(yaml_file)
    host = yaml_conf['host']

    if not yaml_conf['test_locustio']:

        resp = requests.post(host + '/start')
        channel_id = resp.json()['channelId']
        fanout_realm = resp.json()['fanoutRealm']
        fanout_url = 'https://{}.fanoutcdn.com/bayeux'.format(fanout_realm)

        c = FanoutClient(fanout_url)
        c.subscribe('/' + channel_id, 'my_test_callback')
        gevent.spawn(c._execute_greenlet)

        print(fanout_realm, fanout_url)

        for _ in range(10):

            # btn
            json_data = {"postback": {"payload": "View Gallery",
                                      "title": "View Gallery"},
                       "sender": channel_id,
                       "recipient": {"id": None}
                        }

            # msg
            # json_data = {"message": {"text": "message", "quick_replies": [], "mid": "mid.1514283239929.941"},
            #              "sender": channel_id, "recipient": {"id": None}
            #              }

            headers = {"content-type": "application/json;charset=UTF-8"}
            r = requests.post(host + "/send", json=json_data, headers=headers)

            while not c.fulfilled:
                print('wait for callback')
                time.sleep(1)

            print('called back')
            print(r)

            c.fulfilled = False
            c.calledback = False

    else:
        Locustio().run()
