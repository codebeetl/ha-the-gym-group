# HACS Submission Plan

This plan covers submission of `codebeetl/ha-the-gym-group` to the HACS default integration list. It does not cover contribution to Home Assistant Core; Core-specific work such as extracting a reusable API library, changing the manifest documentation URL, and moving brand files to `home-assistant/brands` is intentionally deferred.

The repository already has the expected HACS integration layout, `hacs.json`, a README, releases/tags, local brand assets, HACS validation workflow, Hassfest workflow, and a substantial test suite.

## Priority 0 — Confirm the submission target and repository state

Verified via `gh repo view` and `gh release list`; most of this is already satisfied:

- Repository is public, not archived, has Issues enabled, and has a description ("Home Assistant integration for The Gym Group"). No action needed.
- Topics are already set (`gym`, `hacs-integration`, `home-assistant`, `python`). Optionally add `home-assistant-custom-component` and `the-gym-group` for discoverability, but this is not blocking.
- Confirm the submitter is the repository owner or a major contributor.
- `v1.5.1` has both a git tag and a published GitHub Release (`gh release list` confirms it). No action needed.
- `The+Gym+Group_7.7_APKPure.xapk` (137 MB) is `.gitignore`d and was never committed (`git log --all -- "*.xapk"` is empty), so it isn't a leak risk in the release archive itself. Still worth deleting locally so it can't be accidentally force-added or included in a manual zip.

Acceptance criteria:

- GitHub repository metadata satisfies HACS's description, topics, issues, release, and ownership checks.
- `git status --short --ignored` shows no generated or downloaded artifact that could be accidentally included.

## Priority 1 — Make the local test environment and CI pass

An earlier local test attempt failed during collection because `pytest-homeassistant-custom-component` was not installed:

```text
ModuleNotFoundError: No module named 'pytest_homeassistant_custom_component'
```

That was an environment gap, not a code problem: the repository's own `.venv` already has Python 3.14 and the dependency installed, and `pytest tests/ --asyncio-mode=auto` currently passes (61 passed). Still worth reproducing in a disposable environment before submission, since the CI matrix (`test.yml`) pins Python 3.14 specifically and the system default `python3` on this machine resolves to 3.12 — use `python3.14` explicitly so the local repro actually matches CI:

```bash
python3.14 -m venv .venv-hacs
. .venv-hacs/bin/activate
python -m pip install -r requirements_test.txt
pytest tests/ --asyncio-mode=auto
```

If dependency installation fails, resolve that before reviewing test failures. Do not make tests use live Netpulse requests.

Acceptance criteria:

- `pytest tests/ --asyncio-mode=auto` passes.
- The GitHub [`Test` workflow](.github/workflows/test.yml) passes on Python 3.14.
- No test uses real credentials or makes a live API request.

## Priority 2 — Run the exact repository validators

The repository already runs both required validators in [`.github/workflows/validate.yml`](.github/workflows/validate.yml):

- `hacs/action@main` with `category: integration`
- `home-assistant/actions/hassfest@master`

Run or trigger both workflows against the final commit. Review every warning, ignored check, and failure rather than assuming a green pytest run is sufficient.

Acceptance criteria:

- HACS validation passes with no ignored checks.
- Hassfest passes.
- The final commit is pushed before opening the HACS default-repository PR, so the checks reflect the exact submitted revision.

## Priority 3 — Review diagnostics privacy

Resolve a documentation/implementation mismatch before publishing another release, not a code change.

Current behavior in [`custom_components/the_gym_group/diagnostics.py`](custom_components/the_gym_group/diagnostics.py) redacts usernames, passwords, config-entry IDs, timestamps in the config-entry metadata, account UUIDs, instructor names, and visit gym names. It intentionally retains:

- Exact activity timestamps in `checkin_history`, `calendar_checkins`, and `calendar_classes` — the code comment and `tests/test_diagnostics.py::test_diagnostics_redacts_pii` both document this as deliberate, since timestamps/durations are the useful diagnostic signal.
- The configured gym name and gym location ID in busyness diagnostics — also deliberate; the code comment explains this is already shown unredacted as the HA device name, so redacting it in diagnostics would add no privacy.
- Historical busyness samples.

[`AGENTS.md`](AGENTS.md) (line 35) was out of sync with this: it stated diagnostics "must redact usernames, passwords, entry IDs, and timestamps," which didn't match the implementation. **Done:** reworded to describe what's actually redacted and to explicitly note that activity timestamps/durations and the configured gym location are intentionally retained.

No changes needed to `diagnostics.py`, its tests, the snapshot, or the README diagnostics wording — they already match the intended behavior.

Acceptance criteria:

