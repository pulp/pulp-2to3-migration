#!/bin/bash

set -euv

openssl aes-256-cbc -K $encrypted_None_key -iv $encrypted_None_iv -in .travis/pulp-infra.enc -out ~/.ssh/pulp-infra -d
sudo chmod 600 ~/.ssh/pulp-infra

echo "docs.pulpproject.org,8.43.85.236 ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYAAAAIbmlzdHAyNTYAAABBBGXG+8vjSQvnAkq33i0XWgpSrbco3rRqNZr0SfVeiqFI7RN/VznwXMioDDhc+hQtgVhd6TYBOrV07IMcKj+FAzg=" >> /home/travis/.ssh/known_hosts
chmod 644 /home/travis/.ssh/known_hosts

pip3 install -r doc_requirements.txt

cd .travis

export PYTHONUNBUFFERED=1
export DJANGO_SETTINGS_MODULE=pulpcore.app.settings
export PULP_SETTINGS=$TRAVIS_BUILD_DIR/.travis/settings/settings.py

eval "$(ssh-agent -s)" #start the ssh agent
ssh-add ~/.ssh/pulp-infra

python3 docs-builder.py --build-type $1 --branch $TRAVIS_BRANCH
