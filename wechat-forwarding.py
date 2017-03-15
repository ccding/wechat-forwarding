#!/usr/bin/env python
# -*-encoding:utf-8-*-

import sys
reload(sys)
sys.setdefaultencoding('UTF8')

import os, re, shutil, time, collections, json

import itchat
from itchat.content import *

sending_type = {'Picture': 'img', 'Video': 'vid'}
data_path = 'data'
from_group_names = {u'酒井 9#'}
to_group_names = [u'酒井民间自救群', u'酒井 9# 二号']
senders = {u'酒井9#'}

def get_sender_receiver(msg):
    sender = None
    receiver = None
    if msg['FromUserName'][0:2] == '@@': # group chat
        sender = msg['ActualNickName']
        m = itchat.search_chatrooms(userName=msg['FromUserName'])
        if m is not None:
            receiver = m['NickName']
    elif msg['ToUserName'][0:2] == '@@': # group chat by myself
        if 'ActualNickName' in msg:
            sender = msg['ActualNickName']
        else:
            m = itchat.search_friends(userName=msg['FromUserName'])
            if m is not None:
                sender = m['NickName']
        m = itchat.search_chatrooms(userName=msg['ToUserName'])
        if m is not None:
            receiver = m['NickName']
    else: # personal chat
        m = itchat.search_friends(userName=msg['FromUserName'])
        if m is not None:
            sender = m['NickName']
        m = itchat.search_friends(userName=msg['ToUserName'])
        if m is not None:
            receiver = m['NickName']
    return sender.strip(), receiver.strip()

def print_msg(msg):
    if len(msg) == 0:
        return
    print json.dumps(msg).decode('unicode-escape').encode('utf8')

def get_whole_msg(msg, download=False, senders={}, receivers={}):
    if msg['FileName'][-4:] == 'gif': # can't handle gif pictures
        return []
    sender, receiver = get_sender_receiver(msg)
    if (sender in senders) or (receiver not in receivers):
        return []
    if len(msg['FileName']) > 0 and len(msg['Url']) == 0:
        if download: # download the file into data_path directory
            fn = os.path.join(data_path, msg['FileName'])
            msg['Text'](fn)
            c = '@%s@%s' % (sending_type.get(msg['Type'], 'fil'), fn)
        else:
            c = '@%s@%s' % (sending_type.get(msg['Type'], 'fil'), msg['FileName'])
        return ['[%s]:' % (sender), c]
    c = msg['Text']
    if len(msg['Url']) > 0:
        c += ' ' + msg['Url']
    return ['[%s]: %s' % (sender, c)]

@itchat.msg_register([TEXT, PICTURE, MAP, CARD, SHARING, RECORDING,
    ATTACHMENT, VIDEO, FRIENDS], isFriendChat=True, isGroupChat=True)
def normal_msg(msg):
    msg_send = get_whole_msg(msg, download=True, senders=senders, receivers=from_group_names)
    if len(msg_send) == 0:
        return
    print_msg(msg_send)
    for m in msg_send:
        for name in to_group_names:
            room = itchat.search_chatrooms(name=name)
            if room is not None and len(room) > 0:
                username = room[0]['UserName']
                itchat.send(m, toUserName=username)

if __name__ == '__main__':
    if not os.path.exists(data_path):
        os.mkdir(data_path)
    # if the QR code doesn't show correctly, you can try to change the value
    # of enableCdmQR to 1 or -1 or -2. It nothing works, you can change it to
    # enableCmdQR=True and a picture will show up.
    itchat.auto_login(hotReload=True, enableCmdQR=2)
    itchat.run()
