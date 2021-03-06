// Import external dependencies
import 'jquery';
import 'bootstrap';
import 'ekko-lightbox/dist/ekko-lightbox.min.js';
import 'bootstrap-table';
import 'bootstrap-table/dist/locale/bootstrap-table-nl-NL.min.js';
import 'bootstrap-table/dist/extensions/sticky-header/bootstrap-table-sticky-header.min.js';
import 'bootstrap-table/dist/extensions/mobile/bootstrap-table-mobile.min.js';
import naturalSort from 'javascript-natural-sort';

var CurrentApp = window.CurrentApp || {};
CurrentApp.countries = {
    raw: undefined,
    id2name: {},
    name2id: {}
};


CurrentApp.map_countries = function() {
  CurrentApp.countries.raw.forEach(function (c) {
    CurrentApp.countries.id2name[c['@id']] = c['name'];
    CurrentApp.countries.name2id[c['name']] = c['@id'];
  });
};

CurrentApp.get_countries = function() {
  $.get('/countries.json', function (data) {
    console.log('Got countries data!');
    CurrentApp.countries.raw = data;
    CurrentApp.map_countries();
  });
};

CurrentApp.generate_es_query = function(clause) {
  return {
    "query": {
      "bool": {
        "filter": [
          {"terms": {"_type": ["Note"]}},
          {"terms": {"item.tag.raw": clause.percolations}},
          {"terms":{"item.location.raw": [
            clause.location
          ]}},
          {"terms":{"item.attributedTo.raw": [
            clause.attributedTo
          ]}}
        ]
      }
    }
  }
};

CurrentApp.generate_full_eq_query = function(queries, offset) {
  var result = {};
  if (queries.length >1) {
    result = {
      "query": {
        "bool": {
          "should": queries.map(function (q) { return q['query']; }),
          "minimum_should_match": 1
        }
      },
      "sort": [
        { 'item.created': {
          'order': 'desc'
        }}
      ]
    };

  } else {
    result = queries[0];
  }
  result['size'] = 10;
  if (typeof(offset) !== 'undefined') {
    result['from'] = offset;
  }
  return result;
};

CurrentApp.live_paging = function() {
  // TODO: fix this :-)
  console.log('next page link:');
  console.log($('a[rel="next"]'));
  $('a[rel="next"]').on('click', function(e) {
    e.preventDefault();
    console.log('item load more pages link clicked!');

    if (CurrentApp.mode != "search") {
      CurrentApp.perform_search($(this).attr('data-page'));
    } else {
      $('#content-search-results').append('<div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div>');
      $.ajax({
        type: 'GET',
        url: $(this).attr('href') + '&layout=bare',
        success: function(data) {
          console.log('got search mode result data!');
          $('.spinner-border').remove();
          $('#content-search-results').append(data);

          CurrentApp.live_paging();
        },
        contentType: "application/json",
        dataType: 'html'
      });

    }

    $(this).parent().remove();


    return false;
  });
};

