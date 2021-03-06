#!/usr/bin/env python

import sys
import os
import re
from pprint import pprint
import glob
import pickle

import requests

from sklearn import svm

sys.path.insert(0, '.')

from ocd_ml.interestingness import featurize, class_labels


def get_data_from_permalink(permalink):
    poliflw_id = permalink.strip().split('/')[-1]
    try:
        result = requests.get(
            'https://api.poliflw.nl/v0/combined_index/%s' % (poliflw_id,),
            verify=False).json()
    except Exception as e:
        print e, e.__class__.__name__
        result = {}
    return result


def load_data_from_file(file_path):
    ids = []
    with open(file_path) as in_file:
        ids = [get_data_from_permalink(x) for x in in_file.readlines()]
    return ids


def main(argv):
    class_files = glob.glob('ocd_backend/data/interestingness/*.txt')
    classes = {}
    train_data = []
    train_labels = []
    for class_path in class_files:
        class_name = class_path.split('/')[-1].replace('.txt', '')
        ids = load_data_from_file(class_path)
        classes[class_name] = ids
        train_data += [featurize(x) for x in ids]
        train_labels += [class_labels.index(class_name) for x in ids]
    pprint(train_data)
    clf = svm.SVC(gamma='scale')
    clf.fit(train_data, train_labels)
    pickle.dump(clf, open('interestingness.model', 'wb'))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
