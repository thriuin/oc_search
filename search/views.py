import csv
from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect, FileResponse
from django.views.generic import View
from django.shortcuts import render, redirect
from .forms import FieldForm
import hashlib
import importlib
import os
import pkgutil
from .query import calc_pagination_range, calc_starting_row, create_solr_query, create_solr_mlt_query
from search.models import Search, Field, Code
import search.plugins
from SolrClient import SolrClient, SolrResponse
from SolrClient.exceptions import ConnectionError, SolrError
from time import time


def iter_namespace(ns_pkg):
    # Specifying the second argument (prefix) to iter_modules makes the
    # returned name an absolute name instead of a relative one. This allows
    # import_module to work without having to do additional modification to
    # the name.
    return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")


def get_error_context(search_type: str, lang: str, error_msg=""):
    return {
        "language": lang,
        "LANGUAGE_CODE": lang,
        "cdts_version": settings.CDTS_VERSION,
        "search_type": search_type,
        "search_description": "",
        "search_title": search_type,
        "dcterms_lang": 'fra' if lang == 'fr' else 'eng',
        "ADOBE_ANALYTICS_URL": settings.ADOBE_ANALYTICS_URL,
        "GOOGLE_ANALYTICS_GTM_ID": settings.GOOGLE_ANALYTICS_GTM_ID,
        "GOOGLE_ANALYTICS_PROPERTY_ID": settings.GOOGLE_ANALYTICS_PROPERTY_ID,
        "header_js_snippet": "",
        "header_css_snippet": "",
        "breadcrumb_snippet": "search_snippets/default_breadcrumb.html",
        "footer_snippet": "search_snippets/default_footer.html",
        "body_js_snippet": "",
        "info_message_snippet": "search_snippets/default_info_message.html",
        "about_message_snippet": "search_snippets/default_about_message.html",
        "DEBUG": settings.DEBUG,
        "exception_message": error_msg
    }


class FieldFormView(View):
    def __init__(self):
        super().__init__()

    def get(self, request, *args, **kwargs):
        form = FieldForm()
        return render(request, 'field_form.html', {'form': form})

    def post(self, request, *args, **kwargs):
        # create a form instance and populate it with data from the request:
        form = FieldForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            print('Valid')
        return render(request, 'guide_form.html', {'form': form})


