import logging
import pkg_resources

from collections import namedtuple
from gettext import gettext as _

_logger = logging.getLogger(__name__)

# { plugin_name: PluginMigratorClass }
PLUGIN_MIGRATORS = {}
MissingMigrator = namedtuple('MissingMigrator', 'pulp3_plugin')

if not PLUGIN_MIGRATORS:
    for entry_point in pkg_resources.iter_entry_points(group='migrators'):
        try:
            PLUGIN_MIGRATORS[entry_point.name] = entry_point.load()
        except ModuleNotFoundError as exc:
            _logger.info(_(
                'Plugin %s is not installed in pulp3 '
                'therefore it will not be migrated from pulp2') % exc.name
            )
            missing = MissingMigrator(exc.msg)
            PLUGIN_MIGRATORS[entry_point.name] = missing
