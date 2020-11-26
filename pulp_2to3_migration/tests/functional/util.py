# import os
import subprocess

from time import sleep

from .dynaconf_config import settings

from pulp_smash import cli  # , utils
from pulp_smash import config as smash_config


def monitor_task(tasks_api, task_href):
    """Polls the Task API until the task is in a completed state.

    Prints the task details and a success or failure message. Exits on failure.

    Args:
        tasks_api (pulpcore.client.pulpcore.TasksApi): an instance of a configured TasksApi client
        task_href(str): The href of the task to monitor

    Returns:
        list[str]: List of hrefs that identify resource created by the task

    """
    completed = ['completed', 'failed', 'canceled']
    task = tasks_api.read(task_href)
    while task.state not in completed:
        sleep(2)
        task = tasks_api.read(task_href)
    if task.state == 'completed':
        print("The task was successful.")
    else:
        print("The task did not finish successfully.")
    return task


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


def set_pulp2_snapshot(name='20191031'):
    """

    :param name:
    :return:
    """
    smash_cfg = smash_config.get_config()
    smash_cli_client = cli.Client(smash_cfg)
    # pulp2_mongodb_conf = utils.get_pulp_setting(smash_cli_client, "PULP2_MONGODB")
    # mongodb_host = pulp2_mongodb_conf['seeds'].split(':')[0]

    # until the fix is in place in pulp-smash
    # import re
    # pattern = re.compile(r'seeds: (.*?):')
    # mongodb_host = pattern.findall(pulp2_mongodb_conf)[0]

    pulp2_fs_setup_script_path = '/tmp/set_pulp2_fs.sh'
    # if not os.path.isfile(pulp2_fs_setup_script_path):
    #     basepath = os.path.dirname(os.path.realpath(__file__))
    #     pulp2_fs_setup_script_path = os.path.join(basepath, '/scripts/set_pulp2_fs.sh')
    cmd = ('bash', pulp2_fs_setup_script_path, name)
    smash_cli_client.run(cmd, sudo=True)

    cmd = ('wget', f'https://github.com/pulp/pulp-2to3-migration-test-fixtures/raw/master'
                   f'/{name}/pulp2filecontent.{name}.archive')

    completed_process = subprocess.run(
        cmd, env={}, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    if completed_process.returncode != 0:
        raise RuntimeError(str(completed_process.stderr))

    # it is required to have '=' after the named parameter
    cmd = ('mongorestore', f'--archive=pulp2filecontent.{name}.archive')

    # mongo_cmd = 'db.createUser({user:"travis",pwd:"travis",roles:["readWrite"]});'
    # cmd = ('mongo', '--host', mongodb_host , 'pulp_database', mongo_cmd)
    # smash_cli_client.run(cmd, sudo=True)

    completed_process = subprocess.run(
        cmd, env={}, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    if completed_process.returncode != 0:
        raise RuntimeError(str(completed_process.stderr))

    cmd = ('mongo', 'pulp_database', '--eval', '\'db.createUser({user:"ci_cd",pwd:"ci_cd", '
                                               'roles:["readWrite"]});\'')

    completed_process = subprocess.run(
        cmd, env={}, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    if completed_process.returncode != 0:
        raise RuntimeError(str(completed_process.stderr))
