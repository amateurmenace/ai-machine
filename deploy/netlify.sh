#!/usr/bin/env bash
#
# Publish the console to Netlify.
#
# This is the deployment the project actually has: a React frontend on Netlify,
# and an API on the machine that holds the archive and runs the model.
# deploy/cloudrun.sh moves the API into the cloud instead, which is a different
# decision and not currently the recommended one — ROADMAP.md section 2.2 says
# why.
#
# TWO KINDS OF BUILD
#
# --no-api is the public site as it stands: the API is not on the internet, so
# the console is built knowing there is none (REACT_APP_API_URL=none). The
# landing page, the guide and the rules work; the console says the assistant is
# not open to the public. The same build, served by the API on its own machine,
# is the operator's console.
#
# --api-url is for the day an API is reachable from the web. Its administrative
# routes then answer the web only with the admin token (api/admin_guard.py).
#
# WHICH SITE, WHICH ACCOUNT, WHICH TEAM
#
# One CLI, one active login, and it is easy to be signed into a work identity
# and a personal one. A Netlify site belongs to a team rather than a login, and
# deployments go to the personal account, never the Hope Group. So this prints
# the account, the site and the team that owns it, and refuses a Hope Group
# site outright. Set EXPECTED_SITE to make the site check strict.
#
# WHAT IT REFUSES TO DO
#
# It will not publish a build directory it did not just build. A stale build/
# is the classic way to ship last week's console and spend an afternoon
# wondering why a fix did not take.
#
# It will not publish a build whose API is unstated. A console built without
# REACT_APP_API_URL, served from Netlify, asks Netlify for the API and gets the
# landing page back, which looks like a backend outage and is not one.
#
# It will not let the Netlify CLI rebuild what it has just checked. The CLI
# builds before deploying unless told not to, using the dashboard's settings
# rather than these, and would publish its own build over this one.
#
# It publishes a draft by default. Production takes --prod, typed on purpose.
#
#   ./deploy/netlify.sh --no-api                       # the public site, a draft
#   ./deploy/netlify.sh --no-api --prod                # the real one
#   ./deploy/netlify.sh --api-url https://api.example.org --prod

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND="$ROOT/frontend"

EXPECTED_SITE="${EXPECTED_SITE:-}"
API_URL="${REACT_APP_API_URL:-}"
ASSUME_YES="${ASSUME_YES:-}"
PROD=""
SKIP_BUILD=""
NO_API=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prod)        PROD="1"; shift ;;
    --no-api)      NO_API="1"; shift ;;
    --site)        EXPECTED_SITE="${2:-}"; shift 2 ;;
    --api-url)     API_URL="${2:-}"; shift 2 ;;
    --skip-build)  SKIP_BUILD="1"; shift ;;
    --yes|-y)      ASSUME_YES="1"; shift ;;
    -h|--help)     awk 'NR > 1 && /^#/ { sub(/^# ?/, ""); print; next } NR > 1 { exit }' "$0"; exit 0 ;;
    *)             echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

say() { printf '%s\n' "$*"; }
die() { printf '\n%s\n' "$*" >&2; exit 1; }

# Run from a terminal, the CLI decorates what it prints: colors, a spinner's
# cursor-control bytes, carriage returns. Run from a cloud session it does
# not, which is where this script was written. Everything it parses goes
# through here first.
plain() {
  tr -d '\r' | perl -pe 's/\e\[[0-9;?]*[ -\/]*[@-~]//g; s/[\x00-\x08\x0b\x0c\x0e-\x1f]//g'
}

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

# The link is kept in frontend/.netlify, so that is where the CLI can say which
# site this is.
cd "$FRONTEND"

say "Checking who you are signed in as."
STATUS="$(netlify status 2>/dev/null | plain || true)"
ACCOUNT="$(printf '%s\n' "$STATUS" | sed -n 's/.*Email: *//p' | sed 's/[[:space:]]*$//' | head -1)"
# "Current site" in older CLIs, "Current project" since Netlify renamed them.
SITE="$(printf '%s\n' "$STATUS" | sed -n -E 's/.*Current (site|project): *//p' | sed 's/[[:space:]]*$//' | head -1)"
SITE_ID="$(printf '%s\n' "$STATUS" | sed -n -E 's/.*(Site|Project) Id: *//p' | sed 's/[[:space:]]*$//' | head -1)"

[[ -n "$ACCOUNT" ]] || die \
"Not signed in to Netlify, or the CLI could not say who you are.
  netlify login"

[[ -n "$SITE" && -n "$SITE_ID" ]] || die \
"frontend/ is not linked to a Netlify site.
  cd frontend && netlify link"

# With a terminal on stdin the CLI writes its spinner to stdout before the
# JSON, so the JSON is taken from its first brace rather than from byte one.
SITE_JSON="$(netlify api getSite --data "{\"site_id\":\"$SITE_ID\"}" 2>/dev/null | plain || true)"
TEAM="$(printf '%s' "$SITE_JSON" | node -e '
  let s = "";
  process.stdin.on("data", d => s += d).on("end", () => {
    const start = s.indexOf("{");
    if (start < 0) return;
    try { const j = JSON.parse(s.slice(start)); if (j.account_name || j.account_slug) console.log(`${j.account_name} (${j.account_slug})`); }
    catch (e) {}
  });' || true)"

