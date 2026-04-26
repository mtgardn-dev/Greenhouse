# New PyCharm Project Git Checklist

Use this checklist when starting a new PyCharm project that will be connected to GitHub.

## 1. Create the project skeleton
- Create the PyCharm project.
- Enable Git in the project if PyCharm asks, or run `git init`.
- Create the initial folder/package structure.
- Add your entrypoint, such as `core/main.py` or `main.py`.
- Add any needed `__init__.py` files.

## 2. Add `.gitignore` immediately
- Create `.gitignore` before the first commit.
- Include common PyCharm and Python ignores:
  - `.idea/`
  - `.venv/`
  - `__pycache__/`
  - `*.pyc`
  - `.DS_Store`

Example:

```gitignore
.idea/
.venv/
__pycache__/
*.pyc
.DS_Store
```

## 3. Remove PyCharm files from the git index if needed
- If `.idea/` was already staged, remove it from tracking without deleting it locally:

```bash
git rm --cached -r .idea
```

## 4. Verify the working tree
- Check the status:

```bash
git status --short
```

- Confirm your source files and `.gitignore` are present.
- Confirm `.idea/` is not tracked.

## 5. Make the initial commit
- Stage the clean project files:

```bash
git add .gitignore core/__init__.py core/main.py tests/__init__.py config/__init__.py
```

- Commit:

```bash
git commit -m "Initial commit"
```

## 6. Add the GitHub remote with SSH
- Add the remote using SSH:

```bash
git remote add origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
```

- Verify the remote:

```bash
git remote -v
```

## 7. Push and set upstream
- Push the first commit:

```bash
git push -u origin main
```

- If your branch name is different, use that branch instead.

## 8. Start with a small TDD slice
- Extract one small, pure function from `main.py`.
- Write a failing test for it.
- Implement the smallest code that makes the test pass.
- Refactor if needed.

Good first slice for this greenhouse app:
- detect the date column
- parse and sort the CSV
- group daily temperature and humidity `min` / `mean` / `max`

## 9. Repeat the TDD loop
- Write one failing test.
- Implement the minimum code.
- Run the tests.
- Refactor.
- Commit the slice.

## 10. Quick pre-push sanity check
- `git status` is clean except for intended changes.
- `.idea/` is ignored.
- Tests pass.
- The remote uses SSH.
- The branch tracks `origin/main`.

## Common cleanup commands
- Remove `.idea/` from tracking if it gets staged:

```bash
git rm --cached -r .idea
```

- Fix the remote if needed:

```bash
git remote set-url origin git@github.com:YOUR_USERNAME/YOUR_REPO.git
```
