#!/usr/bin/env python

import sys
import os
import re
import os
import os.path
from glob import glob
import datetime

from lxml import etree
import iso8601

sys.path.insert(0, '.')

from ocd_backend.settings import HTML_PATH

def extract_date_from_meta(html):
    parsed_granularity =12
    date_str = None
    # meta_terms = ['DCTERMS.modified', 'dcterms:modified']
    meta_terms = ['DCTERMS.available', 'dcterms:available']
    for meta_term in meta_terms:
        if not date_str:
            date_str = u''.join(
                html.xpath('//meta[@name="%s"]/@content' % (meta_term,)))
    try:
        parsed_date = iso8601.parse_date(date_str)
    except iso8601.ParseError:
        parsed_date = None
        parsed_granularity = 0
    return parsed_date, parsed_granularity

def extract_iso8601_date(contents):
    parsed_granularity = 12
    parsed_date = None
    matches = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', contents)
    if matches is not None:
        try:
            parsed_date = iso8601.parse_date(matches.group(1))
        except iso8601.ParseError:
            parsed_date = None
            parsed_granularity = 0
    return parsed_date, parsed_granularity

def extract_text_date(contents):
    parsed_granularity = 12
    parsed_date = None

    # assumes text
    date_str = contents
    date_match = re.search(r'(?P<d>\d{1,2})-(?P<m>\d{2})-(?P<y>\d{4})', date_str)
    if not date_match:
        date_match = re.search((
            r'(?P<d>\d+)\s+(?P<m>januari|februari|maart|april|mei|juni|juli|augustus|'
            r'september|oktober|november|december)\s+(?P<y>\d{4})'), date_str)
    if not date_match:
        date_match = re.search((
            r'(?P<d>\d+)\s+(?P<m>jan\.|feb\.|mar\.|apr\.|mei|jun\.|jul\.|aug\.|'
            r'sep\.|okt\.|nov\.|dec\.)\s+(?P<y>\d{4})'), date_str)
    if date_match is not None:
        date_conversions = {
            'januari': '01', 'februari': '02', 'maart': '03',
            'april': '04', 'mei': '05', 'juni': '06', 'juli': '07',
            'augustus': '08', 'september': '09', 'oktober': '10',
            'november': '11', 'december': '12', 'jan.': '01',
            'feb.': '02', 'mar.': '03', 'apr.': '04', 'mei': '05',
            'jun.': '06', 'jul.': '07', 'aug.': '08', 'sep.': '09',
            'okt.': '10', 'nov.': '11', 'dec.': '12'}
        if len(date_match.group('d')) <= 1:
            date_prefix = '' if date_match.group('d').startswith('0') else '0'
        else:
            date_prefix = ''
        mnth = date_conversions.get(
            date_match.group('m'), date_match.group('m'))
        date_semi_parsed = u'%s-%s-%s%sT00:00:00' % (
            date_match.group('y'), mnth,
            date_prefix, date_match.group('d'),)
        try:
            parsed_date = iso8601.parse_date(
                date_semi_parsed)
            parsed_granularity = 12
        except LookupError:
            parsed_granularity = 0
            pass
    return parsed_date, parsed_granularity

def extract_date(html, contents):
    parsed_date, parsed_granularity = extract_date_from_meta(html)
    if parsed_date is None:
        parsed_date, parsed_granularity = extract_iso8601_date(contents)
    if parsed_date is None:
        parsed_date, parsed_granularity = extract_text_date(contents)

    return parsed_date, parsed_granularity

def main(argv):
    for h in glob(os.path.join(HTML_PATH, '*.html')):
        with open(h, 'r') as in_file:
            contents = in_file.read()
        html = etree.HTML(contents)
        d, g = extract_date(html, contents)
        print("%s: %s / %s" % (h, g, d,))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
