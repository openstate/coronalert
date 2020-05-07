#!/usr/bin/env python
from datetime import datetime
import csv
import codecs
import json
from glob import glob
import gzip
from hashlib import sha1
import os
import re
import requests
import sys
import time
from urlparse import urljoin
from pprint import pprint

import click
from click.core import Command
from click.decorators import _make_command

from elasticsearch import Elasticsearch
from lxml import etree
import requests


LOCATIONS = []


class UTF8Recoder:
    """
    Iterator that reads an encoded stream and reencodes the input to UTF-8
    """
    def __init__(self, f, encoding):
        self.reader = codecs.getreader(encoding)(f)

    def __iter__(self):
        return self

    def next(self):
        return self.reader.next().encode("utf-8")


class UnicodeReader:
    """
    A CSV reader which will iterate over lines in the CSV file "f",
    which is encoded in the given encoding.
    """

    def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
        f = UTF8Recoder(f, encoding)
        self.reader = csv.reader(f, dialect=dialect, **kwds)

    def next(self):
        row = self.reader.next()
        return [unicode(s, "utf-8") for s in row]

    def __iter__(self):
        return self


def command(name=None, cls=None, **attrs):
    """
    Wrapper for click Commands, to replace the click.Command docstring with the
    docstring of the wrapped method (i.e. the methods defined below). This is
    done to support the autodoc in Sphinx, and the correct display of
    docstrings
    """
    if cls is None:
        cls = Command

    def decorator(f):
        r = _make_command(f, name, attrs, cls)
        r.__doc__ = f.__doc__
        return r
    return decorator


def _get_normalized_locations():
    loc_path = os.path.join(
        os.path.dirname(__file__),
        '../ocd_backend/data/cbs-name2018-mapping.csv')
    result = {}
    with open(loc_path) as locations_in:
        locations = UnicodeReader(locations_in)
        headers = locations.next()
        for location in locations:
            record = dict(zip(headers, location))
            result[record[u'Key_poliflw']] = record[u'Alt_map']
    return result


def _normalize_location(location):
    if unicode(location) in LOCATIONS:
        return LOCATIONS[unicode(location)]
    return unicode(location)


def _enrichments_config():
    return [
        [
            "ocd_backend.enrichers.NEREnricher",
            {}
        ]
    ]


def _generate_for_pvdd(name):
    def _generate_for_pvdd_subsite(name, link):
        m = re.match(r'^https?\:\/\/w?w?w?\.?([^\.]+)', link)
        if m is not None:
            slug = m.group(1)
        else:
            slug = None
        url = os.path.join(link, 'nieuws')
        return [{
            "id": "pvdd_" + slug,
            "location": _normalize_location(name),
            "extractor": "ocd_backend.extractors.pvdd.PVDDExtractor",
            "transformer": "ocd_backend.transformers.BaseTransformer",
            "item": "ocd_backend.items.pvdd.PVDDItem",
            "enrichers": _enrichments_config(),
            "loader": "ocd_backend.loaders.ElasticsearchLoader",
            "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
            "hidden": False,
            "index_name": "pvdd",
            "collection": "Partij voor de Dieren",
            "file_url": url,
            "keep_index_on_update": True
        }]

    resp = requests.get('https://gemeenten.partijvoordedieren.nl/over-de-gemeenteraadsfracties', verify=False)
    html = etree.HTML(resp.content)
    party_elems = html.xpath('//article/p//a')
    result = []
    for party_elem in party_elems:
        local_name = u''.join(party_elem.xpath('.//text()'))
        try:
            local_link = party_elem.xpath('./@href')[0]
        except LookupError:
            local_link = None
        if local_link is not None and not local_link.endswith('pdf'):
            result += _generate_for_pvdd_subsite(local_name, local_link)
    return result


