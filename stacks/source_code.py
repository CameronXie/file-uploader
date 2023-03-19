from aws_cdk import Stack
from aws_cdk.aws_codecommit import Repository
from constructs import Construct


class SourceCode(Stack):
    def __init__(self, scope: Construct, construct_id: str, repo_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        Repository(self, "Repo", repository_name=repo_name)
