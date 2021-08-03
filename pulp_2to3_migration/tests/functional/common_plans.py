"""
Migration plans which are used by many different tests.
"""

import json


DEB_COMPLEX_PLAN = json.dumps({
    "plugins": [{
        "type": "deb",
        "repositories": [
            {
                "name": "debian-empty",
                "pulp2_importer_repository_id": "debian-empty",
                "repository_versions": [
                    {
                        "pulp2_repository_id": "debian-empty",  # content count: 0
                        "pulp2_distributor_repository_ids": ["debian-empty"]
                    }
                ]
            },
            {
                "name": "debian",
                "pulp2_importer_repository_id": "debian",
                "repository_versions": [
                    {
                        "pulp2_repository_id": "debian",
                        "pulp2_distributor_repository_ids": ["debian"]
                    }
                ]
            },
            {
                "name": "debian-complex-dists",
                "pulp2_importer_repository_id": "debian-complex-dists",
                "repository_versions": [
                    {
                        "pulp2_repository_id": "debian-complex-dists",
                        "pulp2_distributor_repository_ids": ["debian-complex-dists"]
                    }
                ]
            },
            {
                "name": "debian_update",
                "pulp2_importer_repository_id": "debian_update",
                "repository_versions": [
                    {
                        "pulp2_repository_id": "debian_update",
                        "pulp2_distributor_repository_ids": ["debian_update"]
                    }
                ]
            },
        ],

    }]
})

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

INITIAL_REPOSITORIES = [
    {
        "name": "rpm-empty",
        "pulp2_importer_repository_id": "rpm-empty",  # policy: immediate
        "repository_versions": [
            {
                "pulp2_repository_id": "rpm-empty",  # content count: 0
                "pulp2_distributor_repository_ids": ["rpm-empty"]
            }
        ]
    },
    {
        "name": "rpm-empty-for-copy",
        "pulp2_importer_repository_id": "rpm-empty-for-copy",  # policy: immediate
        "repository_versions": [
            {
                "pulp2_repository_id": "rpm-empty-for-copy",  # content count: 0
                "pulp2_distributor_repository_ids": ["rpm-empty-for-copy"]
            }
        ]
    },
    {
        "name": "rpm-with-modules",
        "pulp2_importer_repository_id": "rpm-with-modules",  # policy: on_demand
        "repository_versions": [
            {
                "pulp2_repository_id": "rpm-with-modules",
                "pulp2_distributor_repository_ids": ["rpm-with-modules"]
            }
        ]
    },
    {
        "name": "rpm-distribution-tree",
        "pulp2_importer_repository_id": "rpm-distribution-tree",  # policy: on_demand
        "repository_versions": [
            {
                "pulp2_repository_id": "rpm-distribution-tree",
                "pulp2_distributor_repository_ids": ["rpm-distribution-tree"]
            }
        ]
    },
    {
        "name": "srpm-unsigned",
        "pulp2_importer_repository_id": "srpm-unsigned",  # policy: on_demand
        "repository_versions": [
            {
                "pulp2_repository_id": "srpm-unsigned",
                "pulp2_distributor_repository_ids": ["srpm-unsigned"]
            }
        ]
    },
]

RPM_COMPLEX_PLAN = json.dumps({
    "plugins": [{
        "type": "rpm",
        "repositories": INITIAL_REPOSITORIES,
    }]
})


FILE_SIMPLE_PLAN = json.dumps({"plugins": [{"type": "iso"}]})
RPM_SIMPLE_PLAN = json.dumps({"plugins": [{"type": "rpm"}]})
DEB_SIMPLE_PLAN = json.dumps({"plugins": [{"type": "deb"}]})

FILE_DISTRIBUTOR_DIFF_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file",  # content count: iso - 3
                        "pulp2_distributor_repository_ids": ["file-many"]
                    }
                ]
            },
            {
                "name": "file-many",
                "pulp2_importer_repository_id": "file-many",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file-many",  # content count: iso - 250
                        "pulp2_distributor_repository_ids": ["file"]
                    }
                ]
            }
        ]
    }]
})

FILE_IMPORTER_DIFF_PLAN = json.dumps({
    "plugins": [{
        "type": "iso",
        "repositories": [
            {
                "name": "file",
                "pulp2_importer_repository_id": "file-many",  # policy: on_demand
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file"  # content count: iso - 3
                    }
                ]
            },
            {
                "name": "file-many",
                "pulp2_importer_repository_id": "file",  # policy: immediate
                "repository_versions": [
                    {
                        "pulp2_repository_id": "file-many"  # content count: iso - 250
                    }
                ]
            }
        ]
    }]
})
