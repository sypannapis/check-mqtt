#!/usr/bin/env python

'''
check_myrightweight.py makes use of some code from Jan-Piet Mens check-mqtt.py.
    https://github.com/jpmens/check-mqtt
    
Copyright (c) 2016 Jeff Albrecht
All rights reserved.

Use this to monitor an mqtt application with Nagios.

Unlike check-mqtt which this is based on that monitors the mqtt broker, 
check_myrightweight will not publish a response.
check_myrightweight waits to hear a 'pong' sent from the application it is 
monitoring in response to the'ping' sent from check_myrightweight.py. 

'''

# Copyright (c) 2013-2015 Jan-Piet Mens <jpmens()gmail.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice,
#    this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of mosquitto nor the names of its
#    contributors may be used to endorse or promote products derived from
#    this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import paho.mqtt.client as paho
import ssl
import time
import sys
import os
import argparse

check_payload = 'ping'
current_milli_time = lambda: int(round(time.time() * 1000))

status = 0
message = ''

nagios_codes = [ 'OK', 'WARNING', 'CRITICAL', 'UNKNOWN' ]

def on_connect(mosq, userdata, rc):
    """
    Upon successfully being connected, we subscribe to the check_topic
    """

    mosq.subscribe(args.check_topic, 0)

def on_publish(mosq, userdata, mid):
    pass

def on_subscribe(mosq, userdata, mid, granted_qos):
    """
    When the subscription is confirmed, we publish our payload
    on the check_topic. Since we're subscribed to this same topic,
    on_message() will fire when we see that same message
    """

    (res, mid) =  mosq.publish(args.check_topic, check_payload, qos=2, retain=False)

def on_message(mosq, userdata, msg):
    """
    This is invoked when we get our own message back. Verify that it
    is actually our message and if so, we've completed a round-trip.
    """

    global message
    global status

    check_this = check_payload
    if (args.ignore_ping != None):
        check_this = args.ignore_ping
        if str(msg.payload == 'ping'): # if we're loooking for a 'pong' from a monitored application skip our ping.
            pass
 
    if str(msg.payload) == check_this:
        userdata['have_response'] = True
        status = 0
        elapsed = (current_milli_time() - userdata['start_time'])
        message = "%d" % (elapsed)

def on_disconnect(mosq, userdata, rc):

    if rc != 0:
        exitus(1, "Unexpected disconnection. Incorrect credentials?")

def exitus(status=0, message="all is well"):
    """
    Produce a Nagios-compatible single-line message and exit according
    to status
    """

    print "%s" % (message)
    sys.exit(status)


parser = argparse.ArgumentParser()
parser.add_argument('-H', '--host', metavar="<hostname>", help="mqtt host to connect to (defaults to localhost)", dest='mqtt_host', default="localhost")
parser.add_argument('-P', '--port', metavar="<port>", help="network port to connect to (defaults to 1883)", dest='mqtt_port', default=1883, type=int)
parser.add_argument('-u', '--username', metavar="<username>", help="username", dest='mqtt_username', default=None)
parser.add_argument('-p', '--password', metavar="<password>", help="password", dest='mqtt_password', default=None)
parser.add_argument('-t', '--topic', metavar="<topic>", help="topic to use for the check (defaults to nagios/test)", dest='check_topic', default='nagios/test')
parser.add_argument('-m', '--max-wait', metavar="<seconds>", help="maximum time to wait for the check (defaults to 4 seconds)", dest='max_wait', default=4, type=int)
parser.add_argument('-i', '--ignoreping', metavar="<ignoreping>", help="ignore ping, test on pong sent from monitored clients", dest='ignore_ping', default=None)
args = parser.parse_args()

userdata = {
    'have_response' : False,
    'start_time'    : current_milli_time(),
}
mqttc = paho.Client('nagios-%d' % (os.getpid()), clean_session=True, userdata=userdata, protocol=4)
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_disconnect = on_disconnect
mqttc.on_publish = on_publish
mqttc.on_subscribe = on_subscribe

#mqttc.tls_set('root.ca',
#    cert_reqs=ssl.CERT_REQUIRED,
#    tls_version=1)

#mqttc.tls_set('root.ca', certfile='c1.crt', keyfile='c1.key', cert_reqs=ssl.CERT_REQUIRED, tls_version=3, ciphers=None)
#mqttc.tls_insecure_set(True)    # optional: avoid check certificate name if true

# username & password may be None
if args.mqtt_username is not None:
    mqttc.username_pw_set(args.mqtt_username, args.mqtt_password)

# Attempt to connect to broker. If this fails, issue CRITICAL

try:
    mqttc.connect(args.mqtt_host, args.mqtt_port, 60)
except Exception, e:
    status = 2
    message = "Connection to %s:%d failed: %s" % (args.mqtt_host, args.mqtt_port, str(e))
    exitus(status, message)

rc = 0
while userdata['have_response'] == False and rc == 0:
    rc = mqttc.loop()
    if current_milli_time() - userdata['start_time'] > args.max_wait:
        message = 'timeout waiting for PUB'
        status = 2
        break

mqttc.disconnect()

exitus(status, message)

