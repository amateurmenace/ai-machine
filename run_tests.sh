#!/bin/bash
# Run the Community AI test suite.
#
# None of these need a GPU, a vector database, or a language model: the vector
# store and the model are replaced with test doubles, and everything between
# them is the real code. They are safe to run in CI.

set -u
cd "$(dirname "$0")"

SUITES=(
  tests.test_rag           # retrieval, citations, pipeline assembly
  tests.test_gateway       # auth, scopes, rate limits, HTTP behavior
  tests.test_app_wiring    # routes, imports, OpenAPI schema
  tests.test_end_to_end    # the real agent path, model and database stubbed
)

failed=0
for suite in "${SUITES[@]}"; do
  echo
  echo "### $suite"
  if ! python3 -m "$suite"; then
    failed=$((failed + 1))
  fi
done

echo
if [ "$failed" -gt 0 ]; then
  echo "$failed suite(s) failed."
  exit 1
fi
echo "All suites passed."
