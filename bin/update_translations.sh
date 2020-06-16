#!/bin/sh
FQPATH=`readlink -f $0`
BINDIR=`dirname $FQPATH`
docker exec -it alt_app_1 bash -c 'cd frontend && ./update-translations.sh'
cd $BINDIR/../app/frontend/translations
find . -name '*.po' -exec sudo chown "$USER.$USER" \{\} \;
cd -
