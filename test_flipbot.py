''' Flipbot tests '''

import flipbot

def test_link_matcher():
    match = flipbot.link_re.match
    assert match('<http://wordaligned.org>')
    assert match('<http://wordaligned.org|wordaligned.org>')

    search = flipbot.link_re.search 
    m = search('Flip it! <https://flip.it>')
    assert m
    assert m.group(1) == 'https://flip.it'
    assert m.group(2) == m.group(3) == ''

    m = search('Flip it! <https://flip.it|flip.it> good')
    assert m
    assert m.group(1) == 'https://flip.it'
    assert m.group(2) == '|'
    assert m.group(3) == 'flip.it'

def test_link_flipper():
    flip_fn = lambda s: s[::-1]
    echo_fn = str.upper

    assert (flipbot.flip_text_with_links(
        'FLIP it! <https://flip.it|Flip.It> Good',
        flip_fn, echo_fn)
            == 'dooG <HTTPS://FLIP.IT|tI.pilF> !ti PILF')
