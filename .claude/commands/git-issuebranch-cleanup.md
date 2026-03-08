Clean up remote branches that have already been merged into main via closed/merged pull requests.

1. Run `gh pr list --state merged --json number,headRefName,title` to get all merged PR branch names.
2. Run `git branch -r` to list all remote branches.
3. Cross-reference: identify remote branches whose names appear in the merged PR list. **Never delete `main`, `master`, or `HEAD` — skip them unconditionally regardless of PR state.**
4. For each stale branch, delete it from the remote with `git push origin --delete <branch-name>`.
5. Run `git remote prune origin` to clean up stale remote-tracking refs locally.
6. Report a summary of which branches were deleted and which (if any) were skipped.

**Usage:**
```
/git-issuebranch-cleanup
```
