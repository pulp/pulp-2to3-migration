from dynaconf import Dynaconf

settings = Dynaconf(
    settings_files=[
        "func_test_settings.py",
        "/pulp-2to3-migration/func_test_settings.py",
        "/etc/pulp/settings.py",
    ]
)