class SearchView(View):

    searches = {}
    fields = {}
    facets_en = {}
    facets_fr = {}
    codes_en = {}
    codes_fr = {}
    display_fields_en = {}
    display_fields_fr = {}
    display_fields_names_en = {}
    display_fields_names_fr = {}

    discovered_plugins = {}

    def __init__(self):
        super().__init__()

        # Original function copied from https://packaging.python.org/guides/creating-and-discovering-plugins/
        self.discovered_plugins = {
            name: importlib.import_module(name)
            for finder, name, ispkg
            in iter_namespace(search.plugins)
        }

        # Load Search and Field configuration
        search_queryset = Search.objects.all()
        for s in search_queryset:
            self.searches[s.search_id] = s
        for sid in self.searches.keys():
            sfields = {}
            facet_list_en = []
            facet_list_fr = []
            display_list_en = []
            display_list_fr = []
            field_queryset = Field.objects.filter(search_id_id=sid)
            for f in field_queryset:
                sfields[f.field_id] = f
            field_queryset = Field.objects.filter(search_id_id=sid).filter(is_search_facet=True).order_by('solr_facet_display_order')
            for f in field_queryset:
                if f.solr_field_lang == 'en':
                    facet_list_en.append(f.field_id)
                elif f.solr_field_lang == 'fr':
                    facet_list_fr.append(f.field_id)
                elif f.solr_field_lang == 'bi':
                    facet_list_en.append(f.field_id)
                    facet_list_fr.append(f.field_id)
            field_queryset = Field.objects.filter(search_id_id=sid).filter(is_default_display=True)
            for f in field_queryset:
                if f.is_default_display and f.solr_field_lang == 'en':
                    display_list_en.append(f.field_id)
                elif f.is_default_display and f.solr_field_lang == 'fr':
                    display_list_fr.append(f.field_id)
                elif f.is_default_display and f.solr_field_lang == 'bi':
                    display_list_en.append(f.field_id)
                    display_list_fr.append(f.field_id)

            self.fields[sid] = sfields
            self.facets_en[sid] = facet_list_en
            self.facets_fr[sid] = facet_list_fr
            self.display_fields_en[sid] = display_list_en
            self.display_fields_fr[sid] = display_list_fr
            self.display_fields_names_en[sid] = self.get_default_display_fields('en', sid)
            self.display_fields_names_fr[sid] = self.get_default_display_fields('fr', sid)

        # Load Code configuration
        codes_queryset = Code.objects.all()
        for code in codes_queryset:
            if code.field_id.field_id in self.codes_en:
                self.codes_en[code.field_id.field_id][code.code_id] = code.label_en
                self.codes_fr[code.field_id.field_id][code.code_id] = code.label_fr
            else:
                self.codes_en[code.field_id.field_id] = {code.code_id: code.label_en}
                self.codes_fr[code.field_id.field_id] = {code.code_id: code.label_fr}

    def get_default_display_fields(self, lang: str, search_type: str):
        display_field_name = {}
        for f in self.fields[search_type]:
            if self.fields[search_type][f].solr_field_lang in [lang, 'bi']:
                if lang == 'en' and not f[:2] == 'fr':
                    display_field_name[f] = self.fields[search_type][f].label_en
                    continue
                elif lang == 'fr' and not f[:2] == 'en':
                    display_field_name[f] = self.fields[search_type][f].label_fr
                    continue
        return display_field_name

    def default_context(self, request: HttpRequest, search_type: str, lang: str):
        context = {
            "language": lang,
            "cdts_version": settings.CDTS_VERSION,
            "search_type": search_type,
            "search_description": self.searches[search_type].desc_fr if lang == 'fr' else self.searches[
                search_type].desc_fr,
            "search_title": self.searches[search_type].label_fr if lang == 'fr' else self.searches[
                search_type].label_en,
            "dcterms_lang": 'fra' if lang == 'fr' else 'eng',
            "ADOBE_ANALYTICS_URL": settings.ADOBE_ANALYTICS_URL,
            "GOOGLE_ANALYTICS_GTM_ID": settings.GOOGLE_ANALYTICS_GTM_ID,
            "GOOGLE_ANALYTICS_PROPERTY_ID": settings.GOOGLE_ANALYTICS_PROPERTY_ID,
            "url_uses_path": settings.SEARCH_LANG_USE_PATH,
            "url_host_en": settings.SEARCH_EN_HOSTNAME,
            "url_host_fr": settings.SEARCH_FR_HOSTNAME,
            "url_host_path": settings.SEARCH_HOST_PATH,
            "header_js_snippet": self.searches[search_type].header_js_snippet,
            "header_css_snippet": self.searches[search_type].header_css_snippet,
            "breadcrumb_snippet": self.searches[search_type].breadcrumb_snippet,
            "record_breadcrumb_snippet": self.searches[search_type].record_breadcrumb_snippet,
            "footer_snippet": self.searches[search_type].footer_snippet,
            "body_js_snippet": self.searches[search_type].body_js_snippet,
            "info_message_snippet": self.searches[search_type].info_message_snippet,
            "about_message_snippet": self.searches[search_type].about_message_snippet,
            "mlt_enabled": self.searches[search_type].mlt_enabled,
            "query_path": request.META["QUERY_STRING"],
            "path_info": request.META["PATH_INFO"],
        }
        utl_fragments = request.META["PATH_INFO"].split('/')
        utl_fragments = utl_fragments if utl_fragments[-2] == search_type else utl_fragments[:-2]
        if utl_fragments[-1]:
            utl_fragments.append('')

        context['parent_path'] = "/".join(utl_fragments)

        return context

    def get(self, request: HttpRequest, lang='en', search_type=''):
        lang = request.LANGUAGE_CODE
        request.session['prev_search'] = request.build_absolute_uri()
        if search_type in self.searches:
            context = self.default_context(request, search_type, lang)
            context["search_item_snippet"] = self.searches[search_type].search_item_snippet
            context["download_ds_url"] = self.searches[search_type].dataset_download_url_fr if lang == 'fr' else self.searches[search_type].dataset_download_url_en
            context["download_ds_text"] = self.searches[search_type].dataset_download_text_fr if lang == 'fr' else self.searches[search_type].dataset_download_text_en
            context["search_text"] = request.GET.get("search_text", "")
            context["id_fields"] = self.searches[search_type].id_fields.split(',') if self.searches[
                search_type].id_fields else []
            context["export_path"] = "{0}export?{1}".format(request.META["PATH_INFO"], request.META["QUERY_STRING"])
            context['about_msg'] = self.searches[search_type].about_message_fr if lang == 'fr' else self.searches[search_type].about_message_en

            solr = SolrClient(settings.SOLR_SERVER_URL)

            core_name = self.searches[search_type].solr_core_name

            # Get the search result boundaries
            start_row, page = calc_starting_row(request.GET.get('page', 1),
                                                rows_per_page=self.searches[search_type].results_page_size)

            # Compose the Solr query
            facets = self.facets_fr[search_type] if lang == 'fr' else self.facets_en[search_type]
            reversed_facets = []
            for facet in facets:
                if self.fields[search_type][facet].solr_facet_display_reversed:
                    reversed_facets.append(facet)
            context['reversed_facets'] = reversed_facets

            # Determine a default sort  - only used by the query if a valid sort order is not specified. Use the
            # first soft specified in the search model, or use score if nothing is specified

            default_sort_order = 'score desc'
            if request.LANGUAGE_CODE == 'fr':
                if self.searches[search_type].results_sort_order_fr:
                    default_sort_order = self.searches[search_type].results_sort_order_fr.split(',')[0]
            else:
                if self.searches[search_type].results_sort_order_en:
                    default_sort_order = self.searches[search_type].results_sort_order_en.split(',')[0]

            solr_query = create_solr_query(request, self.searches[search_type], self.fields[search_type],
                                           self.codes_fr if lang == 'fr' else self.codes_en,
                                           facets, start_row, self.searches[search_type].results_page_size,
                                           record_id='', export=False, highlighting=True,
                                           default_sort=default_sort_order)

            # Call  plugin pre-solr-query if defined
            search_type_plugin = 'search.plugins.{0}'.format(search_type)
            if search_type_plugin in self.discovered_plugins:
                context, solr_query = self.discovered_plugins[search_type_plugin].pre_search_solr_query(
                    context,
                    solr_query,
                    request,
                    self.searches[search_type], self.fields[search_type],
                    self.codes_fr if lang == 'fr' else self.codes_en,
                    facets,
                    '')

            # Query Solr

            try:
                solr_response = solr.query(core_name, solr_query, highlight=True)

                # Call  plugin post-solr-query if it exists
                if search_type_plugin in self.discovered_plugins:
                    context, solr_response = self.discovered_plugins[search_type_plugin].post_search_solr_query(
                        context,
                        solr_response,
                        solr_query,
                        request,
                        self.searches[search_type], self.fields[search_type],
                        self.codes_fr if lang == 'fr' else self.codes_en,
                        facets,
                        '')

                if len(facets) > 0:
                    # Facet search results
                    context['facets'] = solr_response.get_facets()
                    # Get the selected facets from the search URL
                    selected_facets = {}

                    for request_field in request.GET.keys():
                        if request_field in self.fields[search_type] and request_field in context['facets']:
                            selected_facets[request_field] = request.GET.get(request_field, "").split('|')
                    context['selected_facets'] = selected_facets
                    # Provide human friendly facet labels to the web page and any custom snippets
                    facets_custom_snippets = {}
                    for f in context['facets']:
                        context['facets'][f]['__label__'] = self.fields[search_type][f].label_fr if lang == 'fr' else self.fields[search_type][f].label_en
                        if self.fields[search_type][f].solr_facet_snippet:
                            facets_custom_snippets[f] = self.fields[search_type][f].solr_facet_snippet
                    context['facet_snippets'] = facets_custom_snippets
                else:
                    context['facets'] = []
                    context['selected_facets'] = []
                context['total_hits'] = solr_response.num_found
                context['docs'] = solr_response.get_highlighting()

                # Prepare a dictionary of language appropriate sort options
                sort_options = {}
                sort_labels = self.searches[search_type].results_sort_order_display_fr.split(',') if lang == 'fr' else self.searches[search_type].results_sort_order_display_en.split(',')
                if lang == 'fr':
                    for i, v in enumerate(self.searches[search_type].results_sort_order_fr.split(',')):
                        sort_options[v] = str(sort_labels[i]).strip()
                else:
                    for i, v in enumerate(self.searches[search_type].results_sort_order_en.split(',')):
                        sort_options[v] = str(sort_labels[i]).strip()
                context['sort_options'] = sort_options
                context['sort'] = solr_query['sort']

                # Add code information
                context['codes'] = self.codes_fr if lang == 'fr' else self.codes_en

                # Save display fields
                context['default_display_fields'] = self.display_fields_fr[search_type] if lang == 'fr' else self.display_fields_en[search_type]
                context['display_field_name'] = self.display_fields_names_fr[search_type] if lang == 'fr' else self.display_fields_names_en[search_type]

                # Calculate pagination for the search page
                context['pagination'] = calc_pagination_range(solr_response.num_found, self.searches[search_type].results_page_size, page, 3)
                context['previous_page'] = (1 if page == 1 else page - 1)
                last_page = (context['pagination'][len(context['pagination']) - 1] if len(context['pagination']) > 0 else 1)
                last_page = (1 if last_page < 1 else last_page)
                context['last_page'] = last_page
                next_page = page + 1
                next_page = (last_page if next_page > last_page else next_page)
                context['next_page'] = next_page
                context['currentpage'] = page

                return render(request, self.searches[search_type].page_template, context)
            except (ConnectionError, SolrError) as ce:
                return render(request, 'error.html', get_error_context(search_type, lang, ce.args[0]))

        else:
            return render(request, '404.html', get_error_context(search_type, lang))


