from typing import Optional

from github import Github


def open_pull_request(token: str, repo_full_name: str, branch: str, title: str, body: str) -> str:
    """Open a PR and return its URL."""
    gh = Github(token)
    repo = gh.get_repo(repo_full_name)
    pr = repo.create_pull(title=title, body=body, head=branch, base="main")
    return pr.html_url 