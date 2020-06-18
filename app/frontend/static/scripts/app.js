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

CurrentApp.generate_full_eq_query = function(queries) {
  var result = {};
  if (queries.length >1) {
    result = {
      "query": {
        "bool": {
          "should": queries.map(function (q) { return q['query']; }),
          "minimum_should_match": 1
        }
      }
    };

  } else {
    result = queries[0];
  }
  result['size'] = 10;
  return result;
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
    // TODO: figureout how to do automatic selection
    var pidx = 0;
    var vidx = 1;
    if (!selected_place.object.tag[0].nameMap.nl.startsWith($('#search-results-types-province').attr('title')+' ')) {
      pidx = 1;
      vidx = 0;
    }

    $('#form-subscribe-show-municipality').text(selected_place.object.nameMap.nl);
    $('#form-subscribe-show-province').text(selected_place.object.tag[pidx].nameMap.nl);
    if (selected_place.object.tag.length > 1) {
      $('#form-subscribe-show-safety-region').text(selected_place.object.tag[vidx].nameMap.nl);
    }

    $('#search-results-types-municipality').attr('data-location', selected_place.object.nameMap.nl);

    $('#search-results-types-province').attr('data-location', selected_place.object.tag[pidx].nameMap.nl);
    if (selected_place.object.tag.length > 1) {
      $('#search-results-types-safety-region').attr('data-location', selected_place.object.tag[vidx].nameMap.nl);
    }

    $('#search-results-types-municipality').attr('href', selected_place.object['@id']);
    $('#search-results-types-province').attr('href', selected_place.object.tag[pidx]['@id']);
    if (selected_place.object.tag.length > 1) {
      $('#search-results-types-safety-region').attr('href', selected_place.object.tag[vidx]['@id']);
    }

    $('#formSubscribeIncludeProvince').attr('value', selected_place.object.tag[pidx]['@id']);
    $('#formSubscribeIncludeSafetyRegion').attr('value', selected_place.object.tag[vidx]['@id']);

    var fields_to_names = {
      'municipality': selected_place.object.nameMap.nl,
      'province': selected_place.object.tag[pidx].nameMap.nl,
      'safety-region': selected_place.object.tag[vidx].nameMap.nl
    }

    for (var f in fields_to_names) {
      var parse = fields_to_names[f].split(' ');
      var result = CurrentApp.actor_types_keys[0];
      for (var t in CurrentApp.actor_types_keys) {
        if (parse[0] == CurrentApp.actor_types_keys[t]) {
          result = CurrentApp.actor_types_keys[t];
        }
      }
      $('#form-subscribe-' + f + '-actor-type').attr("value", CurrentApp.actor_types[result]).attr('title', result);
      $('#form-subscribe-' + f + '-name').attr("value", fields_to_names[f]);
    }

    $('#search-results-types-all').click();
  });

  // search resuts types functionality
  $('#search-results-types li a').on('click', function (e) {
    $('#content-search-results').html('<div class="spinner-border" role="status"><span class="sr-only">Loading...</span></div>');
    console.log('clicked!');
    $('#search-results-types li a').removeClass('active');
    $(this).addClass('active');
    e.preventDefault();
    var actor_types = $(this).attr('data-actor-types').split(',');
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
    var full_query = CurrentApp.generate_full_eq_query(clauses);
    console.log('full query:');
    console.dir(full_query);
    $.ajax({
      type: 'POST',
      url: '/query',
      data: JSON.stringify(full_query), // or JSON.stringify ({name: 'jonas'}),
      success: function(data) { console.log('got data!'); $('#content-search-results').html(data); },
      contentType: "application/json",
      dataType: 'html'
    });
    return false;
  });

  $('#form-subscribe-municipality').change();
};

$(function() {
  console.log('jQuery init');
  CurrentApp.init();
});