class RecordView(SearchView):

    def get(self, request: HttpRequest, lang='en', search_type='', record_id=''):
        lang = request.LANGUAGE_CODE
        if search_type in self.searches:
            context = self.default_context(request, search_type, lang)
            context['record_detail_snippet'] = self.searches[search_type].record_detail_snippet
            context["download_ds_url_en"] = self.searches[search_type].dataset_download_url_fr if lang == 'fr' else self.searches[search_type].dataset_download_url_en
            context["search_text"] = request.GET.get("search_text", "")
            if 'prev_search' in request.session:
                context['back_to_url'] =  request.session['prev_search']
            request.session['prev_record'] = request.build_absolute_uri()
            solr = SolrClient(settings.SOLR_SERVER_URL)

            core_name = self.searches[search_type].solr_core_name

            # Get the search result boundaries
            start_row, page = calc_starting_row(request.GET.get('page', 1), rows_per_page=5)

            # Compose the Solr query
            facets = {}

            solr_query = create_solr_query(request, self.searches[search_type], self.fields[search_type],
                                           self.codes_fr if lang == 'fr' else self.codes_en,
                                           facets, start_row, 5, record_id)

            # Call  plugin pre-solr-query if defined
            search_type_plugin = 'search.plugins.{0}'.format(search_type)
            if search_type_plugin in self.discovered_plugins:
                context, solr_query = self.discovered_plugins[search_type_plugin].pre_record_solr_query(
                    context,
                    solr_query,
                    request,
                    self.searches[search_type], self.fields[search_type],
                    self.codes_fr if lang == 'fr' else self.codes_en,
                    facets,
                    record_id)

            # Query Solr
            solr_response = solr.query(core_name, solr_query)

            # Call  plugin post-solr-query if it exists
            if search_type_plugin in self.discovered_plugins:
                context, solr_response = self.discovered_plugins[search_type_plugin].post_record_solr_query(
                    context,
                    solr_response,
                    solr_query,
                    request,
                    self.searches[search_type], self.fields[search_type],
                    self.codes_fr if lang == 'fr' else self.codes_en,
                    facets,
                    record_id)

            context['facets'] = []
            context['selected_facets'] = []
            context['total_hits'] = solr_response.num_found
            context['docs'] = solr_response.get_highlighting()

            # Add code information
            context['codes'] = self.codes_fr if lang == 'fr' else self.codes_en

            display_fields = []
            display_field_name = {}
            for f in self.fields[search_type]:
                if self.fields[search_type][f].solr_field_lang in [request.LANGUAGE_CODE, 'bi']:
                    if request.LANGUAGE_CODE == 'en' and not f[:2] == 'fr':
                        display_fields.append(f)
                        display_field_name[f] = self.fields[search_type][f].label_en
                        continue
                    elif request.LANGUAGE_CODE == 'fr' and not f[:2] == 'en':
                        display_fields.append(f)
                        display_field_name[f] = self.fields[search_type][f].label_fr
                        continue
                    if self.fields[search_type][f].solr_extra_fields:
                        display_fields.extend(self.fields[search_type][f].solr_extra_fields.split(","))
            context['display_fields'] = display_fields
            context['display_field_name'] = display_field_name

            # Calculate pagination for the search page
            context['pagination'] = calc_pagination_range(solr_response.num_found, 10, page)
            context['previous_page'] = (1 if page == 1 else page - 1)
            last_page = (context['pagination'][len(context['pagination']) - 1] if len(context['pagination']) > 0 else 1)
            last_page = (1 if last_page < 1 else last_page)
            context['last_page'] = last_page
            next_page = page + 1
            next_page = (last_page if next_page > last_page else next_page)
            context['next_page'] = next_page
            context['currentpage'] = page

            return render(request, self.searches[search_type].record_template, context)

        else:

            return render(request, '404.html', get_error_context(search_type, lang))


