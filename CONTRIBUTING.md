# Contributing

## Conventional Commits

This is a specification designed to ensure that commit messages are human-readable. Developers using this convention use specific commit prefix text such as `fix:` for commits which fix a bug, and `feat:` for commits which add a new feature.

Have a look at the full specification [here](https://www.conventionalcommits.org/en/v1.0.0-beta.2/).

### Summary

As an open-source maintainer, squash feature branches onto master and write a standardized commit message while doing so.

The commit message should be structured as follows:

```git
<type>[optional scope]: <description>

[optional body]

[optional footer]
```

The commit contains the following structural elements, to communicate intent to the consumers of your library:

1. `fix:` a commit of the *type* `fix` patches a bug in your codebase (this correlates with `PATCH` in semantic versioning).
2. `feat:` a commit of the *type* `feat` introduces a new feature to the codebase (this correlates with `MINOR` in semantic versioning).
3. `BREAKING CHANGE:` a commit that has the text `BREAKING CHANGE:` at the beginning of its optional body or footer section introduces a breaking API change (correlating with `MAJOR` in semantic versioning). A breaking change can be part of commits of any *type*. e.g., a `fix:`, `feat:` & `chore:` *types* would all be valid, in addition to any other *type*.
4. Others: commit *types* other than `fix:` and `feat:` are allowed, for example @commitlint/config-conventional (based on the the Angular convention) recommends `chore:`, `docs:`, `style:`, `refactor:`, `perf:`, `test:`, and others. We also recommend improvement for commits that improve a current implementation without adding a new feature or fixing a bug. Notice these *types* are not mandated by the conventional commits specification, and have no implicit effect in semantic versioning (unless they include a BREAKING CHANGE, which is NOT recommended). A scope may be provided to a commit’s type, to provide additional contextual information and is contained within parenthesis, e.g., `feat(parser): add ability to parse arrays`.
