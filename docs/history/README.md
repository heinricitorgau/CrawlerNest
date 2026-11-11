# History rewrite of 2026-11-11

On 2026-11-11 the repository's history was rewritten with `git filter-repo`, by decision of the repository owner.

**Why.** The v0.2 release dump (`docs/releases/v0.2-2026-snapshot/clawer-2026-09-04-release-freeze.dump`, earlier
`releases/v0.2-2026-snapshot/…`) had been committed with two `warehouse.app_user` rows in it: an email address and
its bcrypt password hash. The dump was replaced, in every commit that carried it, by one restored from it with
user-table data excluded. Nothing else was changed: every commit keeps its tree apart from that file, and its
message, author and date.

**What changed for you.**

- Every commit from the one that added the dump onwards has a new id. [`commit-map-2026-11-11.txt`](commit-map-2026-11-11.txt)
  lists `old new` for each, so a hash quoted in an old pull request, issue or note can still be found:

  ```bash
  grep '^4bd24cd' docs/history/commit-map-2026-11-11.txt
  ```

- A clone made before 2026-11-11 no longer shares history with `main`. Clone again rather than pull.
- Commit hashes quoted inside the repository (release manifests' `built_from_commit`, a few documents) were
  updated to the new ids on 2026-11-12.
- SSH signatures on 27 commits did not survive; a rewritten commit is a new object.

**What a rewrite cannot do.** Copies made before it (clones, forks, caches) still hold the original file, and
GitHub keeps pull-request refs that only GitHub Support can remove. Treat the old password hash as disclosed:
the account's password must be changed whatever else is done.
