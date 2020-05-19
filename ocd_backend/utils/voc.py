from urlparse import urljoin
from hashlib import sha1

from ocd_backend import settings


class VocabularyMixin(object):
    """
    Interface for getting identifiers from vocabulary
    """

    def get_identifier(self, entity, identifier, additional={}):
        ns = settings.AS2_NAMESPACE
        identifier_key = identifier
        if len(additional.keys()) > 0:
            identifier_additional = u'&'.join(['%s=%s' % (k, additional[k],) for k in additional.keys()])
            identifier_key += u'|' + identifier_additional
        identifier_hash = sha1(identifier_key.decode('utf8')).hexdigest()
        return urljoin(urljoin(ns, entity + '/'), identifier_hash)

    def get_organization(self, identifier, location=u'NL', additional={}):
        additional['location'] = location
        return {
            "@type": u"Organization",
            "name": identifier,
            "@id": self.get_identifier(
                'Organization', identifier, additional=additional)
        }

    def get_person(self, identifier, location=u'NL', additional={}):
        additional['location'] = location
        return {
            "@type": u"Person",
            "name": identifier,
            "@id": self.get_identifier(
                'Person', identifier, additional=additional)
        }

    def get_topic(self, identifier, location=u'NL', additional={}):
        additional['location'] = location
        ns_identifier = self.get_identifier(
            'Link', identifier, additional=additional)
        return {
            "@type": u"Link",
            "name": identifier,
            "@id": ns_identifier,
            "href": ns_identifier
        }

    def get_sentiment(self, sentiments, additional={}):
        output = []
        for s, v in sentiments.iteritems():
            ns_identifier = self.get_identifier(
                'Link', s, {'classification': 'sentiment'})
            output.append({
                "@type": u"Link",
                "name": v['description'],
                "@id": ns_identifier,
                "href": ns_identifier,
                "nif:taConfidence": v['score'],
                "rel": s
            })
        return output

    def get_interestingness(self, identifier, additional={}):
        ns_identifier = self.get_identifier(
            'Link', identifier, additional={
                'classification': 'interestingness'})
        return {
            "@type": u"Link",
            "name": identifier,
            "@id": ns_identifier,
            "href": ns_identifier,
            'rel': 'interestingness'
        }

    def get_percolation(self, identifier, additional={}):
        ns_identifier = self.get_identifier(
            'Link', identifier, additional={
                'classification': 'percolation'})
        return {
            "@type": u"Link",
            "name": identifier.split('/')[-1].capitalize(),
            "@id": ns_identifier,
            "href": ns_identifier,
            'rel': 'percolation'
        }

    def get_type(self, identifier, additional={}):
        ns_identifier = self.get_identifier(
            'Link', identifier, additional={
                'classification': 'type'})
        return {
            "@type": u"Link",
            "name": identifier,
            "@id": ns_identifier,
            "href": ns_identifier,
            'rel': 'type'
        }
