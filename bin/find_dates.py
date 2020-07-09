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
    parsed_granularity = 12
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


def extract_date(html, contents):
    parsed_date, parsed_granularity = extract_date_from_meta(html)
    if parsed_date is None:
        parsed_date, parsed_granularity = extract_iso8601_date(contents)
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
