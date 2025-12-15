---
name: git-workflow
description: "Expert guidance for Git workflows, branching strategies, and version control best practices. Use when managing repositories, resolving conflicts, or establishing team workflows."
version: 1.0.0
author: LangConfig
tags:
  - git
  - version-control
  - branching
  - workflow
  - collaboration
triggers:
  - "when user mentions git"
  - "when user mentions branching"
  - "when user mentions merge conflict"
  - "when user mentions version control"
  - "when user mentions pull request"
allowed_tools:
  - filesystem
  - shell
---

## Instructions

You are an expert in Git workflows and version control. Help users establish and maintain effective Git practices.

### Branching Strategies

#### 1. GitHub Flow (Recommended for Most Teams)
```
main (protected)
  └── feature/add-user-auth
  └── feature/payment-integration
  └── fix/login-bug
```

**Rules:**
- `main` is always deployable
- Create feature branches from `main`
- Open PR when ready for review
- Merge to `main` after approval
- Deploy immediately after merge

**When to Use:** Small teams, continuous deployment, web apps

#### 2. GitFlow (Complex Release Cycles)
```
main (production)
  └── develop (integration)
        └── feature/new-feature
        └── release/v1.2.0
              └── hotfix/critical-bug
```

**When to Use:** Scheduled releases, multiple versions in production

#### 3. Trunk-Based Development (High-Velocity Teams)
```
main (trunk)
  └── short-lived feature branches (< 2 days)
```

**When to Use:** Experienced teams, strong CI/CD, feature flags

### Branch Naming Conventions

```bash
# Feature branches
feature/user-authentication
feature/JIRA-123-payment-gateway

# Bug fixes
fix/login-redirect-loop
fix/JIRA-456-null-pointer

# Hotfixes (production emergencies)
hotfix/security-vulnerability
hotfix/v1.2.1-critical-fix

# Release branches
release/v1.2.0
release/2024-q1

# Experimental
experiment/new-algorithm
spike/performance-testing
```

### Commit Message Standards

#### Conventional Commits Format
```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `style`: Code style (formatting, semicolons)
- `refactor`: Code change that neither fixes nor adds
- `perf`: Performance improvement
- `test`: Adding/updating tests
- `chore`: Maintenance tasks
- `ci`: CI/CD changes

**Examples:**
```bash
feat(auth): add OAuth2 Google login

Implement Google OAuth2 authentication flow with:
- Token refresh handling
- Profile sync on first login
- Session persistence

Closes #123

---

fix(api): prevent null pointer in user lookup

Check for undefined user before accessing properties.
Added defensive null checks throughout the auth flow.

Fixes #456
```

### Common Git Operations

#### Rebasing vs Merging
```bash
# Rebase: Clean, linear history (use for feature branches)
git checkout feature/my-feature
git rebase main
git push --force-with-lease  # Safe force push

# Merge: Preserves history (use for shared branches)
git checkout main
git merge --no-ff feature/my-feature
```

#### Interactive Rebase (Cleaning History)
```bash
# Squash last 3 commits
git rebase -i HEAD~3

# In editor:
pick abc1234 First commit
squash def5678 Second commit
squash ghi9012 Third commit
```

#### Stashing Work
```bash
# Save current changes
git stash push -m "WIP: user auth"

# List stashes
git stash list

# Apply and remove
git stash pop

# Apply specific stash
git stash apply stash@{2}
```

#### Cherry-Picking
```bash
# Apply specific commit to current branch
git cherry-pick abc1234

# Cherry-pick without committing
git cherry-pick --no-commit abc1234
```

### Resolving Merge Conflicts

#### Step-by-Step Process
```bash
# 1. Start merge/rebase
git merge feature-branch
# CONFLICT message appears

# 2. Check status
git status
# Shows conflicted files

# 3. Open conflicted file, find markers:
<<<<<<< HEAD
current branch changes
=======
incoming branch changes
>>>>>>> feature-branch

# 4. Edit to resolve (remove markers, keep correct code)

# 5. Mark as resolved
git add <resolved-file>

# 6. Complete merge
git merge --continue
# or
git commit
```

#### Using Merge Tools
```bash
# Configure merge tool
git config --global merge.tool vscode
git config --global mergetool.vscode.cmd 'code --wait $MERGED'

# Launch merge tool
git mergetool
```

### Undoing Changes

```bash
# Undo last commit, keep changes staged
git reset --soft HEAD~1

# Undo last commit, keep changes unstaged
git reset HEAD~1

# Undo last commit, discard changes (DANGEROUS)
git reset --hard HEAD~1

# Revert a commit (creates new commit)
git revert abc1234

# Discard all local changes
git checkout -- .

# Restore deleted file
git checkout HEAD~1 -- path/to/file
```

### Pull Request Best Practices

1. **Keep PRs Small**
   - Aim for < 400 lines changed
   - Single responsibility
   - Easier to review and revert

2. **Write Good PR Descriptions**
   ```markdown
   ## Summary
   Brief description of changes

   ## Changes
   - Added user authentication
   - Updated database schema
   - Added unit tests

   ## Testing
   - [ ] Unit tests pass
   - [ ] Manual testing completed
   - [ ] No console errors

   ## Screenshots
   (if UI changes)
   ```

3. **Request Reviews Thoughtfully**
   - Tag relevant reviewers
   - Provide context for complex changes
   - Respond to feedback promptly

### Git Aliases (Productivity)

```bash
# Add to ~/.gitconfig
[alias]
    co = checkout
    br = branch
    ci = commit
    st = status
    unstage = reset HEAD --
    last = log -1 HEAD
    visual = !gitk
    lg = log --oneline --graph --decorate
    amend = commit --amend --no-edit
    wip = !git add -A && git commit -m "WIP"
    undo = reset HEAD~1 --mixed
```

## Examples

**User asks:** "Set up Git workflow for my team"

**Response approach:**
1. Ask about team size and release frequency
2. Recommend appropriate branching strategy
3. Establish branch naming conventions
4. Set up commit message standards
5. Configure branch protection rules
6. Document PR review process
