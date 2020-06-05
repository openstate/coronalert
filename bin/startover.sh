#!/bin/bash
source /opt/bin/activate
cd /opt/alt

./bin/delete_indexes.sh
./manage.py elasticsearch put_template
./manage.py elasticsearch create_indexes es_mappings/
./manage.py extract start gemeente_amsterdam_1
sleep 30
./manage.py elasticsearch create_queries data/elasticsearch/queries/
./manage.py extract start gemeente_amsterdam_1
