# Device manager
# author: ulno
# created: 2017-04-07
#
# manage a list of installed devices and enable
# sending or reacting to mqtt

import gc
import machine
import ulnoiot._wifi as _wifi
import time
import ubinascii
from umqtt.simple import MQTTClient as _MQTTClient
gc.collect()

_devlist = {}

#### global MQTT variables
_client_id = ubinascii.hexlify(machine.unique_id())  # make unique
_broker = None
_topic = None
_user = None
_password = None
_client = None
_report_ip = True

####### simple Input, contact devices/push buttons
def contact(name, pin, *args, report_high="on", report_low="off",
            pullup=True,threshold=0):
    if len(args) > 0:
        report_high = args[0]
        if len(args) > 1:
            report_low = args[1]
    gc.collect()
    from ulnoiot._contact import Contact
    _devlist[name] = Contact(name, pin,
                            report_high=report_high,
                            report_low=report_low,
                            pullup=pullup,
                            threshold=threshold)
    gc.collect()
    return _devlist[name]
button = contact

####### simple Input, contact devices/push buttons
def trigger(name, pin, rising=False, falling=False,
            pullup=True):
    gc.collect()
    from ulnoiot._trigger import Trigger
    _devlist[name] = Trigger(name, pin,
                            rising=rising, falling=falling,
                            pullup=pullup)
    gc.collect()
    return _devlist[name]


####### simple LEDs, other Output (switches)
def out(name, pin, *args, high_command='on', low_command='off', ignore_case=True):
    if len(args) > 0:
        high_command = args[0]
        if len(args) > 1:
            low_command = args[1]
    gc.collect()
    from ulnoiot._output import Output
    _devlist[name] = Output(name, pin, high_command=high_command, low_command=low_command, ignore_case=ignore_case)
    gc.collect()
    return _devlist[name]
led = out
switch = out


####### HT temperature/humidity with
def ht(name, pin):
    gc.collect()
    from ulnoiot._ht import HT
    _devlist[name] = HT(name, pin)
    gc.collect()
    return _devlist[name]

####### display
def display(name, sda, scl, ignore_case=False):
    gc.collect()
    from ulnoiot._display import Display
    _devlist[name] = Display(name, sda, scl, ignore_case=ignore_case)
    gc.collect()
    return _devlist[name]

######## Devices End

##### utils
def linecat(filename,frm=1,to=0):
    from ulnoiot import _line_edit
    _line_edit.linecat(filename,frm=frm,to=to)

def lineedit(filename,linenr):
    from ulnoiot import _line_edit
    _line_edit.lineedit(filename,linenr)

def delete(name):
    _devlist.pop(name)


def _publish_status():
    global _client

    try:
        for d in _devlist.values():
            v = d.value()
            if v is not None:
                t = (_topic + "/" + d.topic).encode()
                if isinstance(v, dict): # several values to publish
                    print('Publish status', t, v)
                    for k in v:
                        t_extra = t + b"/" + k.encode()
                        _client.publish(t_extra, str(v[k]).encode())
                else:
                    v_map = d.mapped_value()  # try to map
                    if v_map is None:  # not mappable, try to send what we have
                        v_map = str(v).encode()

                    print('Publish status:', t, v_map)
                    _client.publish(t, v_map)
#        if _report_ip:
#            t = (_topic + "/ip").encode()
#            _client.publish(t, str(_wifi.config()[0]), retain=True)
    except Exception as e:
        print('Trouble publishing, re-init network.')
        print(e)
        _init_mqtt()


#### Setup and execution
def mqtt(broker_host, topic, *args, user=None, password=None,
         client_id=None, report_ip=True):
    global _broker, _topic, _user, _password, _client_id, _report_ip

    if len(args) > 0:
        user = args[0]
        if len(args) > 1:
            password = args[1]

    _broker = broker_host
    _topic = topic
    if client_id is not None:
        _client_id = client_id.encode() + b"_" + _client_id;
    _user = user
    _password = password
    _report_ip = report_ip


def _subscription_cb(topic, msg):
    topic = topic.decode();
    msg = msg.decode();
    for d in _devlist.values():
        if d.command_topic is not None:
            t = _topic + "/" + d.command_topic
            if topic == t:
                print("Received \"%s\" for topic %s"%(msg, topic))
                d.command(msg)


def _init_mqtt():
    global _client
    global _broker, _topic, _user, _password, _client_id

    print("Trying to connect to mqtt broker.")
    _wifi.connect()
    try:
        _client = _MQTTClient(_client_id, _broker, user=_user,
                             password=_password)
        _client.set_callback(_subscription_cb)
        _client.connect()
        print("Connected to",_broker)
        t = _topic.encode() + b"/#"
        _client.subscribe(t)
        print("Subscribed to topic and subtopics of", _topic)
        if _report_ip:
            t = (_topic + "/ip").encode()
            _client.publish(t, str(_wifi.config()[0]), retain=True)
    except Exception as e:
        print("Trouble to init mqtt:", e)


def _poll_subscripton():
    global _client
    try:
        _client.check_msg()  # non blocking
    except:
        print("Trouble to receive from mqtt.")


def run(updates=5, sleepms=1, poll_rate_inputs=4, poll_rate_network=10):
    # updates: send out a status every this amount of seconds.
    #          If 0, never send time based status updates only when change happened.
    # sleepms: going o sleep for how long between each loop run
    # poll_rate_network: how often to evaluate incoming network commands
    # poll_rate_inputs: how often to evaluate inputs
    _init_mqtt()
    if updates == 0:
        overflow = 1000
    else:
        overflow = updates * 1000
    overflow *= poll_rate_network * poll_rate_inputs / sleepms
    overflow = int(overflow)
#    print("Overflow:",overflow)
    counter = 0

    while True:
        if counter % poll_rate_network == 0:
            _poll_subscripton()
        if counter % poll_rate_inputs == 0:
            change_happened = False
            for d in _devlist.values():
                if d.update():
                    change_happened = True
            if change_happened:
                _publish_status()
        if updates != 0 and counter % (updates * 1000) == 0:
            print("Publishing.")
            _publish_status()

        time.sleep_ms(sleepms)
        counter += 1
        if counter >= overflow:
            counter = 0


transmit = run