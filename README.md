# Probing Stylistic Appropriation in Large Language Models (PSALM): An LLM-as-a-Judge Framework for Evaluating Copyright Infringement under EU Law.

<!-- [![Release](https://img.shields.io/github/v/release/nscharrenberg/psalm)](https://img.shields.io/github/v/release/nscharrenberg/psalm)
[![Build status](https://img.shields.io/github/actions/workflow/status/nscharrenberg/psalm/main.yml?branch=main)](https://github.com/nscharrenberg/psalm/actions/workflows/main.yml?query=branch%3Amain)
[![codecov](https://codecov.io/gh/nscharrenberg/psalm/branch/main/graph/badge.svg)](https://codecov.io/gh/nscharrenberg/psalm)
[![Commit activity](https://img.shields.io/github/commit-activity/m/nscharrenberg/psalm)](https://img.shields.io/github/commit-activity/m/nscharrenberg/psalm)
[![License](https://img.shields.io/github/license/nscharrenberg/psalm)](https://img.shields.io/github/license/nscharrenberg/psalm) -->



- **Git repository**: <https://codeberg.org/nscharrenberg/PSALM/>

## Getting started with your project

### 1. Create a New Repository

First, create a repository on GitHub with the same name as this project, and then run the following commands:

```bash
git init -b main
git add .
git commit -m "init commit"
git remote add origin git@codeberg.org/nscharrenberg/PSALM.git
git push -u origin main
```

### 2. Set Up Your Development Environment

Then, install the environment and the pre-commit hooks with

```bash
make install
```

This will also generate your `uv.lock` file

WARNING: May not work with Windows due to dependency limitations and issues.
WARNING: You may need to adjust the CUDA version dependency for torch in the `pyproject.toml` to the versions you are running.

### 3. Run the pre-commit hooks

Initially, the CI/CD pipeline might be failing due to formatting issues. To resolve those run:

```bash
uv run pre-commit run -a
```

### 4. Commit the changes

Lastly, commit the changes made by the two steps above to your repository.

```bash
git add .
git commit -m 'Fix formatting issues'
git push origin main
```

You are now ready to start development on your project!