class ExportView(SearchView):

    def __init__(self):
        super().__init__()
        self.cache_dir = settings.EXPORT_FILE_CACHE_DIR
        if not os.path.exists(self.cache_dir):
            os.mkdir(self.cache_dir)

    def cache_search_results_file(self, cached_filename: str, sr: SolrResponse, rows=100000):

        if len(sr.docs) == 0:
            return False
        if not os.path.exists(cached_filename):
            with open(cached_filename, 'w', newline='', encoding='utf8') as csv_file:
                cache_writer = csv.writer(csv_file, dialect='excel')
                headers = list(sr.docs[0])
                headers[0] = u'\N{BOM}' + headers[0]
                cache_writer.writerow(headers)
                c = 0
                for i in sr.docs:
                    if c > rows:
                        break
                    try:
                        cache_writer.writerow(i.values())
                        c += 1
                    except UnicodeEncodeError:
                        pass
        return True

    def get(self, request: HttpRequest, lang='en', search_type=''):
        lang = request.LANGUAGE_CODE
        if search_type in self.searches:
            # Check to see if a recent cached results exists and return that instead if it exists
            hashed_query = hashlib.sha1(request.GET.urlencode().encode('utf8')).hexdigest()
            cached_filename = os.path.join(self.cache_dir, "{0}_{1}.csv".format(hashed_query, lang))
            if os.path.exists(cached_filename):
                # If the cached file is over 5 minutes old, just delete and continue. In future, will want this to be a asynchronous opertaion
                if time() - os.path.getmtime(cached_filename) > 600:
                    os.remove(cached_filename)
                else:
                    if settings.EXPORT_FILE_CACHE_URL == "":
                        return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
                    else:
                        return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{0}_{1}.csv".format(hashed_query, lang))

            solr = SolrClient(settings.SOLR_SERVER_URL)
            core_name = self.searches[search_type].solr_core_name
            facets = self.facets_fr[search_type] if lang == 'fr' else self.facets_en[search_type]
            solr_query = create_solr_query(request, self.searches[search_type], self.fields[search_type],
                                           self.codes_fr if lang == 'fr' else self.codes_en,
                                           facets, 1, 0, record_id='', export=True)

            # Call  plugin pre-solr-query if defined
            search_type_plugin = 'search.plugins.{0}'.format(search_type)
            if search_type_plugin in self.discovered_plugins:
                solr_query = self.discovered_plugins[search_type_plugin].pre_export_solr_query(
                    solr_query,
                    request,
                    self.searches[search_type], self.fields[search_type],
                    self.codes_fr if lang == 'fr' else self.codes_en,
                    facets)

            solr_response = solr.query(core_name, solr_query, request_handler='export')

            # Call  plugin pre-solr-query if defined
            if search_type_plugin in self.discovered_plugins:
                solr_query = self.discovered_plugins[search_type_plugin].post_export_solr_query(
                    solr_response,
                    solr_query,
                    request,
                    self.searches[search_type], self.fields[search_type],
                    self.codes_fr if lang == 'fr' else self.codes_en,
                    facets)

            if self.cache_search_results_file(cached_filename=cached_filename, sr=solr_response):
                if settings.EXPORT_FILE_CACHE_URL == "":
                    return FileResponse(open(cached_filename, 'rb'), as_attachment=True)
                else:
                    return HttpResponseRedirect(settings.EXPORT_FILE_CACHE_URL + "{0}_{1}.csv".format(hashed_query, lang))
        else:
            return render(request, '404.html', get_error_context(search_type, lang))


