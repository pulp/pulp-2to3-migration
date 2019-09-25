export PULP_FILE_PR_NUMBER=$(echo $COMMIT_MSG | grep -oP 'Required\ PR:\ https\:\/\/github\.com\/pulp\/pulp_file\/pull\/(\d+)' | awk -F'/' '{print $7}')

cd ..
git clone https://github.com/pulp/pulp_file.git
if [ -n "$PULP_FILE_PR_NUMBER" ]; then
  cd pulp_file
  git fetch origin +refs/pull/$PULP_FILE_PR_NUMBER/merge
  git checkout FETCH_HEAD
  cd ..
fi

cd pulp-2to3-migration