CurrentApp.perform_search = function(page) {
  $('#content-search-results').append('<div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div>');
  // page starts at 1
  var offset = 0;
  if (typeof(page) !== 'undefined') {
    offset = (page - 1) * 10;
  }
  /* START REFACTOR */
  var actor_types = $('#search-results-types .active').attr('data-actor-types').split(',');
  console.log('should do the following actor types:');
  console.log(actor_types);
  var clauses = [];
  var percolations = [];
  for (var p in CurrentApp.percolations) {
    percolations.push(CurrentApp.percolations[p]);
  }
  actor_types.forEach(function (a) {
    clauses.push(CurrentApp.generate_es_query({
      'location': $('#search-results-types-'+a).attr('href'),
      'attributedTo': CurrentApp.actor_types[$('#search-results-types-'+a).attr('title')],
      'percolations': percolations
    }));
  });
  console.log('clauses:');
  // console.dir(clauses);
  var full_query = CurrentApp.generate_full_eq_query(clauses, offset);
  var url_for_query = '/query';
  if (offset > 0) {
    url_for_query += '?page=' + page;
  }
  console.log('full query before search query:');
  console.dir(full_query);
  var searchQuery = $('#formSubscribeQuery').val();
  if ((typeof(searchQuery) !== 'undefined') && (searchQuery.trim() != '')) {
    var cs = "?";
    if (url_for_query.indexOf(cs) >= 0) {
      cs = "&";
    }
    url_for_query = url_for_query + cs + 'query=' + encodeURI(searchQuery.trim());
    full_query.query.bool.must = [
      {'simple_query_string': {
          'query': searchQuery.trim(),
          'default_operator': 'AND',
          'fields': ['name', 'content', '*.nl', '*.en', '*.fr', '*.de']
      }}
    ]
  }
  console.log('full query after search query:');
  console.dir(full_query);
  $.ajax({
    type: 'POST',
    url: url_for_query,
    data: JSON.stringify(full_query), // or JSON.stringify ({name: 'jonas'}),
    success: function(data) {
      if (offset == 0) {
        $('#content-search-results').empty();
      }
      console.log('got search result data!');
      $('.spinner-border').remove();
      $('#content-search-results').append(data);

      CurrentApp.live_paging();

      $('.toast').toast('show');
    },
    contentType: "application/json",
    dataType: 'html'
  });
  /* END REFACTOR */
};

