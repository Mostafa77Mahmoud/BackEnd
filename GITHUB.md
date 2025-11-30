# Git Commands Reference

## Initial Setup

### Clone Repository
```bash
git clone <repository-url>
cd <repository-name>
```

### Configure Git User
```bash
git config user.name "Your Name"
git config user.email "your.email@example.com"
```

## Daily Workflow

### Check Status
```bash
git status
```

### Pull Latest Changes
```bash
git pull origin main
```

### Add Changes
```bash
# Add specific file
git add <filename>

# Add all changes
git add .

# Add all changes in a folder
git add app/
```

### Commit Changes
```bash
git commit -m "Your commit message"
```

### Push Changes
```bash
git push origin main
```

## Branch Operations

### Create New Branch
```bash
git checkout -b feature/new-feature
```

### Switch Branch
```bash
git checkout main
git checkout feature/new-feature
```

### List Branches
```bash
git branch        # local branches
git branch -a     # all branches including remote
```

### Merge Branch
```bash
git checkout main
git merge feature/new-feature
```

### Delete Branch
```bash
git branch -d feature/new-feature       # delete local
git push origin --delete feature/new-feature  # delete remote
```

## Common Scenarios

### Undo Last Commit (keep changes)
```bash
git reset --soft HEAD~1
```

### Discard Local Changes
```bash
git checkout -- <filename>
```

### View Commit History
```bash
git log
git log --oneline
```

### Stash Changes
```bash
git stash           # save changes
git stash pop       # restore changes
git stash list      # view stashed changes
```

## Remote Operations

### View Remote
```bash
git remote -v
```

### Add Remote
```bash
git remote add origin <repository-url>
```

### Fetch Remote Changes
```bash
git fetch origin
```

## Quick Reference

| Action | Command |
|--------|---------|
| Pull latest | `git pull origin main` |
| Push changes | `git push origin main` |
| Check status | `git status` |
| Add all files | `git add .` |
| Commit | `git commit -m "message"` |
| View history | `git log --oneline` |
