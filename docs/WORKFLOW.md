# Git Workflow Guide

## **1. Branch Naming Convention**
Follow these branch naming conventions during project work:

- **feature/{issue-number}**: Adding a new feature
  - Example: `feature/1`
- **bugfix/{issue-number}**: Fixing a bug
  - Example: `bugfix/2`
- **docs/{description}**: Documentation updates
  - Example: `docs/update-api-reference`

---

## **2. Workflow Overview**
The basic workflow for tasks is as follows:

1. **Create a Git Issue**
   - When a new task is needed, create an issue on GitHub.
   - Include the purpose and details of the task in the issue.

2. **Create a Branch**
   - Create a branch according to the issue:
   ```bash
   git checkout develop
   git checkout -b feature/{issue-number}
   ```

3. **Commit and Push Changes**
   - After completing the task, create a commit with a descriptive message:
   ```bash
   git add .
   git commit -m "feat: {description of the work done}"
   git push origin feature/{issue-number}
   ```

---

## **3. Commit Message Convention**
Follow these commit message conventions:

- **feat**: Adding a new feature
- **fix**: Fixing a bug
- **docs**: Updating documentation
- **refactor**: Refactoring code without changing functionality
- **test**: Adding or updating tests
- **chore**: Build or configuration changes

**Examples**:
```bash
git commit -m "feat: Add support for DOCX file uploads"
git commit -m "fix: Correct file validation for .doc files"
```

---

## **4. Pull Request (PR) Guidelines**
- Create a PR to the `develop` branch once the task is completed.
- Write the PR title as a summary of the changes.
- Include the following in the PR description:
  1. Description of the work done
  2. Testing steps
  3. Related issue numbers (if applicable)
- Request a code review for the PR (optional).
- Merge the PR into `develop` if there are no conflicts.

---

## **5. Merge Policy**
- After approval, use the `Squash and Merge` strategy.
- Clean up the commit messages and merge as a single commit.