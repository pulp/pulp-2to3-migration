import logging
import os
import subprocess

from .dynaconf_config import settings

from pulp_smash import cli, utils
from pulp_smash import config as smash_config


_logger = logging.getLogger(__name__)


def get_psql_smash_cmd(sql_statement):
    """
    Generate a command in a format for pulp smash cli client to execute the specified SQL statement.
    The implication is that PostgreSQL is always running on localhost.

    Args:
        sql_statement(str): An SQL statement to execute.

    Returns:
        tuple: a command in the format for  pulp smash cli client

    """
    host = 'localhost'
    user = settings.DATABASES['default']['USER']
    password = settings.DATABASES['default']['PASSWORD']
    dbname = settings.DATABASES['default']['NAME']
    return (
        'psql', '-c', sql_statement,
        f'postgresql://{user}:{password}@{host}/{dbname}'
    )


def set_pulp2_snapshot(name):
    """
    Roll out a specific pulp 2 snapshot

    Args:
        name(str): directory name  of the pulp 2 snapshot

    """
    smash_cfg = smash_config.get_config()
    smash_cli_client = cli.Client(smash_cfg)
    pulp2_mongodb_conf = utils.get_pulp_setting(smash_cli_client, "PULP2_MONGODB")
    mongodb_host = pulp2_mongodb_conf['seeds'].split(':')[0]

    pulp2_fs_setup_script_path = '/tmp/set_pulp2.sh'

    # for running tests locally
    if smash_cfg.hosts[0].hostname == 'localhost':
        basepath = os.path.dirname(os.path.realpath(__file__))
        pulp2_fs_setup_script_path = os.path.join(basepath, 'scripts/set_pulp2.sh')

    cmd = ('bash', pulp2_fs_setup_script_path, mongodb_host, name)
    smash_cli_client.run(cmd, sudo=True)

    # needs to be done locally otherwise auth is required because password is provided in the
    # cleartext.
    cmd = ('mongo', 'pulp_database', '--eval', 'db.createUser({user:"ci_cd",pwd:"ci_cd", '
                                               'roles:["readWrite"]});')
    subprocess.run(cmd)