class MoreLikeThisView(SearchView):

    def __init__(self):
        super().__init__()

    # @TODO  In the query class, use a shared method for fl and create new mothod fr MLT queries
    # Note, for MLT, use the standard query but specify MLT params id:XXXX mlt=true&mlt.fl=title_en,name_en,purpose_en
    # http://localhost:8983/solr/core_travelq/select?mlt.count=5&mlt.fl=title_en%2Cname_en%2Cpurpose_en%2Cid&mlt=true&q=id%3A%22aafc-aac%2CT-2017-Q1-00003%22
    # http://127.0.0.1:8000/search/en/travelq/similar/aafc-aac,T-2017-Q1-00003

    def get(self, request: HttpRequest, lang='en', search_type='', record_id=''):
        lang = request.LANGUAGE_CODE
        if search_type in self.searches:
            context = self.default_context(request, search_type, lang)
            context["search_item_snippet"] = self.searches[search_type].search_item_snippet
            context["referer"] = request.META["HTTP_REFERER"] if "HTTP_REFERER" in request.META and (request.META["HTTP_REFERER"].startswith("http://" + request.META["HTTP_HOST"]) or request.META[
                    "HTTP_REFERER"].startswith("https://" + request.META["HTTP_HOST"])) else ""
            solr = SolrClient(settings.SOLR_SERVER_URL)

            core_name = self.searches[search_type].solr_core_name

            # Get the search result boundaries
            start_row, page = calc_starting_row(request.GET.get('page', 1), rows_per_page=self.searches[search_type].mlt_items)
            # Compose the Solr query
            solr_query = create_solr_mlt_query(request, self.searches[search_type], self.fields[search_type], start_row, record_id)

            # Call  plugin pre-solr-query if defined
            search_type_plugin = 'search.plugins.{0}'.format(search_type)
            if search_type_plugin in self.discovered_plugins:
                context, solr_query = self.discovered_plugins[search_type_plugin].pre_mlt_solr_query(
                    context,
                    solr_query,
                    request,
                    self.searches[search_type], self.fields[search_type],
                    self.codes_fr if lang == 'fr' else self.codes_en,
                    record_id)

            # Query Solr
            solr_response = solr.query(core_name, solr_query)

            if search_type_plugin in self.discovered_plugins:
                context, solr_query = self.discovered_plugins[search_type_plugin].post_mlt_solr_query(
                    context,
                    solr_response,
                    solr_query,
                    request,
                    self.searches[search_type], self.fields[search_type],
                    self.codes_fr if lang == 'fr' else self.codes_en,
                    record_id)

            context['docs'] = solr_response.data['moreLikeThis'][record_id]['docs']
            context['original_doc'] = solr_response.docs[0]
            if 'prev_record' in request.session:
                context['back_to_url'] =  request.session['prev_record']

            return render(request, "more_like_this.html", context)

        else:
            return render(request, '404.html', get_error_context(search_type, lang))


