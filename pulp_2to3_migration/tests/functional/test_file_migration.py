from time import sleep
import unittest
from pulpcore.client.pulpcore import (ApiClient as CoreApiClient, Configuration,
                                      TasksApi)
from pulpcore.client.pulp_2to3_migration import (ApiClient as MigrationApiClient,
                                                 MigrationPlansApi)


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
        print("The task was successfful.")
    else:
        print("The task did not finish successfully.")
    return task


class TestMigrationPlan(unittest.TestCase):
    """Test the APIs for creating a Migration Plan."""

    @classmethod
    def setUpClass(cls):
        """
        Create all the client instances needed to communicate with Pulp.
        """

        configuration = Configuration()
        configuration.username = 'admin'
        configuration.password = 'password'
        configuration.safe_chars_for_path_param = '/'

        core_client = CoreApiClient(configuration)
        # file_client = FileApiClient(configuration)
        migration_client = MigrationApiClient(configuration)

        # Create api clients for all resource types
        # artifacts = ArtifactsApi(core_client)
        # repositories = RepositoriesApi(core_client)
        # repoversions = RepositoriesVersionsApi(core_client)
        # filecontent = ContentFilesApi(file_client)
        # filedistributions = DistributionsFileApi(core_client)
        # filepublications = PublicationsFileApi(file_client)
        # fileremotes = RemotesFileApi(file_client)
        cls.tasks = TasksApi(core_client)
        # uploads = UploadsApi(core_client)
        cls.migration_plans = MigrationPlansApi(migration_client)

    def test_create_migration_plan(self):
        """Test that a valid Migration Plan can be created."""
        migration_plan = '{"plugins": [{"type": "iso"}]}'
        mp = self.migration_plans.create({'plan': migration_plan})
        mp_run_response = self.migration_plans.run(mp.pulp_href, data={})
        task = monitor_task(self.tasks, mp_run_response.task)
        self.assertEqual(task.state, "completed")