CurrentApp.init = function() {
  console.log('CurrentApp inited correctly!');
  // console.dir(CurrentApp.places);

  CurrentApp.get_countries();

  // country checkbox selection thingie
  $('input[type="checkbox"]').on('change', function() {
    var state = $('#' + $(this).attr('id')).is(':checked');
    if (state) {
      $('label[for="'+ $(this).attr('id')+'"] i').removeClass('fa-square-o').addClass('fa-check-square-o');
    } else {
      $('label[for="'+ $(this).attr('id')+'"] i').removeClass('fa-check-square-o').addClass('fa-square-o');
    }
  });

  $('.form-countries .form-check').keydown(function (e) {
    console.log('countrie checkbox thingie keydown!');
    // console.dir(e);
    if (e.originalEvent.key == "x") {
      console.log('x pressed!');
      $(e.target.firstElementChild).click();
    }
  });

  // countries for the collect modal
  $('#modal-subscribe').on('show.bs.modal', function (e) {
    // do something...
    console.log('show subscribe modal!');

    $('#modal-subscribe-location-info ul li').each(function (idx, item) {
      console.log('setting country name for ' + item);
      $(item).text(CurrentApp.countries.id2name[$(item).attr('data-location')]);
    });
  });

  $('#formSubscribeQuery').on('blur', function(e) {
    console.log('query blur: should update results below now!');
    if (CurrentApp.queryModified) {
      $('#form-subscribe-municipality').change();
    }
    CurrentApp.queryModified = false;
  }).on('focus', function (e) {
    CurrentApp.queryModified = false;
  }).on('keyup', function (e) {
    CurrentApp.queryModified = true;
    clearTimeout(CurrentApp.queryTimer);
    CurrentApp.queryTimer = setTimeout(function() {
      console.log('query keyup delay: should update results below now for ' + $('#formSubscribeQuery').val());
      if (CurrentApp.queryModified) {
        $('#form-subscribe-municipality').change();
      }
      CurrentApp.queryModified = false;
    }, CurrentApp.queryDelay); // Will do the ajax stuff after 1000 ms, or 1 s
  });


  $('.form-subscribe-select-location').on('change', function (e) {
    console.log('search mode: ' + CurrentApp.mode);
    var selected_objects = {
      'municipality': undefined,
      'province': undefined,
      'safety-region': undefined
    };
    var selected_param = $(this).attr('name');
    var selected_place_id = $(this).val();
    console.log('you selected another ' + selected_param + ': ' + selected_place_id);
    // TODO: rework this
    var selected_place = CurrentApp.places.filter(function (i) {
      return i['object']['@id'] == selected_place_id;
    })[0];
    console.log(selected_place);

    if (CurrentApp.mode == "basic") {
      var sid = $('#form-subscribe-municipality').val();
      console.log('basic munucipality selected: ' + sid);
      selected_objects['municipality'] = CurrentApp.places.filter(function (i) {
        return i['object']['@id'] == sid;
      })[0];
      for (var t in selected_objects['municipality'].object.tag) {
        var ct = selected_objects['municipality'].object.tag[t];
        if (ct.nameMap.nl.startsWith($('#search-results-types-province').attr('title')+' ')) {
          selected_objects['province'] = ct;
        } else {
          selected_objects['safety-region'] = ct;
        }
      }
    } else {
      for (var s in selected_objects) {
        var sid = $('#form-subscribe-'+s).val();
        selected_objects[s] = CurrentApp.places.filter(function (i) {
          return i['object']['@id'] == sid;
        })[0];
      }
    }
    console.log('selected objects:');
    console.dir(selected_objects);

    for(var s in selected_objects) {
      var current_selected_object = selected_objects[s];
      if (typeof(selected_objects[s]) !== 'undefined') {
        if (typeof(current_selected_object.object) !== 'undefined') {
          current_selected_object = current_selected_object.object;
        }
        $('#form-subscribe-show-' + s).text(current_selected_object.nameMap.nl);

        var name_parts = current_selected_object.nameMap.nl.split(' ');
        var actor_type_index = CurrentApp.actor_types_keys.indexOf(name_parts[0]);
        if (actor_type_index < 0) {
          actor_type_index = 0;
        }
        var actor_type_label = CurrentApp.actor_types_keys[actor_type_index];
        if (CurrentApp.mode == 'advanced') {
          actor_type_label = current_selected_object.nameMap.nl;
        }
        $('#search-results-types-'+s).attr(
          'data-location', current_selected_object.nameMap.nl
        ).text(
          actor_type_label
        );
        $('#search-results-types-'+s).attr('href', current_selected_object['@id']);
        $('#form-subscribe-' + s + '-actor-type').attr("value", CurrentApp.actor_types[actor_type_label]).attr('title', actor_type_label);
        $('#form-subscribe-' + s + '-name').attr("value", current_selected_object.nameMap.nl);
      } else {
        $('#form-subscribe-show-' + s).text('');
        $('#search-results-types-'+s).attr('data-location', '');
        $('#search-results-types-'+s).attr('href', '');
        $('#form-subscribe-' + s + '-actor-type').attr("value", "").attr('title', "");
        $('#form-subscribe-' + s + '-name').attr("value", "");
      }

    }

    if (typeof(selected_objects['province']) !== 'undefined') {
      $('#formSubscribeIncludeProvince').attr('value', selected_objects['province']['@id']);
    } else {
      $('#formSubscribeIncludeProvince').attr('value', '');
    }

    if (typeof(selected_objects['safety-region']) !== 'undefined') {
      $('#formSubscribeIncludeSafetyRegion').attr('value', selected_objects['safety-region']['@id']);
    } else {
      $('#formSubscribeIncludeSafetyRegion').attr('value', '');
    }

    $('#search-results-types-all').click();
  });

  // search resuts types functionality
  $('#search-results-types li a').on('click', function (e) {
    $('#content-search-results').empty(); //html('<div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div>');
    console.log('clicked!');
    $('#search-results-types li a').removeClass('active');
    $(this).addClass('active');
    e.preventDefault();

    CurrentApp.perform_search(1);

    return false;
  });


  CurrentApp.live_paging();
  $('#form-subscribe-municipality').change();

  $('.toast').toast({autohide: false});
  console.log('toasted!');
};

$(function() {
  console.log('jQuery init');
  CurrentApp.init();
});
