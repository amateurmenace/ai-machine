#!/usr/bin/env bash
#
# Publish the console to Netlify.
#
# This is the deployment the project actually has: a React frontend on Netlify
# talking to an API on the machine that holds the archive and runs the model,
# reached over a Cloudflare tunnel. deploy/cloudrun.sh moves the API into the
# cloud instead, which is a different decision and not currently the
# recommended one — ROADMAP.md section 2.2 says why.
#
# WHICH SITE AND WHICH ACCOUNT
#
# Same reasoning as the Cloud Run script: one CLI, one active login, and it is
# easy to be signed into a work identity and a personal one. Publishing a
# community's console over the wrong site is not a mistake to discover from a
# resident. So this prints the account and the site and stops if either looks
# wrong. Set EXPECTED_SITE to make the check strict.
#
# WHAT IT REFUSES TO DO
#
# It will not publish a build directory it did not just build. A stale build/
# is the classic way to ship last week's console and spend an afternoon
# wondering why a fix did not take.
#
# It will not publish a build with no API URL. A console built without
# REACT_APP_API_URL points at nothing, loads perfectly, and fails on the first
# question, which looks like a backend outage and is not one.
#
# It publishes a draft by default. Production takes --prod, typed on purpose.
#
#   ./deploy/netlify.sh                          # draft, at a preview URL
#   ./deploy/netlify.sh --prod                   # the real one
#   EXPECTED_SITE=neighborhood-ai ./deploy/netlify.sh --prod

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"

EXPECTED_SITE="${EXPECTED_SITE:-}"
API_URL="${REACT_APP_API_URL:-}"
ASSUME_YES="${ASSUME_YES:-}"
PROD=""
SKIP_BUILD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prod)        PROD="1"; shift ;;
    --site)        EXPECTED_SITE="${2:-}"; shift 2 ;;
    --api-url)     API_URL="${2:-}"; shift 2 ;;
    --skip-build)  SKIP_BUILD="1"; shift ;;
    --yes|-y)      ASSUME_YES="1"; shift ;;
    -h|--help)     sed -n '2,33p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)             echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
die() { printf '\n%s\n' "$*" >&2; exit 1; }

# --- the tools ------------------------------------------------------------

command -v node >/dev/null 2>&1 || die \
"Node is not installed, and the console is a React app.
  macOS:  brew install node
  else:   https://nodejs.org"

if ! command -v netlify >/dev/null 2>&1; then
  die \
"The Netlify CLI is not installed. Claude cannot deploy for you without it:

  npm install -g netlify-cli
  netlify login

If you would rather not install it, the site is also connected to git and
Netlify will build on push. This script exists so a deploy can happen without
waiting for that, and so it can be checked before it goes out."
fi

# --- who, and where -------------------------------------------------------

say "Checking who you are signed in as."
ACCOUNT="$(netlify status 2>/dev/null | sed -n 's/.*Email: *//p' | head -1)"
SITE="$(netlify status 2>/dev/null | sed -n 's/.*Current site: *//p' | head -1)"

[[ -n "$ACCOUNT" ]] || die \
"Not signed in to Netlify, or the CLI could not say who you are.
  netlify login"

[[ -n "$SITE" ]] || die \
"This directory is not linked to a Netlify site.
  cd frontend && netlify link"

if [[ -n "$EXPECTED_SITE" && "$SITE" != *"$EXPECTED_SITE"* ]]; then
  die \
"Refusing to deploy.

  expected site:  $EXPECTED_SITE
  linked site:    $SITE

Link the right site, or change EXPECTED_SITE if this one is correct."
fi

# --- the API url ----------------------------------------------------------

if [[ -z "$API_URL" ]]; then
  die \
"No API URL. The console would build, load, and fail on the first question.

Pass the tunnel that fronts your API:
  ./deploy/netlify.sh --api-url https://api.neighborhoodai.org --prod

or set it in the Netlify dashboard as REACT_APP_API_URL and export it here so
this script can check that the two agree."
fi

case "$API_URL" in
  https://*) ;;
  http://localhost*|http://127.0.0.1*)
    die "REACT_APP_API_URL is $API_URL. A published console cannot reach your
laptop. Use the tunnel hostname." ;;
  *) die "REACT_APP_API_URL must be https. Got: $API_URL" ;;
esac

# The API's CORS whitelist is in app.py and is not wildcarded, which is
# correct. A console served from an origin the API does not know is a browser
# error nobody can read, so it is worth saying now rather than then.
say
say "The API must allow this console's origin in its CORS list (app.py)."
say "Current allowed origins:"
sed -n '/allow_origins=\[/,/\]/p' "$ROOT/app.py" | sed -n 's/^ *"\(http[^"]*\)".*/    \1/p'

# --- build ----------------------------------------------------------------

if [[ -z "$SKIP_BUILD" ]]; then
  say
  say "Building the console against $API_URL"
  cd "$FRONTEND"
  if [[ -f package-lock.json ]]; then npm ci --silent; else npm install --silent; fi
  rm -rf build
  REACT_APP_API_URL="$API_URL" npm run build
  cd "$ROOT"
else
  say "Skipping the build, as asked. Publishing whatever is in frontend/build."
fi

[[ -d "$FRONTEND/build" && -f "$FRONTEND/build/index.html" ]] || die \
"There is no build to publish at frontend/build."

# Catch the case the --skip-build flag exists for: a build made against a
# different API than the one named here.
if ! grep -rqF "$API_URL" "$FRONTEND/build" 2>/dev/null; then
  say
  say "WARNING: the built files do not mention $API_URL."
  say "That usually means this build was made against a different API URL."
  [[ -n "$SKIP_BUILD" ]] || die "Refusing to publish a build that does not match."
fi

# --- confirm --------------------------------------------------------------

TARGET="a draft URL"
[[ -n "$PROD" ]] && TARGET="PRODUCTION"

say
say "About to publish:"
say "  account:  $ACCOUNT"
say "  site:     $SITE"
say "  api:      $API_URL"
say "  target:   $TARGET"
say

if [[ -z "$ASSUME_YES" ]]; then
  if [[ ! -t 0 ]]; then
    die "Nothing here can confirm this. Re-run with --yes if you meant it."
  fi
  if [[ -n "$PROD" ]]; then
    read -r -p "Type the site name to publish to production: " TYPED
    [[ "$TYPED" == "$SITE" || "$SITE" == *"$TYPED"* ]] || die "That is not the site. Nothing was published."
  else
    read -r -p "Publish a draft? [y/N] " REPLY
    [[ "$REPLY" == "y" || "$REPLY" == "Y" ]] || die "Nothing was published."
  fi
fi

# --- publish --------------------------------------------------------------

cd "$FRONTEND"
if [[ -n "$PROD" ]]; then
  netlify deploy --dir=build --prod
else
  netlify deploy --dir=build
fi

say
say "Published. Two things worth checking now, in this order:"
say "  1. Open the console and ask one question. A blank answer with a CORS"
say "     error in the browser console means app.py does not allow this origin."
say "  2. Check the tunnel is up: curl -sS $API_URL/api | head -5"
