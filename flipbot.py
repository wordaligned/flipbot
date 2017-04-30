''' Flipbot flips text and images posted to slack channels. '''

import configparser
import io
import os
import random
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

def reaction():
    '''Return a reaction (emoji)'''
    return random.choice(
        'upside_down_face umbrella flag-au arrows_counterclockwise'.split())

def flip_text(s):
    '''Flip latin characters in s to create an "upside-down" impression.'''
    return upsidedown.transform(s)

def is_text_message(msg):
    '''Return True if the message is simple text.'''
    return msg.get('type') == 'message' and not msg.get('subtype')

def is_image_message(msg):
    '''Return True if the message is an image upload.'''
    return (msg.get('type') == 'message' and
            msg.get('subtype') == 'file_share' and
            msg['file']['mimetype'].startswith('image'))

def flip_text_message(client, msg):
    '''Respond to the text message by posting a flipped version.'''
    client.api_call('chat.postMessage',
                    text=flip_text(msg['text']),
                    channel=msg['channel'],
                    as_user=True)

def flip_file_metadata(f):
    '''Returns flipped upload file metadata.'''
    meta = {}
    title = f.get('title')
    comment = f.get('initial_comment', {}).get('comment')
    if title:
        meta['title'] = flip_text(title)
    if comment:
        meta['initial_comment'] = flip_text(comment)
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

def flip_image_message(client, msg):
    '''Respond to an image upload by posting a flipped version.'''
    f = msg['file']
    fname = f['name']
    url = f['url_private_download']
    meta = flip_file_metadata(f)

    hdrs = {'Authorization': 'Bearer %s' % TOKEN}
    resp = requests.get(url, headers=hdrs)
    if resp.status_code == 200:
        client.api_call('files.upload',
                        filename=flip_text(fname),
                        channels=msg['channel'],
                        file=flip_image(resp.content),
                        **meta)
    else:
        print('Download failed', resp.content)

def react(client, msg):
    '''React to the message with a flipped emoji.'''
    client.api_call('reactions.add',
                    channel=msg['channel'],
                    timestamp=msg['ts'],
                    name=reaction())

def handle(client, messages):
    '''Respond to a list of messages.'''
    for msg in messages:
        try:
            if msg.get('user') == USER:
                pass # Don't reprocess our own messages!
            else:
                if is_image_message(msg):
                    flip_image_message(client, msg)
                    react(client, msg)
                elif is_text_message(msg):
                    flip_text_message(client, msg)
                    react(client, msg)
        except Exception as e:
            print(e, file=sys.stderr)

def run(client):
    '''Run flipbot.'''
    while True:
        handle(client, client.rtm_read())
        time.sleep(1)

if __name__ == "__main__":
    client = slackclient.SlackClient(TOKEN)
    if client.rtm_connect():
        print("Flipbot connected and running!")
        run(client)
    else:
        print("Connection failed. Invalid Slack token or bot ID?")