[[ -n "$TEAM" ]] || die \
"Could not read which team owns $SITE (id: ${SITE_ID:-unknown}). Nothing was published.
The CLI answered:
$(printf '%s\n' "$SITE_JSON" | head -5)"

if printf '%s' "$TEAM" | grep -qi "hope"; then
  die \
"Refusing to deploy.

  site:  $SITE
  team:  $TEAM

Deployments go to the personal account, never the Hope Group. Link a site that
belongs to the personal team:  cd frontend && netlify link"
fi

if [[ -n "$EXPECTED_SITE" && "$SITE" != *"$EXPECTED_SITE"* ]]; then
  die \
"Refusing to deploy.

  expected site:  $EXPECTED_SITE
  linked site:    $SITE

Link the right site, or change EXPECTED_SITE if this one is correct."
fi

# --- the API --------------------------------------------------------------

if [[ -n "$NO_API" ]]; then
  [[ -z "$API_URL" ]] || die \
"--no-api, and an API URL ($API_URL). Those contradict each other; pick one."
  BUILD_API="none"
else
  if [[ -z "$API_URL" ]]; then
    die \
"No API stated. A console built without one asks Netlify for the API and gets
the landing page back, which looks like an outage.

The API is not on the internet:        ./deploy/netlify.sh --no-api
It is, behind a tunnel you control:    ./deploy/netlify.sh --api-url https://api.example.org"
  fi

  case "$API_URL" in
    https://*) ;;
    http://localhost*|http://127.0.0.1*)
      die "REACT_APP_API_URL is $API_URL. A published console cannot reach your
laptop, and a public page should not try. Use --no-api, or the tunnel hostname." ;;
    *) die "REACT_APP_API_URL must be https. Got: $API_URL" ;;
  esac
  BUILD_API="$API_URL"

  # The API's CORS whitelist is in app.py and is not wildcarded, which is
  # correct. A console served from an origin the API does not know is a
  # browser error nobody can read, so it is worth saying now rather than then.
  say
  say "The API must allow this console's origin in its CORS list (app.py)."
  say "Current allowed origins:"
  sed -n '/allow_origins=\[/,/\]/p' "$ROOT/app.py" | sed -n 's/^ *"\(http[^"]*\)".*/    \1/p'
fi

# A build Netlify runs itself, from a push to the production branch, uses the
# site's own setting rather than this script's. Say so if the two disagree.
DASHBOARD_API="$(netlify env:get REACT_APP_API_URL --context production 2>/dev/null | plain | tail -1 || true)"
if [[ "$DASHBOARD_API" != "$BUILD_API" ]]; then
  say
  say "NOTE: the site's own REACT_APP_API_URL is '${DASHBOARD_API:-unset}', and this build uses"
  say "'$BUILD_API'. A build Netlify runs from git uses the site's. To make them agree:"
  say "  cd frontend && netlify env:set REACT_APP_API_URL $BUILD_API"
fi

# --- build ----------------------------------------------------------------

if [[ -z "$SKIP_BUILD" ]]; then
  say
  if [[ -n "$NO_API" ]]; then
    say "Building the public console, with no API behind it."
  else
    say "Building the console against $API_URL"
  fi
  if [[ -f package-lock.json ]]; then npm ci --silent; else npm install --silent; fi
  rm -rf build
  REACT_APP_API_URL="$BUILD_API" npm run build
else
  say "Skipping the build, as asked. Publishing whatever is in frontend/build."
fi

[[ -d build && -f build/index.html ]] || die \
"There is no build to publish at frontend/build."

# Catch the case the --skip-build flag exists for: a build made against a
# different API than the one named here.
if [[ -z "$NO_API" ]] && ! grep -rqF "$API_URL" build 2>/dev/null; then
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
say "  team:     $TEAM"
say "  site:     $SITE"
if [[ -n "$NO_API" ]]; then
  say "  api:      none (the public site; the API is not on the internet)"
else
  say "  api:      $API_URL"
fi
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

# --no-build, or the CLI builds again with the dashboard's settings and
# publishes that instead of what was just checked.
if [[ -n "$PROD" ]]; then
  netlify deploy --no-build --dir=build --prod
else
  netlify deploy --no-build --dir=build
fi

say
if [[ -n "$NO_API" ]]; then
  say "Published. Worth checking now:"
  say "  1. The landing page loads, and /console says the assistant is not open to the public."
  LOCAL_PORT="$(sed -n 's/^PORT=//p' "$ROOT/.env" 2>/dev/null | tail -1)"
  say "  2. On the machine that runs the API, the same build is the console:"
  say "     http://127.0.0.1:${LOCAL_PORT:-8000} once the API is running."
else
  say "Published. Two things worth checking now, in this order:"
  say "  1. Open the console and ask one question. A blank answer with a CORS"
  say "     error in the browser console means app.py does not allow this origin."
  say "  2. Check the tunnel is up: curl -sS $API_URL/api | head -5"
fi
