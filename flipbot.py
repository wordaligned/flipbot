''' Flipbot flips text and images posted to slack channels.

Thomas Guest, https://github.com/wordaligned/flipbot
'''

import configparser
import html
import io
import json
import os
import pprint
import re
import sys
import time

from PIL import Image
import requests
import slackclient
import upsidedown

import  emoji

# Read Slack API token and the bot user name from settings.ini
config = configparser.ConfigParser()
config.read('settings.ini')

TOKEN = config['SETTINGS']['TOKEN']
USER = config['SETTINGS']['USER']
VERBOSE = config['SETTINGS'].getboolean('VERBOSE')

class FlipClient:
    '''Slack RTM client which flips messages.'''

    def __init__(self, token, user):
        self._client = slackclient.SlackClient(token)
        self._user = user
        self._api_call = self._client.api_call
        if self._client.rtm_connect():
            print("Flipbot connected and running!")
            self._find_users()
            self._flipper = FlipMarkedupText(self._users)
        else:
            print("Connection failed. Invalid Slack token or bot ID?")

    def _react(self, msg):
        '''React to the message with a flipped emoji.'''
        self._api_call('reactions.add',
                       channel=msg['channel'],
                       timestamp=msg['ts'],
                       name=reaction())

    def _flip_image_message(self, msg):
        '''Respond to an image upload by posting a flipped version.'''
        f = msg['file']
        fname = f['name']
        url = f['url_private_download']
        meta = flip_file_metadata(f, self._flipper)

        hdrs = {'Authorization': 'Bearer %s' % TOKEN}
        resp = requests.get(url, headers=hdrs)
        if resp.status_code == 200:
            self._api_call('files.upload',
                           filename=self._flipper.flip(fname),
                           channels=msg['channel'],
                           file=flip_image(resp.content),
                           **meta)
        else:
            print('Download failed', resp.content)

    def _flip_text_message(self, msg):
        '''Respond to the text message by posting a flipped version.'''
        text = msg['text']
        self._api_call('chat.postMessage',
                       channel=msg['channel'],
                       text=flip_markedup_text(text, self._flipper),
                       as_user=True)

    def _find_users(self):
        r = self._client.api_call('users.list')
        if r['ok']:
            self._users = {'@' + m['id']: m['name'] for m in r['members']}

    def _handle(self, msg):
        if msg.get('user') == self._user:
            return # Don't reprocess our own messages!
        try:
            if VERBOSE:
                pprint.pprint(msg)
            if is_user_change(msg):
                self._find_users()
            elif is_image_message(msg):
                self._flip_image_message(msg)
                self._react(msg)
            elif is_text_message(msg):
                self._flip_text_message(msg)
                self._react(msg)
        except Exception as e:
            print(e, file=sys.stderr)

    def _messages(self):
        while True:
            yield from self._client.rtm_read()
            time.sleep(1)

    def run(self):
        for msg in self._messages():
            self._handle(msg)

def is_user_change(msg):
    '''Return true if the users have been changed.'''
    return msg['type'] in {'user_change',
                           'team_join',
                           'bot_added',
                           'bot_updated'}

def reaction():
    '''Return a reaction (emoji)'''
    return emoji.wrong_way_up()

# https://api.slack.com/docs/message-formatting#how_to_display_formatted_messages
markup_re = re.compile(
    '(:[-a-z0-9_\+]+:)'
    '|'
    '<(.*?)>')

class FlipMarkedupText:
    '''Text flip functions.'''
    def __init__(self, users):
        # The users arg maps from user id to user name, and is used to flip
        # <@USER|name> markup.
        self._users = users

    def unescape(self, s):
        '''Reverse the escapes used in slack markup.'''
        return s.replace(
            '&lt;', '<').replace(
            '&gt;', '>').replace(
            '&amp;', '&')

    def echo(self, s):
        '''Returns the text, unmodified'''
        return s

    def flip(self, s):
        '''Flip latin characters in s to create an "upside-down" impression.'''
        s = self.unescape(s)
        return upsidedown.transform(s)

    def emoji(self, s):
        '''Flips an emoji.'''
        return emoji.flip(s)

    def link(self, url, s):
        '''Flips a link, keeping the target unchanged.'''
        return '<{}{}>'.format(self.echo(url), '|' + self.flip(s) if s else '')

    def user(self, userid, s):
        '''Flips a user reference, keeping the target user unchanged.'''
        s = s if s else self._users.get(userid)
        return self.link(userid, s)

    command = channel = link

def flip_markedup_text(text, flipper):
    '''Flips text containing slack markup.

    See: https://api.slack.com/docs/message-formatting

    The intention here is to render the upside down text, whilst
    retaining link and user references, and identifying and flipping
    emojis
    '''
    def flip_markup(m):
        if m.group(1):
            return flipper.emoji(m.group(1))
        else:
            ref, _, desc = m.group(2).partition('|')
            return {
                '@': flipper.user,
                '#': flipper.channel,
                '!': flipper.command
                }.get(ref[0], flipper.link)(ref, desc)

    chunks = []
    pos = 0
    for m in markup_re.finditer(text):
        chunks.append(flipper.flip(text[pos:m.start()]))
        chunks.append(flip_markup(m))
        pos = m.end()
    chunks.append(flipper.flip(text[pos:]))

    return ''.join(reversed(chunks))

def is_text_message(msg):
    '''Return True if the message is simple text.'''
    return msg.get('type') == 'message' and not msg.get('subtype')

def is_image_message(msg):
    '''Return True if the message is an image upload.'''
    return (msg.get('type') == 'message' and
            msg.get('subtype') == 'file_share' and
            msg['file']['mimetype'].startswith('image'))

def flip_file_metadata(f, flipper):
    '''Returns flipped upload file metadata.'''
    meta = {}
    title = f.get('title')
    comment = f.get('initial_comment', {}).get('comment')
    if title:
        meta['title'] = flip_markedup_text(title, flipper)
    if comment:
        meta['initial_comment'] = flip_markedup_text(comment, flipper)
    return meta

def flip_image(img_bytes):
    '''Returns binary image data representing a flipped version of the input data.'''
    stream = io.BytesIO(img_bytes)
    img = Image.open(stream)
    out = img.rotate(180)
    stream = io.BytesIO()
    out.save(stream, format=img.format)
    stream.seek(0)
    return stream.read()

if __name__ == "__main__":
    client = FlipClient(TOKEN, USER)
    client.run()
