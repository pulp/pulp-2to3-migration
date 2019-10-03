SCHEMA = '''{
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "MigrationPlan",
    "type": "object",
    "properties": {
        "plugins": {
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string"
                    },
                    "protection": {
                        "type": "boolean"
                    },
                    "repositories": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string"
                                },
                                "pulp2_importer_repository_id": {
                                    "type": "string"
                                },
                                "repository_versions": {
                                    "type": "array",
                                    "minItems": 1,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "pulp2_repository_id": {
                                                "type": "string"
                                             },
                                             "distributor_ids": {
                                                 "type": "array"
                                             },
                                             "protection": {
                                                 "type": "array"
                                              }
                                        },
                                        "required": ["pulp2_repository_id"],
                                        "additionalProperties": false,
                                        "$comment": "if protection field is present then distributor_ids field should be present",
                                        "dependencies": {
                                            "protection": ["distributor_ids"]
                                        }
                                    }
                                }
                            },
                            "required": ["name", "pulp2_importer_repository_id", "repository_versions"],
                            "additionalProperties": false,
                            "$comment": "pulp2_importer_repository_id field should be specified so we know which importer to use when migrating multiple pulp2 repos into repo versions"
                        }
                    }
                },
                "required": ["type"],
                "additionalProperties": false,
                "$comment": "if protection field is present then repositories field should be present",
                "dependencies": {
                    "protection": ["repositories"],
                    "repositories": ["protection"]
                }
            }
        }
    },
    "required": ["plugins"],
    "additionalProperties": false
}'''
