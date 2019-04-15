from gettext import gettext as _

import os

from pkg_resources import iter_entry_points

from django.core.management import BaseCommand, CommandError
from mongoengine import connect

class Command(BaseCommand):
    """
    Django management command for migrating from Pulp 2 to Pulp 3.
    """
    help = _('Migrate data from Pulp 2 to Pulp 3.')

    def add_arguments(self, parser):
        parser.add_argument('--db_host',
                            default='localhost',
                            help=_('The host where MongoDB for Pulp 2 is running. Default is '
                                   'localhost.'))
        parser.add_argument('--db_port',
                            default=27017,
                            type=int,
                            help=_('The port where MongoDB for Pulp 2 is running. Default is '
                                   '27017.'))
        parser.add_argument('--db_name',
                            default='pulp_database',
                            help=_('The Pulp 2 MongoDB database to use. Default is pulp_database.'))
        parser.add_argument('--db_user',
                            default='admin',
                            help=_('The Pulp 2 MongoDB database user. Default is admin.'))
        parser.add_argument('--db_passwd',
                            default='admin',
                            help=_('The Pulp 2 MongoDB database password. Default is admin.'))
        all_supported_plugins = []
        for entry_point in iter_entry_points('pulp_2to3_migrate.plugin'):
            all_supported_plugins.append(entry_point.name)
        parser.add_argument('--plugins',
                            default=None,
                            choices=all_supported_plugins,
                            nargs='*',
                            help=_('Pulp 3 plugins to migrate to. By default all supported content '
                                   'types are migrated.'))

    def handle(self, *args, **options):
        if not os.access('/var/lib/pulp', os.W_OK | os.X_OK):
            raise CommandError(_('/var/lib/pulp is not writable'))

        mongodb_connection = connect(host=options.get('db_host'),
                                     port=options.get('db_port'),
                                     username=options.get('db_user'),
                                     password=options.get('db_passwd'))
        pulp2_db = mongodb_connection.get_database(options.get('db_name'))

        migrate_all = False
        if not options['plugins']:
            migrate_all = True

        for entry_point in iter_entry_points('pulp_2to3_migrate.plugin'):
            if migrate_all or entry_point.name in options['plugins']:
                plugin_migrate = entry_point.load()
                plugin_migrate(pulp2_db)

