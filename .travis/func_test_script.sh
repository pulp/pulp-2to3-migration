#!/usr/bin/env bash
# coding=utf-8

set -mveuo pipefail

# Note: This function is in the process of being merged into after_failure
show_logs_and_return_non_zero() {
  readonly local rc="$?"
  return "${rc}"
}
export -f show_logs_and_return_non_zero

# Run functional tests
set +u

export PYTHONPATH=$TRAVIS_BUILD_DIR:$TRAVIS_BUILD_DIR/../pulpcore:${PYTHONPATH}
export DJANGO_SETTINGS_MODULE=pulpcore.app.settings
export PULP_CONTENT_ORIGIN=http://localhost

set -u

pytest -v -r sx --color=yes --pyargs pulp_2to3_migration.tests.functional || show_logs_and_return_non_zero