def _generate_for_groenlinks(name):
    def _generate_for_groen_links_subsite(name, link):
        m = re.match(r'^https?\:\/\/w?w?w?\.?([^\.]+)', link)
        if m is not None:
            slug = m.group(1)
        else:
            slug = None
        return [
            {
                "id": "groenlinks_" + slug,
                "location": _normalize_location(name),
                "extractor": "ocd_backend.extractors.paging.PagedStaticHtmlExtractor",
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "file_url": urljoin(link, "/nieuws"),
                "item": "ocd_backend.items.html.HTMLPageItem",
                "enrichers": _enrichments_config(),
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False,
                "index_name": "groenlinks",
                "collection": "GroenLinks",
                "keep_index_on_update": True,
                "item_xpath": "//article[contains(@class, \"node-newsarticle\")]",
                "item_link_xpath": "(.//h1//a/@href)[1]",
                "content_xpath": "//div[contains(@class, \"intro\")]|//div[@class=\"content\"]",
                "title_xpath": "//title//text()",
                "date_xpath": "//span[contains(@class, \"submitted-date\")]//text()",

            },
            {
                "extractor": "ocd_backend.extractors.paging.PagedStaticHtmlExtractor",
                "keep_index_on_update": True,
                "enrichers": _enrichments_config(),
                "index_name": "groenlinks",
                "collection": "GroenLinks",
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "item_xpath": "//article[contains(@class, \"node-newsarticle\")]",
                "item_link_xpath": "(.//h1//a/@href)[1]",
                "paging_xpath": "//li[@class=\"pager-next\"]/a/@href",
                "content_xpath": "//div[contains(@class, \"intro\")]|//div[@class=\"content\"]",
                "title_xpath": "//title//text()",
                "date_xpath": "//span[contains(@class, \"submitted-date\")]//text()",
                "id": "groenlinks_archives_" + slug,
                "location": _normalize_location(name),
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "file_url": urljoin(link, "/nieuws"),
                "item": "ocd_backend.items.html.HTMLPageItem",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False
            }
        ]

    resp = requests.get('https://groenlinks.nl/lokaal')
    html = etree.HTML(resp.content)
    party_elems = html.xpath(
        '//ul[@class="clearfix province-departments-list"]//li/a')
    result = []
    for party_elem in party_elems:
        local_name = u''.join(party_elem.xpath('.//text()'))
        try:
            local_link = party_elem.xpath('./@href')[0]
        except LookupError:
            local_link = None
        if local_link is not None:
            result += _generate_for_groen_links_subsite(local_name, local_link)
    return result


def _generate_for_cda(name):
    def _generate_for_cda_subsite(name, link):
        prefix = u'' if link.startswith('/') else '/'
        feed_url = u'%s%s%s%s' % (
            'https://www.cda.nl', prefix,  link, u'nieuws.rss',)
        try:
            slug = link.split('/')[-2].replace('-', '_')
        except LookupError:
            slug = u''
        return [
            {
                "id": u"cda_%s" % (slug,),
                "location": _normalize_location(name),
                "extractor": "ocd_backend.extractors.feed.FeedExtractor",
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "item": "ocd_backend.items.feed.FeedItem",
                "enrichers": _enrichments_config(),
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False,
                "index_name": "cda",
                "collection": "CDA",
                "file_url": feed_url,
                "keep_index_on_update": True
            },
            {
                "extractor": "ocd_backend.extractors.paging.PagedStaticHtmlExtractor",
                "keep_index_on_update": True,
                "enrichers": _enrichments_config(),
                "index_name": "cda",
                "collection": "CDA",
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "item_xpath": "//*[@id=\"mainContent\"]/section/div/div/div/div/div/a",
                "item_link_xpath": "(./@href)[1]",
                "paging_xpath": "//li[contains(@class, \"pagination-next\")]/a/@href",
                "content_xpath": "//div[contains(@class, \"widePhoto\")]//img|//div[@id=\"readSpeakerContent\"]//p",
                "title_xpath": "//h1//text()",
                "date_xpath": "(//div[contains(@class, \"widePhoto-content\")])[1]//span//text()",
                "id": u"cda_archives_%s" % (slug,),
                "location": _normalize_location(name),
                "transformer": "ocd_backend.transformers.BaseTransformer",
                # "file_url": "https://www.cda.nl/overijssel/dinkelland/actueel/nieuws/",
                "file_url": urljoin('https://www.cda.nl', urljoin(link, 'actueel/nieuws')),
                "item": "ocd_backend.items.html.HTMLPageItem",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False
            }
        ]

    resp = requests.get('https://www.cda.nl/partij/afdelingen/')
    html = etree.HTML(resp.content)
    party_elems = html.xpath(
        '//div[@class="panel-mainContent"]//select[@class="redirectSelect"]//option')
    result = []
    for party_elem in party_elems:
        local_name = u''.join(party_elem.xpath('.//text()')).strip()
        try:
            local_link = party_elem.xpath('./@value')[0]
        except LookupError:
            local_link = None
        if local_link is not None:
            result += _generate_for_cda_subsite(local_name, local_link)
    return result


