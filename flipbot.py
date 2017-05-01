''' Flipbot flips text and images posted to slack channels. 

Thomas Guest, https://github.com/wordaligned/flipbot
'''

import configparser
import io
import json
import os
import pprint
import random
import re
import sys
import time

from PIL import Image
import requests
import slackclient
import upsidedown

# Read Slack API token and the bot user name from settings.ini
config = configparser.ConfigParser()
config.read('settings.ini')

TOKEN = config['SETTINGS']['TOKEN']
USER = config['SETTINGS']['USER']

class FlipClient:
    '''Slack RTM client which flips messages.'''

    def __init__(self, token, user):
        self._client = slackclient.SlackClient(token)
        self._user = user
        self._api_call = self._client.api_call
        if self._client.rtm_connect():
            print("Flipbot connected and running!")
            self._find_users()
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
        meta = flip_file_metadata(f)

        hdrs = {'Authorization': 'Bearer %s' % TOKEN}
        resp = requests.get(url, headers=hdrs)
        if resp.status_code == 200:
            self._api_call('files.upload',
                           filename=flip_text(fname),
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
                       text=flip_text_with_links(text),
                       as_user=True)

    def _find_users(self):
        r = self._client.api_call('users.list')
        if r['ok']:
            self._users = {m['id']: m['name'] for m in r['members']}

    def _messages(self):
        while True:
            yield from self._client.rtm_read()
            time.sleep(1)

    def _handle(self, msg):
        try:
            if msg.get('user') == self._user:
                pass # Don't reprocess our own messages!
            elif is_image_message(msg):
                self._flip_image_message(msg)
                self._react(msg)
            elif is_text_message(msg):
                self._flip_text_message(msg)
                self._react(msg)
        except Exception as e:
            print(e, file=sys.stderr)

    def run(self):
        for msg in self._messages():
            if is_user_change(msg):
                self._find_users()
            self._handle(msg)

def is_user_change(msg):
    '''Return true if the users have been changed.'''
    return msg['type'] in {'user_change',
                           'team_join',
                           'bot_added',
                           'bot_updated'}

def reaction():
    '''Return a reaction (emoji)'''
    return random.choice(
        'upside_down_face umbrella flag-au arrows_counterclockwise'.split())

def flip_text(s):
    '''Flip latin characters in s to create an "upside-down" impression.'''
    return upsidedown.transform(s)

def echo_text(s):
    '''Returns the text, unmodified'''
    return s

link_re = re.compile('<(https?://[^|>]*)(\|?)([^>]*)>')

def flip_text_with_links(s, flip_fn=flip_text, echo_fn=echo_text):
    '''Handles links in the message, s.

    See: https://api.slack.com/docs/message-formatting#linking_to_urls


    Any URL in s will look something like <http://www.foo.com|www.foo.com>
    We keep the link functional by flipping the text following the pipe,
    (www.foo.com) and keeping the text before the pipe unchanged.
    '''
    def repl(m):
        return '<{}{}{}>'.format(
            echo_fn(m.group(1)), m.group(2), flip_fn(m.group(3)))

    chunks = []
    pos = 0
    for m in link_re.finditer(s):
        chunks.append(flip_fn(s[pos:m.start()]))
        chunks.append(repl(m))
        pos = m.end()
    chunks.append(flip_fn(s[pos:]))

    return ''.join(reversed(chunks))

def is_text_message(msg):
    '''Return True if the message is simple text.'''
    return msg.get('type') == 'message' and not msg.get('subtype')

def is_image_message(msg):
    '''Return True if the message is an image upload.'''
    return (msg.get('type') == 'message' and
            msg.get('subtype') == 'file_share' and
            msg['file']['mimetype'].startswith('image'))

def flip_file_metadata(f):
    '''Returns flipped upload file metadata.'''
    meta = {}
    title = f.get('title')
    comment = f.get('initial_comment', {}).get('comment')
    if title:
        meta['title'] = flip_text(title)
    if comment:
        meta['initial_comment'] = flip_text_with_links(comment)
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
