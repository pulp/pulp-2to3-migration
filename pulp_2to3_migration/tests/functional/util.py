from time import sleep

from django.core.management.color import no_style
from django.db import DEFAULT_DB_ALIAS, connections


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


def teardown():
    """
    A teardown utility which is expected to be used in tests as a teardown class or instance method.

    Cleans all the Pulp 3 tables without shutting down the services.
    """
    database = DEFAULT_DB_ALIAS
    connection = connections[database]
    style = no_style()
    tables = connection.introspection.django_table_names(only_existing=True, include_views=False)
    tables.remove('auth_user')
    sql_list = connection.ops.sql_flush(style, tables, sequences=())
    connection.ops.execute_sql_flush(database, sql_list)
