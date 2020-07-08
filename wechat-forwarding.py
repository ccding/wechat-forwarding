#!/usr/bin/env python3
# -*-encoding:utf-8-*-

import os, json, time, requests, html, threading, queue
from xml.etree import ElementTree as ETree

import itchat
from itchat.content import *
import signal
import timeout_decorator

class Const:
    PERSON = 'PERSON'
    GROUP = 'GROUP'
    TYPES = {'Picture': 'img', 'Video': 'vid'}
    data_path = None

    def __init__(self, config):
        if 'data_path' in config:
            self.data_path = config['data_path']

    @timeout_decorator.timeout(60)
    def preprocess(self, msg):
        if self.data_path is None:
            return
        if len(msg['FileName']) > 0 and len(msg['Url']) == 0: # file as a message
            fn = os.path.join(self.data_path, msg['FileName'])
            msg.download(fn)

class AddMemberBot:
    groups = None
    users = None
    bot = None

    def __init__(self, config, bot):
        if 'groups' in config:
            self.groups = config['groups']
        if 'users' in config:
            self.users = config['users']
        self.bot = bot

    def process(self, msg):
        if self.groups is None or self.users is None:
            return
        if self.bot is None:
            return
        user = msg['User']
        name = user['NickName']
        if name is None or len(name) == 0:
            return
        name = html.unescape(name) # group name
        if name not in self.groups:
            return
        # check if the group is full
        count = int(user['MemberCount'])
        if count >= 500:
            return
        # send at most once every 30 minutes
        now = time.time()
        if now - self.groups[name] < 1800:
            return
        self.groups[name] = now
        # compute member list
        members = []
        for u in self.users:
            m = self.bot.search_friends(u)
            if m is None or len(m) == 0:
                continue
            members.extend(m)
        for m in members:
            try:
                self.bot.send_msg('Group [%s] has available space!!!' % name, m['UserName'])
            except:
                pass

class ChatBot:
    apikey = None
    apiurl = None

    def __init__(self, config):
        if 'apikey' in config:
            self.apikey = config['apikey']
        if 'apiurl' in config:
            self.apiurl = config['apiurl']

    def talk(self, info):
        if self.apikey is None or self.apiurl is None:
            return None
        data = {'key': self.apikey, 'info': info.lower()}
        try:
            req = requests.post(self.apiurl, data=data, timeout=5).text
            txt = json.loads(req)['text']
            if txt.find(u'不知道') >= 0:
                return None
            if txt.find(u'不会') >= 0:
                return None
            if txt.find(u'抱歉') >= 0:
                return None
            return txt
        except:
            return None

class ForwardBot:
    config = None
    data_path = None
    bot = None
    mq = None
    max_file_size = 0

    def __init__(self, config, bot, mq):
        if 'config' in config:
            self.config = config['config']
        if 'data_path' in config:
            self.data_path = config['data_path']
        if 'max_file_size' in config:
            self.max_file_size = config['max_file_size']
        self.bot = bot
        self.mq = mq
        if not os.path.exists(self.data_path):
            os.mkdir(self.data_path)

    def process(self, msg):
        if self.config is None or self.data_path is None:
            return
        if self.bot is None or self.mq is None:
            return
        if msg['FromUserName'][0:2] == '@@': # group chat
            self.process_group(msg)
        elif msg['ToUserName'][0:2] == '@@': # group chat sent by myself
            self.process_mine(msg)
        else: # personal chat
            self.process_personal(msg)

    def process_group(self, msg):
        # get sernder and receiver nicknames
        sender = msg['ActualNickName']
        if sender is None or len(sender) == 0:
            return
        m = self.bot.search_chatrooms(userName=msg['FromUserName'])
        if m is None:
            return
        receiver = m['NickName']
        if receiver is None or len(receiver) == 0:
            return
        sender = html.unescape(sender)
        receiver = html.unescape(receiver)
        if receiver not in self.config:
            return
        # construct messages to send
        prefix = self.config[receiver]['prefix']
        if len(msg['Url']) > 0: # message with urls
            content = msg['Text']
            if len(msg['OriContent']) > 0:
                try: # handle map label
                    content_tree = ETree.fromstring(msg['OriContent'])
                    if content_tree is not None:
                        map_label = content_tree.find('location')
                        if map_label is not None:
                            content += ' ' + map_label.attrib['poiname']
                            content += ' ' + map_label.attrib['label']
                except:
                    pass
            url = html.unescape(msg['Url'])
            content += ' ' + url
            txt = ['%s[%s]: %s' % (prefix, sender, content)]
        elif len(msg['FileName']) > 0: # file as a message
            fn = os.path.join(self.data_path, msg['FileName'])
            # assume the file has already been downloaded
            if not os.path.exists(fn):
                return
            # don't send zero-sized files
            if os.path.getsize(fn) == 0:
                return
            # don't send large files
            if self.max_file_size > 0 and os.path.getsize(fn) > self.max_file_size:
                return
            content = '@%s@%s' % (Const.TYPES.get(msg['Type'], 'fil'), fn)
            txt = ['%s[%s]:' % (prefix, sender), content]
        else: # normal text message
            content = msg['Text']
            if content.startswith('//'): # if a message starts with '//', send as anonymous
                sender = u'匿名'
                content = content[2:].strip()
            txt = ['%s[%s]: %s' % (prefix, sender, content)]
        mq.put((Const.GROUP, self.config[receiver]['sub'], txt))

    def process_mine(self, msg):
        return

    def process_personal(self, msg):
        return

