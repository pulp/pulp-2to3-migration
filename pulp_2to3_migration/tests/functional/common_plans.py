"""
Migration plans which are used by many different tests.
"""

import json


FILE_COMPLEX_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file"]
                    }
                ]
            },
            {
                "name": "file2",
                "pulp2_importer_repository_id": "file2",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file2",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file2"]
                    }
                ]
            },
            {
                "name": "file-large",
                "pulp2_importer_repository_id": "file-large",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file-large",  # content count: iso - 10
                        "pulp2_distributor_repository_ids": ["file-large"]
                    }
                ]
            },
            {
                "name": "file-many",
                "pulp2_importer_repository_id": "file-many",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file-many",  # content count: iso - 250
                        "pulp2_distributor_repository_ids": ["file-many"]
                    }
                ]
            },
        ]
    }]
})

FILE_SIMPLE_PLAN = json.dumps({"plugins": [{"type": "iso"}]})

RPM_SIMPLE_PLAN = json.dumps({"plugins": [{"type": "rpm"}]})
