from aws_cdk import Stack
from aws_cdk.aws_codebuild import BuildEnvironment, ComputeType, LinuxBuildImage
from aws_cdk.aws_codecommit import Repository
from aws_cdk.pipelines import CodeBuildOptions, CodePipeline, CodePipelineSource, ShellStep
from constructs import Construct

from stacks.deployment_stage import DeploymentStage


class Pipeline(Stack):
    default_branch = "main"

    def __init__(self, scope: Construct, construct_id: str, repo_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repo = Repository.from_repository_name(self, "Repo", repository_name=repo_name)

        pipeline = CodePipeline(
            self,
            "Pipeline",
            pipeline_name=f"{repo_name}-pipeline",
            code_build_defaults=CodeBuildOptions(
                build_environment=BuildEnvironment(
                    build_image=LinuxBuildImage.STANDARD_6_0,
                    compute_type=ComputeType.SMALL,
                    privileged=True,
                )
            ),
            synth=ShellStep(
                "Synth",
                input=CodePipelineSource.code_commit(repository=repo, branch=self.default_branch),
                commands=["make ci-build"],
            ),
        )

        pipeline.add_stage(DeploymentStage(self, "Deploy", stack_name=repo_name, env=kwargs.get("env")))