class HomeView(SearchView):

    def __init__(self):
        super().__init__()

    def get(self, request: HttpRequest, lang='en'):
        lang = request.LANGUAGE_CODE
        context = {
            "language": lang,
            "cdts_version": settings.CDTS_VERSION,
            "dcterms_lang": 'fra' if lang == 'fr' else 'eng',
            "ADOBE_ANALYTICS_URL": settings.ADOBE_ANALYTICS_URL,
            "GOOGLE_ANALYTICS_GTM_ID": settings.GOOGLE_ANALYTICS_GTM_ID,
            "GOOGLE_ANALYTICS_PROPERTY_ID": settings.GOOGLE_ANALYTICS_PROPERTY_ID,
            "query_path": request.META["QUERY_STRING"],
            "path_info": request.META["PATH_INFO"],
            'parent_path': request.META["PATH_INFO"],
            "url_uses_path": settings.SEARCH_LANG_USE_PATH,
            "footer_snippet": "search_snippets/default_footer.html",
            "breadcrumb_snippet": "search_snippets/default_breadcrumb.html",
            "info_message_snippet": "search_snippets/default_info_message.html",
            "about_message_snippet": "search_snippets/default_about_message.html",
            "search_list": list(self.searches.values())
        }

        return render(request, "homepage.html", context)


class DefaultView(View):

    def get(self, request: HttpRequest):
        if settings.SEARCH_LANG_USE_PATH:
            return redirect('/search/{0}/'.format(request.LANGUAGE_CODE) )
        else:
            return redirect('/search/')
