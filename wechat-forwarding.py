#!/usr/bin/env python3
# -*-encoding:utf-8-*-

import os, json, requests, html
from xml.etree import ElementTree as ETree

import itchat
from itchat.content import *

sending_type = {'Picture': 'img', 'Video': 'vid'}
data_path = 'data'
nickname = ''
as_chat_bot = True
bot = None
config = {}

if __name__ == '__main__':
    with open('config.json', 'r') as fin:
        config = json.loads(fin.read())
    if not os.path.exists(data_path):
        os.mkdir(data_path)
    # if the QR code doesn't show correctly, you can try to change the value
    # of enableCdmQR to 1 or -1 or -2. It nothing works, you can change it to
    # enableCmdQR=True and a picture will show up.
    bot = itchat.new_instance()
    bot.auto_login(hotReload=True, enableCmdQR=2)
    nickname = bot.loginInfo['User']['NickName']

# tuling chat bot
def talks_robot(info):
    api_url = 'http://www.tuling123.com/openapi/api'
    apikey = ''
    data = {'key': apikey, 'info': info.lower()}
    try:
        req = requests.post(api_url, data=data, timeout=5).text
        txt = json.loads(req)['text']
        if txt.find(u'不知道') >= 0:
            return
        if txt.find(u'不会') >= 0:
            return
        if txt.find(u'抱歉') >= 0:
            return
        return txt
    except:
        pass
    return None

def get_sender_receiver(msg):
    sender = nickname
    receiver = nickname
    if msg['FromUserName'][0:2] == '@@': # group chat
        sender = msg['ActualNickName']
        m = bot.search_chatrooms(userName=msg['FromUserName'])
        if m is not None:
            receiver = m['NickName']
    elif msg['ToUserName'][0:2] == '@@': # group chat by myself
        if 'ActualNickName' in msg:
            sender = msg['ActualNickName']
        else:
            m = bot.search_friends(userName=msg['FromUserName'])
            if m is not None:
                sender = m['NickName']
        m = bot.search_chatrooms(userName=msg['ToUserName'])
        if m is not None:
            receiver = m['NickName']
    else: # personal chat
        m = bot.search_friends(userName=msg['FromUserName'])
        if m is not None:
            sender = m['NickName']
        m = bot.search_friends(userName=msg['ToUserName'])
        if m is not None:
            receiver = m['NickName']
    return html.unescape(sender), html.unescape(receiver)

def print_msg(msg):
    print(' '.join(msg))

def get_whole_msg(msg, prefix, sender, download=True):
    if len(msg['FileName']) > 0 and len(msg['Url']) == 0:
        if download: # download the file into data_path directory
            fn = os.path.join(data_path, msg['FileName'])
            msg['Text'](fn)
            if os.path.getsize(fn) == 0:
                return []
            c = '@%s@%s' % (sending_type.get(msg['Type'], 'fil'), fn)
        else:
            c = '@%s@%s' % (sending_type.get(msg['Type'], 'fil'), msg['FileName'])
        return ['%s[%s]:' % (prefix, sender), c]
    c = msg['Text']
    if len(msg['Url']) > 0:
        if len(msg['OriContent']) > 0:
            try: # handle map label
                content_tree = ETree.fromstring(msg['OriContent'])
                if content_tree is not None:
                    map_label = content_tree.find('location')
                    if map_label is not None:
                        c += ' ' + map_label.attrib['poiname']
                        c += ' ' + map_label.attrib['label']
            except:
                pass
        url = html.unescape(msg['Url'])
        c += ' ' + url
    # if a message starts with '//', send as anonymous
    if c.startswith('//'):
        sender = u'匿名'
        c = c[2:].strip()
    return ['%s[%s]: %s' % (prefix, sender, c)]

@bot.msg_register([TEXT], isFriendChat=True, isGroupChat=False)
def personal_msg(msg):
    global as_chat_bot
    text = msg['Text'].strip()
    if text == u'闭嘴':
        as_chat_bot = False
    if text == u'张嘴吃药':
        as_chat_bot = True
    return talks_robot(text)

@bot.msg_register([FRIENDS])
def accept_friend(msg):
    bot.add_friend(msg['RecommendInfo']['UserName'], 3)

@bot.msg_register([TEXT, PICTURE, MAP, SHARING, RECORDING, ATTACHMENT, VIDEO], isFriendChat=False, isGroupChat=True)
def group_msg(msg):
    # chat bot functionality
    global as_chat_bot
    if 'IsAt' in msg and msg['IsAt'] == True and msg['Type'] == 'Text' and \
            msg['ToUserName'][0:2] != '@@' and msg['Text'].find(u'@' + nickname) >= 0:
        text = msg['Text'].replace(u'@' + nickname, '').strip()
        if text == u'闭嘴':
            as_chat_bot = False
            return
        if as_chat_bot:
            info = talks_robot(text)
            return info
        return
    # forwarding functionality
    group = msg['FromUserName']
    if msg['ToUserName'][0:2] == '@@': # message sent by myself
        group = msg['ToUserName']
    sender, receiver = get_sender_receiver(msg)
    if sender == '':
        sender = nickname
    # check if the message is in the config
    if receiver not in config: # if not in the config, do nothing
        return
    # process message and send it to all the subscribers
    prefix = config[receiver]['prefix']
    msg_send = get_whole_msg(msg, prefix, sender)
    if msg_send is None or len(msg_send) == 0:
        return
    print_msg(msg_send)
    for tosend in config[receiver]['sub']:
        room = bot.search_chatrooms(name=tosend)
        for r in room:
            if r['UserName'] == group: # don't send back to the source
                continue
            if r['NickName'] != tosend: # check group name exact match
                continue
            for m in msg_send: # iterate messages (for images, videos, and files)
                bot.send(m, toUserName=r['UserName'])

if __name__ == '__main__':
    bot.run()
