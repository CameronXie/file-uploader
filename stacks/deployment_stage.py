from aws_cdk import Stage
from constructs import Construct

from stacks.file_uploader import FileUploader


class DeploymentStage(Stage):
    def __init__(self, scope: Construct, construct_id: str, stack_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        FileUploader(self, "FileUploader", stack_name=stack_name, env=kwargs.get("env"))
