from datetime import datetime
import sys
import re
from urlparse import urljoin

import iso8601

from lxml import etree

from jparser import PageModel

from ocd_backend.extractors import HttpRequestMixin
from ocd_backend.items import BaseItem
from ocd_backend.utils.misc import html_cleanup, html_cleanup_with_structure
from ocd_backend.utils.voc import VocabularyMixin

from selenium import webdriver
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.common.exceptions import WebDriverException


class FeedItem(BaseItem, VocabularyMixin):
    def get_original_object_id(self):
        return unicode(self.original_item['link'])

    def get_original_object_urls(self):
        return {
            'html': self.original_item['link']
        }

    def get_rights(self):
        return unicode(self.original_item.get('rights', 'Undefined'))

    def get_collection(self):
        return unicode(self.source_definition.get('collection', 'Unknown'))

    def get_combined_index_data(self):
        combined_index_data = {
            'hidden': self.source_definition['hidden'],
            'source': unicode(
                self.source_definition.get('source', 'Partij nieuws')),
            'type': unicode(self.source_definition.get('type', 'Partij')),
            'parties': [unicode(self.source_definition['collection'])]
        }

        # TODO: provide easier way for default mapping
        mappings = {
            'summary': 'description'
        }
        mappings.update(self.source_definition.get('mappings', {}))

        for fld in ['title', 'summary']:
            if self.original_item.get(fld, None) is not None:
                mapping_fld = mappings.get(fld, fld)
                combined_index_data[mapping_fld] = unicode(self.original_item[fld])

        # try to get the full content, if available
        try:
            combined_index_data['description'] = unicode(self.original_item[
                'content'][0]['value'])
        except LookupError:
                pass

        try:
            combined_index_data['date'] = iso8601.parse_date(
                self.original_item['published_parsed'])
        except LookupError:
            pass

        if self.source_definition.get('location', None) is not None:
            combined_index_data['location'] = unicode(self.source_definition[
                'location'].decode('utf-8'))
        combined_index_data['date_granularity'] = 12

        return combined_index_data

    def get_index_data(self):
        return {}

    def get_all_text(self):
        text_items = []

        return u' '.join(text_items)


class FeedFullTextItem(FeedItem, HttpRequestMixin):
    def get_combined_index_data(self):
        combined_index_data = super(
            FeedFullTextItem, self).get_combined_index_data()

        r = self.http_session.get(self.original_item['link'])
        print >>sys.stderr, "Got %s with status code : %s" % (
            self.original_item['link'], r.status_code)

        # only continue if we got the page
        if r.status_code < 200 or r.status_code >= 300:
            return combined_index_data

        try:
            html = etree.HTML(r.content)
        except etree.ElementTree.ParseError as e:
            return combined_index_data

        output = u''
        for elem in html.xpath(self.source_definition['content_xpath']):
            output += unicode(etree.tostring(elem))

        if output.strip() != u'':
            combined_index_data['description'] = output

        return combined_index_data


class FeedContentFromPageItem(FeedItem, HttpRequestMixin):
    def get_combined_index_data(self):
        combined_index_data = super(
            FeedContentFromPageItem, self).get_combined_index_data()

        if re.match(r'^https?\:\/\/', self.original_item['link']):
            page_link = self.original_item['link']
        else:
            page_link = urljoin(self.source_definition['file_url'], self.original_item['link'])
        r = self.http_session.get(page_link, timeout=5)
        print >>sys.stderr, "Got %s with status code : %s" % (
            self.original_item['link'], r.status_code)

        # only continue if we got the page
        if r.status_code < 200 or r.status_code >= 300:
            return combined_index_data

        try:
            full_content = r.content
        except etree.ElementTree.ParseError as e:
            return combined_index_data

        # TODO: Fix byte 0xff problem: 'utf8' codec can't decode byte 0xff in position <x>: invalid start byte
        # TODO: Fix Unicode strings with encoding declaration are not supported. Please use bytes input or XML fragments without declaration.
        # TODO: remove things like: Share on Facebook Share Share on Twitter Tweet Share on Pinterest Share Share on LinkedIn Share Send email Mail Print Print
        try:
            cleaned = PageModel(full_content.decode(r.encoding)).extract()
        except Exception as e:
            print >>sys.stderr, e
            cleaned = {}

        output = u''
        for elem in cleaned.get('content', []):
            if elem['type'] == 'text':
                # if it starts with these words it's probably garbage
                if re.match('^\s*(Share|Deel|Delen|Send|Print)\s*', elem['data']) is None:
                    output += '<p>%s</p>' % (elem['data'],)
            if elem['type'] == 'image':
                output += '<img src="%s" />' % (elem['data']['src'],)

        if output.strip() != u'':
            combined_index_data['description'] = unicode(output)

        return combined_index_data
