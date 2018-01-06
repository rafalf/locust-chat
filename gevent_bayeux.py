import gevent
import requests
import python_bayeux
import time
import json


class FanoutClient(python_bayeux.BayeuxClient):
    def __init__(self, *args, **kwargs):
        super(FanoutClient, self).__init__(*args, **kwargs)
        self.connect_timeout = None

        self.fulfilled = False
        self.calledback = False
        self.btns = []
        self.log = None
        self.subscriber = None

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
            self.log.debug("callback: callback msg: {}".format(message['data']))
            d = json.loads(message['data'])
            self.calledback = True
            try:
                for btn in d['message']['attachment']['payload']['buttons']:
                    if btn['type'] == "postback":
                        self.log.debug("callback: subscriber: {} postback btn found w/ title: {}".
                                       format(self.subscriber, btn['title']))
                        self.btns.append(btn['title'])
                        self.fulfilled = True
            except KeyError:
                pass
        except Exception as err:
            self.log.error('callback: someting went wrong reading callback: {}'.format(err))

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

if __name__ == "__main__":

    resp = requests.post('https://staging2.imblox.com/webchat/jq1rOdGR/start')
    channel_id = resp.json()['channelId']
    fanout_realm = resp.json()['fanoutRealm']
    fanout_url = 'https://{}.fanoutcdn.com/bayeux'.format(fanout_realm)

    c = FanoutClient(fanout_url)
    c.subscribe('/' + channel_id, 'my_test_callback')
    gevent.spawn(c._execute_greenlet)

    print(fanout_realm, fanout_url)

    # btn
    # json_data = {"postback": {"payload": "Btn-1",
    #                           "title": "title"},
    #            "sender": channel_id,
    #            "recipient": {"id": None}
    #             }

    # msg
    json_data = {"message": {"text": "message", "quick_replies": [], "mid": "mid.1514283239929.941"},
                 "sender": channel_id, "recipient": {"id": None}
                 }

    headers = {"content-type": "application/json;charset=UTF-8"}
    r = requests.post("https://staging2.imblox.com/webchat/jq1rOdGR/send", json=json_data, headers=headers)

    while not c.fulfilled:
        print('wait for callback')
        time.sleep(1)

    print('called back')
    print(r)

