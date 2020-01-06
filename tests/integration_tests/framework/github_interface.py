from os import environ
from shutil import rmtree
from tempfile import mkdtemp

from git import Repo
from github import Github

DEFAULT_BLUEPRINT_REPO_ORG = 'cloudify-community'
DEFAULT_BLUEPRINT_REPO_NAME = 'blueprint-examples'


class GithubInterface(object):
    """Handles Creating Releases and uploading artifacts."""

    def __init__(self,
                 github_token=None,
                 github_orgname=DEFAULT_BLUEPRINT_REPO_ORG,
                 github_reponame=DEFAULT_BLUEPRINT_REPO_NAME,
                 file_path=None):
        self.github_token = github_token or environ.get(
            'GITHUB_TOKEN', 'RELEASE_BUILD_TOKEN')
        self.client = self.get_github_client()
        self.repo = self.get_github_repo(github_orgname, github_reponame)
        self._git_location = file_path or mkdtemp()

    @property
    def git_location(self):
        return self._git_location

    def get_github_client(self, token=None):
        token = token or self.github_token
        return Github(token)

    def get_github_repo(self, org, repo, client=None):
        client = client or self.client
        return client.get_repo(
            '{org}/{repo}'.format(
                org=org,
                repo=repo
            )
        )

    def clone(self, save_to=None, repo=None, tag_name=None):
        repo = repo or self.repo
        save_to = save_to or self.git_location
        Repo.clone_from(repo.clone_url, save_to)
        repo_from_path = Repo(save_to)
        if tag_name:
            repo_from_path.git.checkout(tag_name)
        for submodule in repo_from_path.submodules:
            submodule.update(init=True)

    def cleanup(self, file_path=None):
        file_path = file_path or self.git_location
        rmtree(file_path)
