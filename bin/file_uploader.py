#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.file_uploader import FileUploader
from stacks.pipeline import PipelineStack
from stacks.source_code import SourceCode

app = cdk.App()
env = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("AWS_DEFAULT_REGION"))
repo_name = "file-uploader"

code = SourceCode(app, f"{repo_name}-source-code", repo_name, env=env)
pipeline = PipelineStack(app, f"{repo_name}-pipeline", repo_name, env=env)
pipeline.add_dependency(code)

FileUploader(app, "file-uploader", env=env)

app.synth()
