import csv
from import_export import resources
from distutils.dir_util import copy_tree
from search.admin import SearchResource, FieldResource, CodeResource
from search.models import Search, Field, Code
from django.core.management.base import BaseCommand, CommandError
import logging
from os import path, mkdir
from pathlib import Path
from shutil import copyfile
import tablib


class ExportSearchResource(SearchResource):

    def __init__(self, search_id):
        super().__init__()
        self.search_id = search_id
        self._meta.import_id_fields = ['search_id']

    def get_queryset(self):
        return Search.objects.filter(search_id=self.search_id)


class ExportFieldResource(FieldResource):

    def __init__(self, search_id):
        super().__init__()
        self.search_id = search_id

    def get_queryset(self):
        sid = Search.objects.get(search_id=self.search_id)
        return Field.objects.filter(search_id=sid)


class ExportCodeResource(CodeResource):

    def __init__(self, search_id):
        super().__init__()
        self.search_id = search_id

    def get_queryset(self):
        sid = Search.objects.get(search_id=self.search_id)
        return Code.objects.filter(field_id__search_id=sid)


class Command(BaseCommand):
    help = 'Export selected search model definitions'

    logger = logging.getLogger(__name__)

    def add_arguments(self, parser):
        parser.add_argument('--import_dir', type=str, help='Directory to write export files to', required=True)
        parser.add_argument('--search_id', type=str, help='A unique code identifier for the Search', required=True)


    def handle(self, *args, **options):
        if not path.exists(options['import_dir']):
            raise CommandError('Import directory not found: ' + options['export_dir'])

        root_path = path.join(options['import_dir'], options['search_id'])
        if not path.exists(root_path):
            raise CommandError('Import search directory not found: ' + root_path)

        # Examine directory the default directories of an exported search
        db_path = path.join(root_path, 'db')
        if not path.exists(db_path):
            raise CommandError('Import search database definition directory not found: ' + db_path)
        snippet_path = path.join(root_path, 'snippets')
        if not path.exists(snippet_path):
            snippet_path = ''
        plugin_path = path.join(root_path, 'plugins')
        if not path.exists(plugin_path):
            plugin_path = ''
        data_path = path.join(root_path, 'data')
        if not path.exists(data_path):
            data_path = ''

        # Import Search

        search_resource = ExportSearchResource(options['search_id'])
        searches_path = path.join(db_path, "{0}_search.json".format(options['search_id']))
        with open(searches_path, 'r', encoding='utf-8-sig', errors="ignore") as json_file:
            imported_data = tablib.Dataset().load(json_file)
            result = search_resource.import_data(dataset=imported_data, dry_run=True)
            if result.has_errors():
                raise CommandError('Errors raised while importing Search')
            result = search_resource.import_data(dataset=imported_data, dry_run=False)
            if not result.has_errors():
                logging.info("Imported Search model")

        # Import Fields
        field_resource = ExportFieldResource(options['search_id'])
        fields_path = path.join(db_path, "{0}_fields.json".format(options['search_id']))
        with open(fields_path, 'r', encoding='utf-8-sig', errors="ignore") as json_file:
            imported_data = tablib.Dataset().load(json_file)
            result = field_resource.import_data(dataset=imported_data, dry_run=True)
            if result.has_errors():
                raise CommandError('Errors raised while importing Fields')
            result = field_resource.import_data(dataset=imported_data, dry_run=False)
            if not result.has_errors():
                logging.info("Imported Field models")

        # Import Codes - A search may not necessarily have codes
        code_resource = ExportCodeResource(options['search_id'])
        codes_path = path.join(db_path, "{0}_codes.json".format(options['search_id']))
        if path.exists(codes_path):
            with open(codes_path, 'r', encoding='utf-8-sig', errors="ignore") as json_file:
                imported_data = tablib.Dataset().load(json_file)
                result = code_resource.import_data(dataset=imported_data, dry_run=True)
                if result.has_errors():
                    raise CommandError('Errors raised while importing Codes')
                result = code_resource.import_data(dataset=imported_data, dry_run=False)
                if not result.has_errors():
                    logging.info("Imported Code models")

        # Copy custom snippets. The convention is for templates to be deployed to : BASE_DIr/templates/snippets/<search ID>/
        BASE_DIR = Path(__file__).resolve().parent.parent.parent
        custom_template_dir = path.join(BASE_DIR, 'templates', 'snippets', 'custom', options['search_id'])
        if path.exists(snippet_path):
            if not path.exists(custom_template_dir):
                mkdir(custom_template_dir)
            copy_tree(snippet_path, custom_template_dir)
            logging.info("Copying custom snippets to {0}".format(custom_template_dir))

        # Copy custom plugin - if one exists. The convention is for plugin file to be named : BASE_DIr/plugins/<search ID>.py
        custom_plug_in = path.join(BASE_DIR, 'plugins', "{0}.py".format(options['search_id']))

        if path.exists(plugin_path):
            copyfile(path.join(plugin_path, "{0}.py".format(options['search_id'])), custom_plug_in)
            logging.info("Copying custom plugin to {0}".format(plugin_path))

        # Copy custom local file