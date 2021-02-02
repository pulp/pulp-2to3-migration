BINDINGS_CONFIGURATION = {
    'username': 'admin',
    'password': 'password',
    'host': 'http://pulp',
}

TABLES_TO_KEEP = (
    # django's sqlclear or sqlflush excludes this table when cleaning up the db
    'django_migrations',

    # not to create an admin user every time
    'auth_user',

    # not to be doomed by the lack of permissions
    'auth_permission',
    'core_accesspolicy',

    # 'auth_permission' references it, so it should not be truncated
    'django_content_type',

    # not to freak out the tasking system
    'core_reservedresource',
    'core_reservedresourcerecord',
    'core_task',
    'core_taskgroup',
    'core_taskreservedresource',
    'core_taskreservedresourcerecord',
    'core_worker',
)

TRUNCATE_TABLES_QUERY_BASH = f"""
DO $$
  BEGIN
    EXECUTE format('TRUNCATE %s',
                    (SELECT STRING_AGG(table_name, ', ')
                       FROM information_schema.tables
                         WHERE table_schema = 'public' AND table_name NOT IN {TABLES_TO_KEEP}
                    )
                  );
  END
$$;
"""  # noqa

FILE_URL = 'https://repos.fedorapeople.org/pulp/pulp/fixtures/file/PULP_MANIFEST'
FILE_MANY_URL = 'https://repos.fedorapeople.org/pulp/pulp/fixtures/file-many/PULP_MANIFEST'
FIXTURES_BASE_URL = 'https://fixtures.pulpproject.org/'