def _generate_for_cu(name):
    def _generate_for_cu_subsite(name, link):
        m = re.match(r'^https?\:\/\/w?w?w?\.?([^\.]+)', link)
        if m is not None:
            slug = m.group(1)
        else:
            slug = None

        resp = requests.get(link)
        html = etree.HTML(resp.content)
        feeds = html.xpath('//link[@type="application/rss+xml"]')

        result = []
        feed_idx = 0
        for feed in feeds:
            feed_idx += 1
            feed_url = u''.join(feed.xpath('./@href'))
            result.append({
                "id": u"cu_%s_%s" % (slug.replace('-', '_'), feed_idx,),
                "location": _normalize_location(name),
                "extractor": "ocd_backend.extractors.feed.FeedExtractor",
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "item": "ocd_backend.items.feed.FeedItem",
                "enrichers": _enrichments_config(),
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False,
                "index_name": "christenunie",
                "collection": "ChristenUnie",
                "file_url": feed_url,
                "keep_index_on_update": True
            })
        return result

    resp = requests.get('https://www.christenunie.nl/lokaal-en-provinciaal')
    html = etree.HTML(resp.content)
    party_elems = html.xpath(
        '//form[@name="formName2"]/select//option')
    result = []
    for party_elem in party_elems:
        local_name = u''.join(party_elem.xpath('.//text()')).strip()
        try:
            local_link = party_elem.xpath('./@value')[0]
        except LookupError:
            local_link = None
        if local_link is not None:
            result += _generate_for_cu_subsite(local_name, local_link)
    return result


def _generate_for_vvd(name):
    def _generate_for_vvd_subsite(name, feed_url, feed_idx):
        m = re.match(r'^https?\:\/\/w?w?w?\.?([^\.]+)', feed_url)
        if m is not None:
            slug = m.group(1)
        else:
            slug = None

        result = []
        result.append({
            "id": u"vvd_%s_%s" % (slug.replace('-', '_'), feed_idx,),
            "location": _normalize_location(name),
            "extractor": "ocd_backend.extractors.feed.FeedExtractor",
            "transformer": "ocd_backend.transformers.BaseTransformer",
            "item": "ocd_backend.items.feed.FeedFullTextItem",
            "enrichers": _enrichments_config(),
            "loader": "ocd_backend.loaders.ElasticsearchLoader",
            "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
            "hidden": False,
            "index_name": "vvd",
            "collection": "VVD",
            "file_url": feed_url,
            "keep_index_on_update": True,
            "content_xpath": "//div[@class=\"article__intro\"]|//div[@class=\"article__content\"]"
        })
        result.append({
            "extractor": "ocd_backend.extractors.vvd.VVDHtmlExtractor",
            "keep_index_on_update": True,
            "enrichers": _enrichments_config(),
            "index_name": "vvd",
            "collection": "VVD",
            "loader": "ocd_backend.loaders.ElasticsearchLoader",
            "item_xpath": "//ul[@class=\"archive__list overview__list\"]//li",
            "item_link_xpath": "(./a/@href)[1]",
            "paging_xpath": "//ul[contains(@class, \"pagination\")]//a[@aria-label=\"Next\"]/@href",
            "content_xpath": "//div[@class=\"article__intro\"]|//div[@class=\"article__content\"]",
            "title_xpath": "//h1[@class=\"article__heading\"]//text()",
            "date_xpath": "(//span[@item-prop=\"date\"])[1]//text()",
            "id": u"vvd_archives_%s_%s" % (slug.replace('-', '_'), feed_idx,),
            "location": _normalize_location(name),
            "transformer": "ocd_backend.transformers.BaseTransformer",
            "file_url": urljoin(feed_url, '/'),
            "item": "ocd_backend.items.html.HTMLPageItem",
            "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
            "hidden": False
        })
        return result

    result = []

    session = requests.session()

    with open('vvd.txt') as IN:
        lines = list(UnicodeReader(IN))

        feed_idx = 0
        for line in lines:
            print >> sys.stderr, line
            feed_idx += 1

            rss_url = 'http://' + line[0] + '/feeds/nieuws.rss'

            # Get name from CSV or website
            if len(line) == 3:
                name = line[2]
                if line[1]:
                    rss_url = 'http://' + line[0] + line[1]
            else:
                url = 'http://' + line[0]
                resp = session.get(url, verify=False)
                html = etree.HTML(resp.content)
                name = html.xpath('.//span[@class="site-logo__text"]/text()')[0]

            # Get RSS feed path from CSV or assume default '/feeds/nieuws.rss'
            if len(line) == 2:
                rss_url = 'http://' + line[0] + line[1]

            result += _generate_for_vvd_subsite(name, rss_url, feed_idx)
            time.sleep(2)
    return result


