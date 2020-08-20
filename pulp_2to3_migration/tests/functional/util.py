from time import sleep

from .dynaconf_config import settings


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
