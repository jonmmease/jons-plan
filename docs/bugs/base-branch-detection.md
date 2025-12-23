# Bug: /jons-plan:new-review doesn't detect feature branch bases

## Summary

When running `/jons-plan:new-review` on a branch that was created from another feature branch (not main/master), the command only checks for `main` or `master` as the base branch. It doesn't detect the actual parent branch.

## Reproduction

1. Have a branch `feature-a` based on `master`
2. Create branch `feature-b` based on `feature-a`
3. Run `/jons-plan:new-review` on `feature-b`
4. **Expected:** Detects `feature-a` as the base (24 commits)
5. **Actual:** Uses `master` as base (142 commits, includes all of `feature-a`'s commits)

## Specific Case

- Branch: `jonmmease/chart-tests-with-hisc`
- Actual base: `gj/explore-integration-hisc-rest-of-the-fucking-owl`
- Detected base: `master`

The command used:
```bash
git rev-parse --verify main 2>/dev/null && echo "BASE=main" || echo "BASE=master"
```

This only checks main vs master, missing that the branch was actually based on another feature branch.

## Suggested Fix

Add heuristics to detect the likely base branch:

```bash
# Option 1: Check merge-base distance to candidate branches
for candidate in master main $(git branch -r --list 'origin/*' | head -20); do
  commits=$(git rev-list --count $candidate..HEAD 2>/dev/null || echo 999999)
  echo "$commits $candidate"
done | sort -n | head -5
# The branch with fewest commits is likely the base
```

```bash
# Option 2: Use git's reflog to find branch point
git reflog show --no-abbrev HEAD | grep 'branch:' | head -1
```

```bash
# Option 3: Present options to user when ambiguous
# If master shows 100+ commits but another branch shows <30, ask user
```

## Workaround

User can manually specify the base branch as an argument, or the command could prompt when it detects a large commit count that might indicate wrong base detection.

## Impact

- Generates much larger diffs than necessary
- Review tasks waste tokens analyzing unrelated commits
- PR description includes commits from parent branch

## Date

2024-12-23

## Resolution

**Status:** Fixed

**Approach:** Instead of using heuristics to auto-detect the base branch, we now:

1. Compute candidate base branches by finding ALL remote branches where HEAD is ahead
2. Sort candidates by commit distance (ascending) - lower count = more likely correct base
3. If only the default branch (main/master) is a candidate, use it silently
4. If multiple candidates exist, present ALL options to the user via `AskUserQuestion`
5. User selects the correct base branch, which is then used for the review diff

This avoids the fundamental problem: feature-off-feature scenarios have a valid merge-base with main/master (via the parent feature branch), so heuristic detection fails. Asking the user is more reliable.

**Files changed:**
- `commands/new-review.md` - Added candidate branch detection to pre-computed context, updated Step 1 decision logic

**Date resolved:** 2025-12-23