def _generate_for_d66(name):
    def _generate_for_d66_subsite(name, link):
        m = re.match(r'^w?w?w?\.?([^\.]+)', link.replace('http://', '').replace('https', ''))
        if m is not None:
            slug = m.group(1)
        else:
            slug = None

        feed_url = "%s/feed/" % (link,)
        return [
            {
                "id": u"d66_%s" % (slug.replace('-', '_'),),
                "location": _normalize_location(name),
                "extractor": "ocd_backend.extractors.feed.FeedExtractor",
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "item": "ocd_backend.items.feed.FeedItem",
                "enrichers": _enrichments_config(),
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False,
                "index_name": "d66",
                "collection": "D66",
                "file_url": feed_url,
                "keep_index_on_update": True
            },
            {
                "extractor": "ocd_backend.extractors.paging.PagedStaticHtmlExtractor",
                "keep_index_on_update": True,
                "enrichers": _enrichments_config(),
                "index_name": "d66",
                "collection": "D66",
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "item_xpath": "//article[contains(@class, \"news-item\")]",
                "item_link_xpath": "(.//h2//a/@href)[1]",
                "paging_xpath": "//div[@class=\"pager\"]/a[contains(@class, \"next\")]/@href",
                "content_xpath": "//section[@class=\"readable\"]/img|//section[@class=\"readable\"]/p",
                "title_xpath": "//div[@class=\"content\"]//h1//text()",
                "date_xpath": "(//span[contains(@class, \"label\")])[1]//text()",
                "id": u"d66_archives_%s" % (slug.replace('-', '_'),),
                "location": _normalize_location(name),
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "file_url": urljoin(feed_url, "/actueel/"),
                "item": "ocd_backend.items.html.HTMLPageItem",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False
            }
        ]

    resp = requests.get('https://d66.nl/partij/d66-het-land/')
    html = etree.HTML(resp.content)
    provinces = html.xpath('//a[@class="tile-thumb"]/@href')
    result = []
    for province in provinces:
        province_resp = requests.get(province)
        province_html = etree.HTML(province_resp.content)
        party_elems = province_html.xpath('//div[@id="rs-content"]//p/a')
        for party_elem in party_elems:
            local_name = u''.join(party_elem.xpath('.//text()')).strip()
            try:
                local_link = party_elem.xpath('./@href')[0]
            except LookupError:
                local_link = None
            if local_link is not None:
                result += _generate_for_d66_subsite(local_name, local_link)
    return result


def _generate_for_sp(name):
    def _generate_for_sp_subsite(name, link):
        m = re.match(r'^https?\:\/\/w?w?w?\.?([^\.]+)', link)
        if m is not None:
            slug = m.group(1)
        else:
            slug = None
        feed_url = os.path.join(link, 'rss.xml')
        try:
            requests.head(feed_url)
        except (
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError
        ):
            feed_url = os.path.join(link, 'feed')
        return [
            {
                "id": "sp_" + slug,
                "location": _normalize_location(
                    unicode(name).replace('SP ', '')),
                "extractor": "ocd_backend.extractors.feed.FeedExtractor",
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "item": "ocd_backend.items.feed.FeedFullTextItem",
                "enrichers": _enrichments_config(),
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False,
                "index_name": "sp",
                "collection": "SP",
                "file_url": feed_url,
                "keep_index_on_update": True,
                "content_xpath": "//div[contains(@class, \"node-content\")]"
            },
            {
                "extractor": "ocd_backend.extractors.paging.PagedStaticHtmlExtractor",
                "keep_index_on_update": True,
                "enrichers": _enrichments_config(),
                "index_name": "sp",
                "collection": "SP",
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "item_xpath": "//div[contains(@class, \"node-nieuwsitem\")]",
                "item_link_xpath": "(.//h2//a/@href)[1]",
                "paging_xpath": "//ul[@class=\"pager\"]/li[@class=\"pager-next\"]/a/@href",
                "content_xpath": "//div[contains(@class, \"node-content\")]",
                "title_xpath": "//div[@class=\"content\"]//h2[@class=\"title\"]//text()",
                "date_xpath": "(//div[contains(@class, \"pub-date\")])[1]//text()",
                "id": "sp_archives_" + slug,
                "location": _normalize_location(
                    unicode(name).replace('SP ', '')),
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "file_url": urljoin(feed_url, "/nieuws"),
                "item": "ocd_backend.items.html.HTMLPageItem",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False
            }
        ]

    resp = requests.get('https://www.sp.nl/wij-sp/lokale-afdelingen')
    html = etree.HTML(resp.content)
    party_elems = html.xpath(
        '//ul[@class="afdelingen-overview"]//li/a')
    result = []
    for party_elem in party_elems:
        local_name = u''.join(party_elem.xpath('.//text()'))
        try:
            local_link = party_elem.xpath('./@href')[0]
        except LookupError:
            local_link = None
        if local_link is not None:
            result += _generate_for_sp_subsite(local_name, local_link)
    return result


