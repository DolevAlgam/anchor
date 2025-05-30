from pathlib import Path
from typing import Optional

from git import Repo


def clone_repo(url: str, dest: str, branch: Optional[str] = None) -> Repo:
    repo = Repo.clone_from(url, dest)
    if branch:
        repo.git.checkout(branch, b=True)
    return repo


class GitRepo:
    """Wrapper around git.Repo with helper shortcuts."""

    def __init__(self, repo: Repo):
        self.repo = repo

    @classmethod
    def clone(cls, url: str, dest: str, branch: Optional[str] = None) -> "GitRepo":
        return cls(clone_repo(url, dest, branch))

    def commit_all(self, msg: str):
        self.repo.git.add(all=True)
        if self.repo.is_dirty():
            self.repo.index.commit(msg)

    def push(self, remote: str = "origin", branch: str = None):
        branch = branch or self.repo.active_branch.name
        self.repo.remote(remote).push(branch)

    @property
    def path(self) -> Path:
        return Path(self.repo.working_tree_dir) 