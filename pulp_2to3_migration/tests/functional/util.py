from contextlib import closing
from time import sleep

import psycopg2

from .dynaconf_config import settings

QUERY_ALL_TABLES = """
    SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
"""
TABLES_TO_KEEP = [
    # django's sqlclear or sqlflush excludes this table when cleaning up the db
    'django_migrations',

    # not to create an admin user every time
    'auth_user',

    # not to be doomed by the lack of permissions
    'auth_permission',
    'core_accesspolicy',

    # 'auth_permission' references it, so it should not be truncated
    'django_content_type',
]


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


def _get_db_connection():
    return psycopg2.connect(
        host=settings.DATABASES['default']['HOST'],
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        dbname=settings.DATABASES['default']['NAME']
    )


def teardown():
    """
    A teardown utility which is expected to be used in tests as a teardown class or instance method.

    Cleans all the Pulp 3 tables without shutting down the services.
    """
    with closing(_get_db_connection()) as conn:
        with closing(conn.cursor()) as cursor:
            cursor.execute(QUERY_ALL_TABLES)
            tables = cursor.fetchall()
            table_names_str = ', '.join(t[0] for t in tables if t[0] not in TABLES_TO_KEEP)
            truncate_query = f'TRUNCATE {table_names_str}'
            cursor.execute(truncate_query)
        conn.commit()