def _generate_for_pvda(name):
    def _generate_for_pvda_subsite(name, link):
        m = re.match(r'^https?s?\:\/\/w?w?w?\.?([^\.]+)', link)
        if m is not None:
            slug = m.group(1)
        else:
            slug = None
        feed_url = os.path.join(link, 'feed')
        return [
            {
                "id": "pvda_" + slug,
                "location": _normalize_location(name),
                "extractor": "ocd_backend.extractors.feed.FeedExtractor",
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "item": "ocd_backend.items.feed.FeedItem",
                "enrichers": _enrichments_config(),
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False,
                "index_name": "pvda",
                "collection": "PvdA",
                "file_url": feed_url,
                "keep_index_on_update": True
            },
            {
                "extractor": "ocd_backend.extractors.paging.PagedStaticHtmlExtractor",
                "keep_index_on_update": True,
                "enrichers": _enrichments_config(),
                "index_name": "pvda",
                "collection": "PvdA",
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "item_xpath": "//div[contains(@class, \"post\")]",
                "item_link_xpath": "(./div/h3/a/@href)[1]",
                "paging_xpath": "//div[contains(@class, \"navigation\")]/div[@class=\"alignright\"]/a/@href",
                "content_xpath": "//div[contains(@class, \"post\")]//img|//div[contains(@class, \"post\")]//p",
                "title_xpath": "//div[contains(@class, \"post\")]//h2//text()",
                "date_xpath": "//div[contains(@class, \"post\")]//div[@class=\"meta\"]//text()",
                "id": "pvda_archives_" + slug,
                "location": _normalize_location(name),
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "file_url": urljoin(feed_url, "/nieuws/"),
                "item": "ocd_backend.items.html.HTMLPageItem",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False
            }
        ]

    resp = requests.get('https://www.pvda.nl/partij/organisatie/lokale-afdelingen/')
    html = etree.HTML(resp.content)
    party_elems = html.xpath(
        '//select//option')
    result = []
    for party_elem in party_elems:
        local_name = u''.join(party_elem.xpath('.//text()'))
        try:
            local_link = party_elem.xpath('./@value')[0]
        except LookupError:
            local_link = None
        if local_link is not None:
            result += _generate_for_pvda_subsite(local_name, local_link)
    return result


def _generate_for_sgp(name):
    def _generate_for_sgp_subsite(name, link):
        if ".sgp.nl" not in link:
            return []

        m = re.match(r'^https?s?\:\/\/w?w?w?\.?([^\.]+)', link)
        if m is not None:
            slug = m.group(1)
        else:
            slug = None

        if slug is None:
            return []

        feed_url = u"%s/actueel" % (link,)
        try:
            requests.head(feed_url)
        except (
            requests.exceptions.HTTPError,
            requests.exceptions.ConnectionError
        ):
            feed_url = None

        if feed_url is None:
            return []

        return [
            {
                "id": "sgp_" + slug,
                "location": _normalize_location(name.strip()),
                "extractor": "ocd_backend.extractors.staticfile.StaticHtmlExtractor",
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "item": "ocd_backend.items.sgp.SGPItem",
                "enrichers": _enrichments_config(),
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False,
                "index_name": "sgp",
                "collection": "SGP",
                "item_xpath": "//a[contains(@class, \"overlay-link\")]",
                "file_url": feed_url,
                "keep_index_on_update": True
            },
            {
                "extractor": "ocd_backend.extractors.paging.PagedStaticHtmlExtractor",
                "keep_index_on_update": True,
                "enrichers": _enrichments_config(),
                "index_name": "sgp",
                "collection": "SGP",
                "loader": "ocd_backend.loaders.ElasticsearchLoader",
                "item_xpath": "//a[contains(@class, \"overlay-link\")]",
                "item_link_xpath": "(./@href)[1]",
                "paging_xpath": "//ul[contains(@class, \"pagination\")]//a[@aria-label=\"Next\"]/@href",
                "content_xpath": "//div[@class=\"story--detail__content\"]//div[@class=\"text\"]",
                "title_xpath": "//h1//text()",
                "date_xpath": "(//span[@class=\"date\"])[1]//text()",
                "id": "sgp_archives_" + slug,
                "location": _normalize_location(name.strip()),
                "transformer": "ocd_backend.transformers.BaseTransformer",
                "file_url": feed_url,
                "item": "ocd_backend.items.html.HTMLPageItem",
                "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
                "hidden": False
            }
        ]

    resp = requests.get('https://www.sgp.nl/decentraal')
    html = etree.HTML(resp.content)
    party_elems = html.xpath(
        '//div[@class="markers"]//div')
    result = []
    links = {}
    for party_elem in party_elems:
        local_name = u''.join(party_elem.xpath('./h3//text()'))
        try:
            local_link = party_elem.xpath('.//a/@href')[0]
        except LookupError:
            local_link = None
        if (local_link is not None) and (links.get(local_link, None) is None):
            links[local_link] = 1
            result += _generate_for_sgp_subsite(local_name, local_link)
    return result