- `AGENTS.md` accurately describes current diagnostics redaction behavior, with no reference to redacting timestamps or gym location.
- No username, password, account UUID, config-entry ID, instructor identity is exposed unintentionally (already satisfied — verify, don't re-implement).
- A diagnostics test fails if a newly introduced sensitive field is not redacted (already satisfied via the allowlisted `BUSYNESS_FIELDS` and `TO_REDACT`/`TO_REDACT_ACTIVITY` sets).

## Priority 4 — Harden malformed-payload handling

The API client validates top-level response types, but coordinator parsing still assumes several nested fields have the expected shape. Review and add tests for:

- Missing or non-list `checkIns`.
- Check-in entries that are not dictionaries.
- Missing, non-numeric, negative, or malformed `duration` values.
- Missing or malformed `timezone` and `checkInDate` values.
- Schedule entries without a dictionary `brief` object.
- Non-numeric `startDateTime`, `endDateTime`, `maxCapacity`, or `totalBooked` values.
- Duplicate or unstable calendar event UIDs.
- Events crossing daylight-saving transitions.

Primary files:

- [`custom_components/the_gym_group/coordinator.py`](custom_components/the_gym_group/coordinator.py)
- [`custom_components/the_gym_group/calendar.py`](custom_components/the_gym_group/calendar.py)
- [`tests/test_coordinator.py`](tests/test_coordinator.py)
- [`tests/test_calendar.py`](tests/test_calendar.py)

Use safe defaults or skip malformed records; one malformed visit or class must not make the entire integration unavailable unless the response itself is unusable.

Acceptance criteria:

- Malformed individual records are ignored or normalized safely.
- Valid records in the same response remain available.
- New tests cover each corrected failure mode.

## Priority 5 — Review the user-facing HACS experience

Review the README against the current released behavior and the HACS rendering experience:

- Keep the README clearly marked as an unofficial custom integration.
- Make the HACS installation path and manual fallback accurate.
- Confirm the stated minimum Home Assistant version in [`hacs.json`](hacs.json) and [`README.md`](README.md) is intentional.
- Ensure all configuration fields are documented, including advanced host/header fields and their security implications.
- Ensure reconfigure, reauth, diagnostics, removal, entity names, polling intervals, calendar behavior, and device triggers match the code.
- Keep the removal instructions; they satisfy an important documentation expectation.
- Check rendered links, images, tables, and YAML examples from the HACS README view.
- Consider replacing the custom repository installation instructions with a HACS “My” link once the repository has a stable public URL and release.

Files to review:

- [`README.md`](README.md)
- [`hacs.json`](hacs.json)
- [`custom_components/the_gym_group/manifest.json`](custom_components/the_gym_group/manifest.json)
- [`custom_components/the_gym_group/translations/en.json`](custom_components/the_gym_group/translations/en.json)

Acceptance criteria:

- A new user can install, configure, update, troubleshoot, and remove the integration using only the README.
- No README claim refers to an OptionsFlow or feature that does not exist.
- No README example contains a stale entity ID or unsupported service/action.

## Priority 6 — Review metadata, branding, and release contents

For HACS/custom integration submission, the local brand directory is valid starting with Home Assistant 2026.3. Keep and validate:

- [`custom_components/the_gym_group/brand/icon.png`](custom_components/the_gym_group/brand/icon.png)
- [`custom_components/the_gym_group/brand/icon@2x.png`](custom_components/the_gym_group/brand/icon@2x.png)
- [`custom_components/the_gym_group/brand/logo.png`](custom_components/the_gym_group/brand/logo.png)
- [`custom_components/the_gym_group/brand/logo@2x.png`](custom_components/the_gym_group/brand/logo@2x.png)

Check that:

- `manifest.json` contains the required HACS integration metadata: domain, name, codeowners, documentation, issue tracker, version, and config-flow/platform metadata.
- The manifest version and GitHub release version are identical.
- `hacs.json` contains at least `name`, with the intended country and minimum HA version.
- No credentials, PINs, cookies, APKs, diagnostics, or local environment files are in the release archive.
- The release asset/source archive contains the integration under `custom_components/the_gym_group/` and does not require repository-level test files at runtime.

Acceptance criteria:

- A clean checkout of the release tag installs successfully through HACS.
- The integration appears with the expected name and branding.
- The release contains no secret or unnecessary binary artifacts.

## Priority 7 — Final end-to-end smoke test

Test the exact release candidate in a disposable Home Assistant instance:

1. Install the candidate through HACS or copy only the integration directory.
2. Restart Home Assistant.
3. Add The Gym Group through the UI.
4. Verify successful login and account uniqueness behavior.
5. Verify the device, six sensors, and calendar are created.
6. Verify unavailable/recovery behavior with mocked or controlled API failures where practical.
7. Exercise reauth and reconfigure without creating duplicate devices or entities.
8. Download diagnostics and inspect the file manually for secrets and personal data.
9. Remove the config entry, restart, reinstall/update through HACS, and confirm the integration remains clean.

Acceptance criteria:

- Fresh installation works from the release artifact, not only from the development checkout.
- Existing entities retain their unique IDs across an update.
- Diagnostics are safe to attach to a public issue.

## Submission procedure

After all priorities pass:

1. Commit the focused changes using a concise Conventional Commit subject.
2. Push the branch and wait for both GitHub workflows to pass.
3. Create a full GitHub Release for the final version.
4. Confirm the release tag, manifest version, and HACS metadata are aligned.
5. Open a pull request to the HACS default repository's integration list, alphabetically positioned as required by HACS.
6. Complete the HACS PR template accurately and link the passing validation runs.
7. Monitor the PR for requested changes; HACS notes that default-repository review can take months.

## Deferred Home Assistant Core work

Do not block the HACS submission on these items:

- Extracting the Netpulse communication code into a reusable Python library.
- Reducing the feature set to a small initial Core PR.
- Replacing the GitHub documentation URL with a Home Assistant documentation page.
- Removing `issue_tracker` and custom-integration `version` from the Core manifest.
- Converting custom `translations/en.json` into Core's `strings.json` workflow.
- Moving brand images from the local integration directory to the Home Assistant brands repository.

