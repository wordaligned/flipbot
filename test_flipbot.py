''' Flipbot tests '''

import flipbot

def test_markup_matcher():
    match = flipbot.markup_re.match
    assert match(':smiley:')
    assert match(':+1:')
    assert match(':fb-wow:')
    assert match('<http://wordaligned.org>')
    assert match('<http://wordaligned.org|wordaligned.org>')
    assert match('<@USER>')
    assert match('<@USER123|thomas>')
    assert match('<#CHANNEL>')
    assert match('<#CHANNEL|name>')
    assert match('<!here>')
    assert match('<!everyone|folks>')

    search = flipbot.markup_re.search
    m = search('Nice :+1:')
    assert m
    assert m.group(1) == ':+1:'
    assert not m.group(2)

    m = search('Flip it! <https://flip.it>')
    assert m
    assert not m.group(1)
    assert m.group(2) == 'https://flip.it'

    m = search('Flip it! <https://flip.it|flip.it> good')
    assert m
    assert not m.group(1)
    assert m.group(2) == 'https://flip.it|flip.it'

    m = search('Hello <@USER123>!')
    assert m
    assert not m.group(1)
    assert m.group(2) == '@USER123'    


def test_unescape():
    unescape = lambda s: flipbot.FlipMarkedupText.unescape(None, s)
    assert unescape('and &amp; lt &lt; gt &gt;') == 'and & lt < gt >'
    assert unescape('&quot;') == '&quot;'


class MarkupHandler(flipbot.FlipMarkedupText):
    def echo(self, s):
        return 'E(%s)' % s

    def flip(self, s):
        return 'F(%s)' % s if s else ''

    def emoji(self, s):
        return 'J(%s)' % s
    
def test_flip_markedup_text():
    users = {'@USER1': 'thomas'}
    handler = MarkupHandler(users)
    flipper = flipbot.flip_markedup_text
    assert (flipper('I :+1: this!', handler) ==
                    'F( this!)J(:+1:)F(I )')
    assert (flipper('go to <http://example.com|example>', handler) ==
                    '<E(http://example.com)|F(example)>F(go to )')
    assert (flipper('<!rotate><@USER1><@NOT_A_USER>', handler) == 
                    '<E(@NOT_A_USER)><E(@USER1)|F(thomas)><E(!rotate)>')