class SimpleFacebookAPI(object):
    def __init__(self, api_version, app_id, app_secret):
        self.api_version = api_version
        self.app_id = app_id
        self.app_secret = app_secret

    def _fb_get_access_token(self):
        return u"%s|%s" % (self.app_id, self.app_secret,)

    def _fb_search(self, query, next_url=None):
        if next_url is not None:
            graph_url = next_url
        else:
            graph_url = "https://graph.facebook.com/%s/search?q=%s&type=page&fields=id,location,name,username,website&access_token=%s" % (
                self.api_version, query,
                self._fb_get_access_token(),)
        r = requests.get(graph_url)
        r.raise_for_status()
        return r.json()

    def search(self, query):
        do_paging = True
        obj = self._fb_search(query)
        for item in obj['data']:
            yield item
        while do_paging and ('paging' in obj) and ('next' in obj['paging']):
            obj = self._fb_search(query, obj['paging']['next'])
            for item in obj['data']:
                yield item


def _generate_facebook_for_party(
    result, index_name, collection, replacements=[]
):
    slug = result.get('username', result['id'])
    if 'location' in result and 'city' in result['location']:
        location = result['location']['city']
    else:
        rep = {}  # define desired replacements here
        for replacement in replacements:
            rep[replacement] = u''
        # use these three lines to do the replacement
        rep = dict((re.escape(k), v) for k, v in rep.iteritems())
        pattern = re.compile("|".join(rep.keys()))
        location = pattern.sub(
            lambda m: rep[re.escape(m.group(0))], result['name'])
        location = location.strip()
    return {
        "extractor": "ocd_backend.extractors.facebook.FacebookExtractor",
        "keep_index_on_update": True,
        "enrichers": _enrichments_config(),
        "index_name": index_name,
        "collection": collection,
        "loader": "ocd_backend.loaders.ElasticsearchLoader",
        "id": "%s_fb_%s" % (index_name, slug,),
        "transformer": "ocd_backend.transformers.BaseTransformer",
        "facebook": {
          "api_version": os.environ['FACEBOOK_API_VERSION'],
          "app_id": os.environ['FACEBOOK_APP_ID'],
          "app_secret": os.environ['FACEBOOK_APP_SECRET'],
          "graph_url": "%s/feed" % (slug,),
          "paging": False
        },
        "item": "ocd_backend.items.facebook.PageItem",
        "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
        "location": _normalize_location(location),
        "hidden": False
    }


def _generate_fb_for_groenlinks(name):
    api = SimpleFacebookAPI(
        os.environ['FACEBOOK_API_VERSION'], os.environ['FACEBOOK_APP_ID'],
        os.environ['FACEBOOK_APP_SECRET'])
    result = api.search('GroenLinks')
    return [
        _generate_facebook_for_party(
            r, 'groenlinks', 'GroenLinks',
            [
                'GroenLinks', 'Groen Links', 'Groenlinks', 'GROENLINKS',
                '/pe', 'Groen & Sociaal'
            ]
        ) for r in result
        if ('.groenlinks.nl' in r.get('website', '')) and
        r.get('name', '').lower().startswith('groen')
    ]


