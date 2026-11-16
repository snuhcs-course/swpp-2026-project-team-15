# Existing Pixabay images: manual database step

**Preparation only; isolated PostgreSQL 17 and API/image integration rehearsals
passed. Separate operational approval is still required.** No reset/import
is needed. Commit and verify this migration **before code deployment or a main
push that triggers deployment**. The old API tolerates the added nullable column.

Use the approved existing-catalog bundle, including `expected.sql` (eight-table
baseline and 537 URL mappings), image hashes and archive. Never substitute the
972-recipe bundle. Review the file hashes and current code against the approved
baseline; changed data, code or conflicting image files require a new review.

## Preflight and backup

Coordinate a window without CI/code or dataset operations. In Bash on the host,
set the actual verified paths; run the following only after operational approval:

```bash
set -euo pipefail
bundle=/absolute/path/to/verified/pixabay-bundle
sql=/absolute/path/to/reviewed/checkout/deploy/recipe-images
previous=$(readlink -f /opt/mylittlechef/current)
cd "$previous"
export APP_IMAGE="mylittlechef:$(git rev-parse HEAD)"
export RECIPE_IMAGES_DIR=/opt/mylittlechef/assets/recipe-images
exec 9>/opt/mylittlechef/deploy.lock
flock -n 9
umask 077
work=$(mktemp -d /opt/mylittlechef/backups/pixabay-XXXXXXXX)
printf '%s\n' "$previous" > "$work/previous-checkout"
git rev-parse HEAD > "$work/previous-sha"
docker compose config > "$work/previous-compose.yaml"
docker compose exec -T postgres psql -X -q -U chef -d chef -v ON_ERROR_STOP=1 \
  -c "BEGIN READ ONLY; COPY (SELECT recipe_id, to_jsonb(r)->>'main_image_url' AS main_image_url FROM public.recipe r ORDER BY recipe_id) TO STDOUT WITH (FORMAT csv, HEADER true); COMMIT;" \
  > "$work/previous-urls.csv"
docker compose exec -T postgres psql -X -q -U chef -d chef -v ON_ERROR_STOP=1 \
  -c "COPY (SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema='public' AND table_name='recipe' ORDER BY ordinal_position) TO STDOUT WITH (FORMAT csv, HEADER true)" \
  > "$work/previous-columns.csv"

# This only constructs the input stream; it does not connect or apply changes.
inputs() {
  cat "$sql/begin.sql" "$bundle/expected.sql"
  printf '\\copy image_previous FROM stdin WITH (FORMAT csv, HEADER true)\n'
  cat "$work/previous-urls.csv"
  printf '\\.\n'
}
{ inputs; cat "$sql/check.sql"; printf 'ROLLBACK;\n'; } |
  docker compose exec -T postgres psql -X -q -U chef -d chef -v ON_ERROR_STOP=1

docker compose exec -T postgres pg_dump -U chef -d chef -Fc > "$work/database.dump"
test -s "$work/database.dump"
docker compose exec -T postgres pg_restore --list < "$work/database.dump" \
  > "$work/backup-contents.txt"
test -s "$work/backup-contents.txt"
sha256sum "$work/database.dump" > "$work/database.dump.sha256"
```

Keep the work directory private; rendered Compose may contain configuration.
Archive readability is checked above; rehearse actual backup restoration in a
disposable database before approval. Save and review the previous code/config
and column report, including whether the image column was absent. Confirm every
image is uploaded at the fixed root with approved hashes and readable permissions
before the next step. Failure here means do not stop the API or apply SQL.

## Migration and post-commit verification

Continue in the same locked shell. Stop on any error; do not deploy new code:

```bash
docker compose stop api
{ inputs; cat "$sql/check.sql" "$sql/apply.sql" "$sql/check.sql" "$sql/verify.sql";
  printf 'COMMIT;\n'; } |
  docker compose exec -T postgres psql -X -q -U chef -d chef -v ON_ERROR_STOP=1

# A separate connection confirms the committed values and all non-image fields.
{ inputs; cat "$sql/check.sql" "$sql/verify.sql"; printf 'ROLLBACK;\n'; } |
  docker compose exec -T postgres psql -X -q -U chef -d chef -v ON_ERROR_STOP=1
flock -u 9
exec 9>&-
```

Only after both commands succeed, deploy the reviewed target SHA using existing
`deploy/release.sh`. Do not call release/db while holding the manual lock. Verify
readiness, catalog preservation and all 307 image responses separately before
declaring image rollout complete. Release updates code metadata on readiness;
this does not mean images passed verification.

## Manual recovery

If SQL fails before commit, psql stops and its disconnected transaction rolls
back. If the outcome is unclear, inspect with the separate verification command;
do not retry blindly. A stopped old API must be restarted explicitly when safe.

Readiness exhaustion in release attempts the existing code/config rollback.
Build/start failures and interruption do not guarantee rollback. Inspect running
containers and `/ready`. To recreate the recorded old code manually, with the
common lock held, use its checkout and image (no build):

```bash
previous=$(cat "$work/previous-checkout")
cd "$previous"
export APP_IMAGE="mylittlechef:$(cat "$work/previous-sha")"
export RECIPE_IMAGES_DIR=/opt/mylittlechef/assets/recipe-images
exec 9>/opt/mylittlechef/deploy.lock
flock -n 9
docker compose up -d --no-build postgres api
docker compose up -d --no-build --force-recreate nginx
curl -fsS --max-time 15 http://127.0.0.1/ready
# Only after confirming the running image matches previous-sha:
ln -sfn "$previous" /opt/mylittlechef/current
cp "$work/previous-sha" /opt/mylittlechef/deployed-sha
```

Keep the previous checkout/config; do not blindly run release.sh against a failing
candidate again. If restarting after interruption, recover `work`, `bundle` and
`sql` explicitly from the saved paths and redefine `inputs` before proceeding.

Code rollback does not restore URLs or files. If URL restoration is needed, first
verify current URLs still match the approved deployed mapping, then restore only
the saved URL values. Continue under the common lock with the `inputs` function
and original work directory retained:

```bash
docker compose stop api
{ inputs; cat "$sql/check.sql" "$sql/verify.sql" "$sql/restore.sql" "$sql/check.sql" "$sql/verify-previous.sql";
  printf 'COMMIT;\n'; } |
  docker compose exec -T postgres psql -X -q -U chef -d chef -v ON_ERROR_STOP=1
{ inputs; cat "$sql/check.sql" "$sql/verify-previous.sql"; printf 'ROLLBACK;\n'; } |
  docker compose exec -T postgres psql -X -q -U chef -d chef -v ON_ERROR_STOP=1
docker compose start api
curl -fsS --max-time 15 http://127.0.0.1/ready
flock -u 9
exec 9>&-
```

The restore sequence checks exact saved URLs before commit and again in a new
connection, and retains the nullable column.
Any unexpected current URLs or catalog drift must be inspected, not overwritten.
Fix image files/permissions or the configured bind source manually and recreate
the API when required. A release using old Compose may not support image mounts;
that rollback does not guarantee image availability. Do not automatically restore
the full dump, drop the column, delete backups or claim recovery without checking.
