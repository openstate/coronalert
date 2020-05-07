#!/usr/bin/env python
import csv
import codecs
import os
import sys

from redis import StrictRedis


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


def _get_normalized_locations():
    loc_path = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        '../ocd_backend/data/cbs-name2018-mapping.csv')
    result = {}
    with open(loc_path) as locations_in:
        locations = UnicodeReader(locations_in)
        headers = locations.next()
        for location in locations:
            record = dict(zip(headers, location))
            result[record[u'Key_poliflw']] = record[u'Alt_map']
    return result


def main():
    LOCATIONS = _get_normalized_locations()
    client = StrictRedis(host='redis')
    client.hmset('alt_locs_norm', LOCATIONS)

if __name__ == '__main__':
    sys.exit(main())
