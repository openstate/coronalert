#!/bin/sh
curl -s 'http://frontend:5000/v0/search' -d '{"size": 0,"filters":{"type":{"terms":["Note"]}}}'