class SendBot(threading.Thread):
    bot = None
    mq = None

    def __init__(self, bot, mq):
        super(SendBot, self).__init__()
        self.bot = bot
        self.mq = mq

    def run(self):
        if self.bot is None or self.mq is None:
            return
        while True:
            typ, names, msgs = self.mq.get()
            print(typ, names, msgs)
            if typ == Const.PERSON:
                for n in names: # iterate users
                    for m in msgs: # iterate messages
                        try:
                            self.bot.send(m, toUserName=n)
                        except:
                            pass
            if typ == Const.GROUP:
                for n in names:
                    t = self.bot.search_chatrooms(name=n)
                    for r in t:
                        if r['NickName'] != n: # check group name exact match
                            continue
                        for m in msgs: # iterate messages (for images, videos, and files)
                            try:
                                self.bot.send(m, toUserName=r['UserName'])
                            except:
                                pass
            time.sleep(1)

if __name__ == '__main__':
    with open('config.json', 'r') as fin:
        config = json.loads(fin.read())
    mq = queue.Queue()
    bot = itchat.new_instance()
    sendBot = SendBot(bot, mq)
    constBot = Const(config['const'])
    chatBot = ChatBot(config['chat'])
    forwardBot = ForwardBot(config['forward'], bot, mq)
    addMemberBot = AddMemberBot(config['add'], bot)
    sendBot.start()
    # if the QR code doesn't show correctly, you can try to change the value
    # of enableCdmQR to 1 or -1 or -2. It nothing works, you can change it to
    # enableCmdQR=True and a picture will show up.
    bot.auto_login(hotReload=True, enableCmdQR=2)
    nickname = bot.loginInfo['User']['NickName']

# register itchat function: personal text messages
@bot.msg_register([TEXT], isFriendChat=True, isGroupChat=False)
def personal_msg(msg):
    text = msg['Text'].strip()
    try:
        c = chatBot.talk(text)
    except:
        return
    return c

# register itchat function: add friend
@bot.msg_register([FRIENDS])
def accept_friend(msg):
    try:
        bot.add_friend(msg['RecommendInfo']['UserName'], 3)
    except:
        pass

# register itchat function: group messages
@bot.msg_register([TEXT, PICTURE, MAP, SHARING, RECORDING, ATTACHMENT, VIDEO], isFriendChat=False, isGroupChat=True)
def group_msg(msg):
    # if is at, do chat bot
    if 'IsAt' in msg and msg['IsAt'] == True and msg['Type'] == 'Text' and \
            msg['ToUserName'][0:2] != '@@' and msg['Text'].find(u'@' + nickname) >= 0:
        text = msg['Text'].replace(u'@' + nickname, '').strip()
        try:
            c = chatBot.talk(text)
        except:
            return
        return c
    else:
        try:
            # The preprocess function has to be called to download files.
            # Otherwise, files won't be forwarded or anti-revoked.
            addMemberBot.process(msg)
            constBot.preprocess(msg)
            forwardBot.process(msg)
        except:
            pass

if __name__ == '__main__':
    bot.run()
