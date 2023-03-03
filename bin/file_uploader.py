#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.file_uploader import FileUploader

app = cdk.App()
env = cdk.Environment(account=os.getenv("CDK_DEFAULT_ACCOUNT"), region=os.getenv("AWS_DEFAULT_REGION"))
FileUploader(app, "FileUploader", env=env)

app.synth()
