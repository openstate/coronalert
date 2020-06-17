
class BinoasElasticsearchRequestFactory(object):
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def get_search_query(self):
        query = self.kwargs.get('query', None)
        if query is None:
            return

        rl = self.kwargs['rl']
        search_fields = ['nameMap.%s' % (rl,), 'contentMap.%s' % (rl,)]

        search_query = {
            "nested": {
                "path": "data",
                "query": {
                    "bool": {
                        "must": [
                            {"terms":{"data.key":search_fields}},
                            {"simple_query_string":{
                                "fields": ["data.value"],
                                "query": query,
                                "default_operator": "and"
                            }}
                        ]
                    }
                }
            }
        }
        return search_query

    def get_search_percolation_filters(self):
        percolation_ids = self.kwargs.get('percolations', [])
        if len(percolation_ids) < 1:
            return

        return {
            "nested": {
                "path": "data",
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"data.key": "tag"}},
                            {"terms": {"data.value.raw": percolation_ids}}
                        ]
                    }
                }
            }
        }

    def get_tag_location_pair(self, tl):
        return {
            "bool": {
                "must":[
                    {
                      "nested": {
                          "path": "data",
                          "query": {
                              "bool": {
                                   "must": [
                                       {"term": {"data.key": "tag"}},
                                       {"term": {"data.value.raw": tl['tag']}}
                                   ]
                               }
                          }
                      }
                    },
                    {
                      "nested": {
                          "path": "data",
                          "query": {
                              "bool": {
                                   "must": [
                                       {"term": {"data.key": "location"}},
                                       {"term": {"data.value.raw": tl['location']}}
                                   ]
                               }
                          }
                      }
                    }
                ]
            }
        }

    def build(self):
        default_filters = [
            self.get_search_query(), self.get_search_percolation_filters()]

        result = {
            "query": {
                "bool": {
                    "must": [f for f in default_filters if f is not None]
                }
            }
        }

        shoulds = [self.get_tag_location_pair(tl) for tl in self.kwargs.get('tag_location_pairs', [])]

        if len(shoulds) > 0:
            result['query']['bool']['should'] = shoulds
            result['query']['bool']['minimum_should_match'] = 1

        if (len(result['query']['bool']['must']) + len(result['query']['bool'].get('should', []))) < 1:
            result = {
                'query': self.get_search_query() or {'match_all':{}}
            }

        return result