def _generate_fb_for_vvd(name):
    api = SimpleFacebookAPI(
        os.environ['FACEBOOK_API_VERSION'], os.environ['FACEBOOK_APP_ID'],
        os.environ['FACEBOOK_APP_SECRET'])
    result = api.search('VVD')
    return [
        _generate_facebook_for_party(
            r, 'vvd', 'VVD',
            [
                'VVD', 'vvd', 'netwerk'
            ]
        ) for r in result
        if ('.vvd.nl' in r.get('website', '')) and
        r.get('name', '').lower().startswith('vvd')
    ]


def _generate_fb_for_d66(name):
    api = SimpleFacebookAPI(
        os.environ['FACEBOOK_API_VERSION'], os.environ['FACEBOOK_APP_ID'],
        os.environ['FACEBOOK_APP_SECRET'])
    result = api.search('D66')
    return [
        _generate_facebook_for_party(
            r, 'd66', 'D66',
            [
                'd66', 'D66'
            ]
        ) for r in result
        if ('.d66.nl' in r.get('website', '')) and
        r.get('name', '').lower().startswith('d66')
    ]


def _generate_fb_for_sp(name):
    # TODO: this does not work ...
    api = SimpleFacebookAPI(
        os.environ['FACEBOOK_API_VERSION'], os.environ['FACEBOOK_APP_ID'],
        os.environ['FACEBOOK_APP_SECRET'])
    result = api.search('SP')
    return [
        _generate_facebook_for_party(
            r, 'sp', 'SP',
            [
                'sp', 'SP'
            ]
        ) for r in result
        if ('.sp.nl' in r.get('website', '')) and
        r.get('name', '').lower().startswith('sp')
    ]


def _generate_fb_for_cda(name):
    api = SimpleFacebookAPI(
        os.environ['FACEBOOK_API_VERSION'], os.environ['FACEBOOK_APP_ID'],
        os.environ['FACEBOOK_APP_SECRET'])
    result1 = api.search('CDA POLITICAL_ORGANIZATION')
    result2 = api.search('CDA POLITICAL_PARTY')
    result = [r for r in result1] + [r for r in result2]
    return [
        _generate_facebook_for_party(
            r, 'cda', 'CDA',
            [
                'cda', 'CDA'
            ]
        ) for r in result
        if ('.cda.nl' in r.get('website', '')) and
        r.get('name', '').lower().startswith('cda')
    ]


def _generate_fb_for_cu(name):
    api = SimpleFacebookAPI(
        os.environ['FACEBOOK_API_VERSION'], os.environ['FACEBOOK_APP_ID'],
        os.environ['FACEBOOK_APP_SECRET'])
    result = api.search('ChristenUnie')
    return [
        _generate_facebook_for_party(
            r, 'christenunie', 'ChristenUnie',
            [
                'christenunie', 'ChristenUnie', 'Christenunie', 'SGP'
            ]
        ) for r in result
        if ('.christenunie.nl' in r.get('website', '')) and
        r.get('name', '').lower().startswith('christenunie')
    ]


def _generate_fb_for_sgp(name):
    # TODO: this does not work correctly ...
    api = SimpleFacebookAPI(
        os.environ['FACEBOOK_API_VERSION'], os.environ['FACEBOOK_APP_ID'],
        os.environ['FACEBOOK_APP_SECRET'])
    result1 = api.search('SGP POLITICAL_ORGANIZATION')
    result2 = api.search('SGP POLITICAL_PARTY')
    result = [r for r in result1] + [r for r in result2]
    return [
        _generate_facebook_for_party(
            r, 'sgp', 'SGP',
            [
                'christenunie', 'ChristenUnie', 'Christenunie', 'SGP', 'sgp'
            ]
        ) for r in result
        if ('.sgp.nl' in r.get('website', '')) and
        r.get('name', '').lower().startswith('sgp')
    ]


def _generate_fb_for_pvda(name):
    api = SimpleFacebookAPI(
        os.environ['FACEBOOK_API_VERSION'], os.environ['FACEBOOK_APP_ID'],
        os.environ['FACEBOOK_APP_SECRET'])
    result = api.search('PvdA')
    return [
        _generate_facebook_for_party(
            r, 'pvda', 'PvdA',
            [
                'pvda', 'PvdA', 'Pvda', 'PVDA', 'Afdeling', 'Roze netwerk',
                'Europees Parlement', 'afdeling', ', links in ', 'fractie',
                'Tk-2017 kandidaat op 43'
            ]
        ) for r in result
        if ('.pvda.nl' in r.get('website', '')) and
        r.get('name', '').lower().startswith('pvda')
    ]


