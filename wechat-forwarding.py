#!/usr/bin/env python
# -*-encoding:utf-8-*-

import sys
reload(sys)
sys.setdefaultencoding('UTF8')

import os, re, shutil, time, collections, json
from HTMLParser import HTMLParser
from xml.etree import ElementTree as ETree

import itchat
from itchat.content import *

sending_type = {'Picture': 'img', 'Video': 'vid'}
data_path = 'data'
from_group_names = {u'酒井 9#', u'酒井民间自救群', u'酒井 9# 互联B'}
to_group_names = [u'酒井 9#', u'酒井民间自救群', u'酒井 9# 互联B']
nickname = ''
bot = None

if __name__ == '__main__':
    if not os.path.exists(data_path):
        os.mkdir(data_path)
    # if the QR code doesn't show correctly, you can try to change the value
    # of enableCdmQR to 1 or -1 or -2. It nothing works, you can change it to
    # enableCmdQR=True and a picture will show up.
    bot = itchat.new_instance()
    bot.auto_login(hotReload=True, enableCmdQR=2)
    nickname = bot.loginInfo['User']['NickName']

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
    return HTMLParser().unescape(sender), HTMLParser().unescape(receiver)

def print_msg(msg):
    if len(msg) == 0:
        return
    print json.dumps(msg).decode('unicode-escape').encode('utf8')

def get_whole_msg(msg, prefix, download=False):
    if len(msg['FileName']) > 0 and len(msg['Url']) == 0:
        if download: # download the file into data_path directory
            fn = os.path.join(data_path, msg['FileName'])
            msg['Text'](fn)
            if os.path.getsize(fn) == 0:
                return []
            c = '@%s@%s' % (sending_type.get(msg['Type'], 'fil'), fn)
        else:
            c = '@%s@%s' % (sending_type.get(msg['Type'], 'fil'), msg['FileName'])
        return ['[%s]:' % (prefix), c]
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
        url = HTMLParser().unescape(msg['Url'])
        c += ' ' + url
    return ['[%s]: %s' % (prefix, c)]

@bot.msg_register([TEXT, PICTURE, MAP, SHARING, RECORDING,
    ATTACHMENT, VIDEO], isFriendChat=False, isGroupChat=True)
def normal_msg(msg):
    to_username = msg['ToUserName']
    from_username = msg['FromUserName']
    if to_username[0:2] == '@@': # message sent by myself
        if msg['Type'] != 'Text': # ignore all none-text msgs to avoid loop
            return
        if msg['Text'][0] == '[': # if a text msg is a forward, do nothing
            return
        to_username, from_username = from_username, to_username
    sender, receiver = get_sender_receiver(msg)
    if receiver not in from_group_names: # if not in the from_group_names, do nothing
        return
    msg_send = get_whole_msg(msg, prefix=sender, download=True)
    if len(msg_send) == 0:
        return
    print_msg(msg_send)
    for tosend in to_group_names:
        room = bot.search_chatrooms(name=tosend)
        for r in room:
            if r['UserName'] == from_username: # don't send back to the source
                continue
            if r['NickName'] != tosend: # check group name exact match
                continue
            for m in msg_send: # iterate messages (for images, videos, and files)
                bot.send(m, toUserName=r['UserName'])

if __name__ == '__main__':
    bot.run()
