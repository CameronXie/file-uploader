from aws_cdk import Stack
from aws_cdk.aws_codebuild import BuildEnvironment, ComputeType, LinuxBuildImage, PipelineProject
from aws_cdk.aws_codecommit import Repository
from aws_cdk.aws_codepipeline import CfnPipeline
from aws_cdk.aws_iam import ArnPrincipal, CompositePrincipal, PolicyDocument, Role, ServicePrincipal
from aws_cdk.aws_s3 import Bucket
from constructs import Construct


class PipelineStack(Stack):
    default_branch = "main"
    deployment_project_name = "DeployProject"
    artifact_name = "file-uploader-pipeline-source-output"

    def __init__(self, scope: Construct, construct_id: str, repo_name: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        repo = Repository.from_repository_name(self, "Repo", repository_name=repo_name)
        bucket = Bucket(self, "ArtifactBucket", versioned=True)

        pipeline_role = Role(
            self,
            "PipelineRole",
            assumed_by=ServicePrincipal("codepipeline.amazonaws.com"),
        )

        deployment_role = Role(
            self,
            "DeploymentRole",
            assumed_by=CompositePrincipal(
                ServicePrincipal("codebuild.amazonaws.com"), ArnPrincipal(pipeline_role.role_arn)
            ),
            inline_policies={
                "DeploymentRolePolicy": PolicyDocument.from_json(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Effect": "Allow",
                                "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"],
                                "Resource": "*",
                            },
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "s3:Abort*",
                                    "s3:DeleteObject*",
                                    "s3:GetBucket*",
                                    "s3:GetObject*",
                                    "s3:List*",
                                    "s3:PutObject",
                                    "s3:PutObjectLegalHold",
                                    "s3:PutObjectRetention",
                                    "s3:PutObjectTagging",
                                    "s3:PutObjectVersionTagging",
                                ],
                                "Resource": [
                                    bucket.bucket_arn,
                                    f"{bucket.bucket_arn}/*",
                                    "arn:aws:s3:::cdk-*",
                                    "arn:aws:s3:::cdk-*/*",
                                ],
                            },
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "codecommit:CancelUploadArchive",
                                    "codecommit:GetBranch",
                                    "codecommit:GetCommit",
                                    "codecommit:GetUploadArchiveStatus",
                                    "codecommit:UploadArchive",
                                ],
                                "Resource": repo.repository_arn,
                            },
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "codebuild:BatchPutCodeCoverages",
                                    "codebuild:BatchPutTestCases",
                                    "codebuild:CreateReport",
                                    "codebuild:CreateReportGroup",
                                    "codebuild:UpdateReport",
                                ],
                                "Resource": "*",
                            },
                            {
                                "Effect": "Allow",
                                "Action": [
                                    "codebuild:BatchGetBuilds",
                                    "codebuild:StartBuild",
                                    "codebuild:StopBuild",
                                ],
                                "Resource": f"arn:aws:codebuild:{self.region}:{self.account}:project/{self.deployment_project_name}",  # noqa: E501
                            },
                            {
                                "Effect": "Allow",
                                "Action": ["iam:PassRole"],
                                "Resource": f"arn:aws:iam::{self.account}:role/cdk-*",
                            },
                            {"Effect": "Allow", "Action": ["cloudformation:*"], "Resource": "*"},
                            {"Effect": "Allow", "Action": ["ssm:*"], "Resource": "*"},
                        ],
                    }
                ),
            },
        )

        deployment_project = PipelineProject(
            self,
            "DeploymentProject",
            project_name=self.deployment_project_name,
            environment=BuildEnvironment(
                build_image=LinuxBuildImage.STANDARD_6_0,
                compute_type=ComputeType.SMALL,
                privileged=True,
            ),
            role=deployment_role,
        )

        CfnPipeline(
            self,
            "Pipeline",
            name=f"{repo_name}-pipeline",
            role_arn=pipeline_role.role_arn,
            artifact_store=CfnPipeline.ArtifactStoreProperty(type="S3", location=bucket.bucket_name),
            stages=[
                CfnPipeline.StageDeclarationProperty(
                    name="Source",
                    actions=[
                        CfnPipeline.ActionDeclarationProperty(
                            name="CodeCommit",
                            action_type_id=CfnPipeline.ActionTypeIdProperty(
                                category="Source", owner="AWS", provider="CodeCommit", version="1"
                            ),
                            configuration={
                                "RepositoryName": repo_name,
                                "BranchName": self.default_branch,
                                "PollForSourceChanges": False,
                            },
                            output_artifacts=[CfnPipeline.OutputArtifactProperty(name=self.artifact_name)],
                            role_arn=deployment_role.role_arn,
                            run_order=1,
                        )
                    ],
                ),
                CfnPipeline.StageDeclarationProperty(
                    name="Deployment",
                    actions=[
                        CfnPipeline.ActionDeclarationProperty(
                            name="Deploy",
                            action_type_id=CfnPipeline.ActionTypeIdProperty(
                                category="Build", owner="AWS", provider="CodeBuild", version="1"
                            ),
                            configuration={"ProjectName": deployment_project.project_name},
                            input_artifacts=[CfnPipeline.InputArtifactProperty(name=self.artifact_name)],
                            role_arn=deployment_role.role_arn,
                            run_order=1,
                        )
                    ],
                ),
            ],
        )
