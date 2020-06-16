#!/bin/sh
curl -s 'https://api.coronalert.nl/v0/search' -d '{"size": 1,"filters":{"type":{"terms":["Note"]}}}'
