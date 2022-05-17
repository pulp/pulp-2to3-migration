Plugin removal
==============

When the move from Pulp 2 to Pulp 3 is done, the pulp-2to3-migration plugin is no longer needed.

It is recommended to remove the plugin because:

    * it will reach EOL sooner than other Pulp plugins. Having it installed will prevent the system
      from further upgrades.
    * it stores a lot of Pulp 2 data in the Pulp 3 database which was used during migration but is
      no longer needed and just takes space.


``remove-plugin`` command use
-----------------------------

In order to remove a Pulp plugin, just uninstalling it is not enough, first the ``remove-plugin``
command should be used.

    1. Stop all Pulp services.
    2. Run the ``remove-plugin`` command.

    This step ensures that all data for this plugin is properly removed from the database.

    .. warning::

        If this step is skipped, other plugins might not function properly (e.g. repository removal
        will fail for the migrated repositories).

    .. code-block:: bash

        $ pulpcore-manager remove-plugin pulp_2to3_migration

    3. Uninstall the pulp-2to3-migration plugin.

    Steps to uninstall depend on how it was originally installed (usually, via ``pip`` for PyPI
    installations or ``dnf`` for RPM installations)

    .. warning::

        It is very important to perform the uninstallation step for this plugin because it has
        relations and references to other Pulp plugins. If this step is skipped, other plugins might not
        function properly (e.g. repository removal will fail for the migrated repositories).

    4. Start Pulp services.


It is possible to install the plugin again following the standard process.
Under the normal circumstances, there should be no need for it.