def _generate_fb_for_pvdd(name):
    api = SimpleFacebookAPI(
        os.environ['FACEBOOK_API_VERSION'], os.environ['FACEBOOK_APP_ID'],
        os.environ['FACEBOOK_APP_SECRET'])
    result = api.search('"Partij voor de Dieren"')
    return [
        _generate_facebook_for_party(
            r, 'pvdd', 'Partij voor de Dieren',
            [
                'pvdd', 'PvdD', 'Partij voor de Dieren', 'Werkgroep', 'e.o.',
                'en omstreken', '/'
            ]
        ) for r in result
        if ('.partijvoordedieren.nl' in r.get('website', '')) and
        r.get('name', '').lower().startswith('partij')
    ]


@click.group()
@click.version_option()
def cli():
    """Poliflw"""


@cli.group()
def sources():
    """Generate sources for a party"""


@command('party')
@click.argument('name', default='')
def generate_sources_local_party(name):
    """
    This generate the sources for a party

    param: name: The name of the party
    """

    LOCATIONS = _get_normalized_locations()

    method_name = '_generate_for_%s' % (name,)
    possibles = globals().copy()
    possibles.update(locals())
    method = possibles.get(method_name)

    sources = (
        method(name)
    )

    print json.dumps(sources, indent=4)


@command('facebook')
@click.argument('name', default='')
def generate_facebook_local_party(name):
    """
    This generate the facebook sources for a party

    param: name: The name of the party
    """

    LOCATIONS = _get_normalized_locations()

    method_name = '_generate_fb_for_%s' % (name,)
    possibles = globals().copy()
    possibles.update(locals())
    method = possibles.get(method_name)

    sources = (
        method(name)
    )

    print json.dumps(sources, indent=4)


@command('locations')
def generate_locations():
    """
    This generates sources for fixing locations
    """
    es = Elasticsearch(
        [{'host': 'elasticsearch', 'port': 9200, 'timeout': 20}])
    available_indices = [
        re.split(r'\s+', x) for x in es.cat.indices().split('\n') if x.strip() != u'']
    selected_indices = [
        x[2] for x in available_indices if not x[2].startswith('.')]
    results = []
    for selected_index in selected_indices:
        if selected_index == 'alt_usage_logs':
            continue
        if selected_index == 'alt_resolver':
            continue
        results.append({
            "extractor": "ocd_backend.extractors.es.ElasticsearchExtractor",
            "keep_index_on_update": True,
            "enrichers": [
            ],
            "index_name": selected_index.replace('alt_', '').split('_')[0],
            "transformer": "ocd_backend.transformers.LocationTransformer",
            "loader": "ocd_backend.loaders.ElasticsearchUpsertLoader",
            "item": "ocd_backend.items.BaseItem",
            "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
            "id": "loc_%s" % (selected_index,),
            "hidden": False,
            "doc_type": "item"
          })
    print json.dumps(results, indent=4)


@command('enrichments')
def generate_enrichments():
    """
    This generates sources for enrichments
    """
    es = Elasticsearch(
        [{'host': 'elasticsearch', 'port': 9200, 'timeout': 20}])
    available_indices = [
        re.split(r'\s+', x) for x in es.cat.indices().split('\n') if x.strip() != u'']
    selected_indices = [
        x[2] for x in available_indices if not x[2].startswith('.')]
    results = []
    for selected_index in selected_indices:
        if selected_index == 'alt_usage_logs':
            continue
        if selected_index == 'alt_resolver':
            continue
        results.append({
            "extractor": "ocd_backend.extractors.es.ElasticsearchExtractor",
            "keep_index_on_update": True,
            "enrichers": [
              [
                "ocd_backend.enrichers.NEREnricher",
                {}
              ]
            ],
            "index_name": selected_index.replace('alt_', '').split('_')[0],
            "transformer": "ocd_backend.transformers.NoneTransformer",
            "loader": "ocd_backend.loaders.ElasticsearchUpsertLoader",
            "item": "ocd_backend.items.BaseItem",
            "cleanup": "ocd_backend.tasks.CleanupElasticsearch",
            "id": "enrich_%s" % (selected_index,),
            "hidden": False,
            "doc_type": "item"
          })
    print json.dumps(results, indent=4)


sources.add_command(generate_sources_local_party)
sources.add_command(generate_facebook_local_party)
sources.add_command(generate_locations)
sources.add_command(generate_enrichments)

if __name__ == '__main__':
    cli()
