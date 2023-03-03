from aws_cdk import Duration, Size, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as tasks
from constructs import Construct


class FileUploader(Stack):
    partitioner_asset = "./partitioner/dist/partitioner.zip"
    uploader_asset = "./uploader/dist/uploader.zip"

    max_num_tasks = 10000

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        bucket = s3.Bucket(
            self,
            "Bucket",
            lifecycle_rules=[
                s3.LifecycleRule(
                    abort_incomplete_multipart_upload_after=Duration.days(1),
                    expiration=Duration.days(30),
                    transitions=[
                        s3.Transition(storage_class=s3.StorageClass.GLACIER, transition_after=Duration.days(7))
                    ],
                )
            ],
        )

        partitioner = lambda_.Function(
            self,
            "Partitioner",
            code=lambda_.Code.from_asset(self.partitioner_asset),
            handler="index.handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            memory_size=512,
            timeout=Duration.seconds(30),
        )

        uploader = lambda_.Function(
            self,
            "Uploader",
            code=lambda_.Code.from_asset(self.uploader_asset),
            handler="index.handler",
            runtime=lambda_.Runtime.PYTHON_3_9,
            memory_size=512,
            ephemeral_storage_size=Size.gibibytes(5),
            timeout=Duration.minutes(10),
        )

        bucket.grant_write(uploader)

        upload_success = sfn.Succeed(self, "Upload Success")
        upload_failure = sfn.Fail(self, "Upload Failure")

        partition_tasks = tasks.LambdaInvoke(
            self,
            "Partition Upload Tasks",
            lambda_function=partitioner,
            payload=sfn.TaskInput.from_object(
                {"URL.$": "$.URL", "SingleTaskSize.$": "$.SingleTaskSize", "Bucket": bucket.bucket_name}
            ),
            result_selector={
                "URL.$": "$.Payload.URL",
                "Bucket.$": "$.Payload.Bucket",
                "Key.$": "$.Payload.Key",
                "Tasks.$": "$.Payload.Tasks",
                "TasksLength.$": "States.ArrayLength($.Payload.Tasks)",
            },
        )

        partition_tasks.add_catch(upload_failure, errors=[sfn.Errors.ALL])

        initiate_multipart_upload = sfn.CustomState(
            self,
            "Initiate Multipart Upload",
            state_json={
                "Type": "Task",
                "Resource": f"arn:{self.partition}:states:::aws-sdk:s3:createMultipartUpload",
                "Parameters": {"Bucket.$": "$.Bucket", "Key.$": "$.Key"},
                "ResultPath": "$.MultipartUpload",
                "ResultSelector": {"UploadId.$": "$.UploadId"},
            },
        )

        abort_multipart_upload = sfn.CustomState(
            self,
            "Abort Multipart Upload",
            state_json={
                "Type": "Task",
                "Resource": f"arn:{self.partition}:states:::aws-sdk:s3:abortMultipartUpload",
                "Parameters": {
                    "Bucket.$": "$.Bucket",
                    "Key.$": "$.Key",
                    "UploadId.$": "$.MultipartUpload.UploadId",
                },
                "ResultPath": "$.AbortMultipartUpload",
            },
        )

        abort_multipart_upload.next(upload_failure)

        dispatch_tasks = sfn.CustomState(
            self,
            "Dispatch Upload Tasks",
            state_json={
                "Type": "Map",
                "MaxConcurrency": 100,
                "ItemsPath": "$.Tasks",
                "ItemSelector": {
                    "URL.$": "$.URL",
                    "Bucket.$": "$.Bucket",
                    "Key.$": "$.Key",
                    "Task.$": "$$.Map.Item.Value",
                    "MultipartUploadId.$": "$.MultipartUpload.UploadId",
                },
                "ResultPath": "$.UploadedParts",
                "Catch": [
                    {
                        "ErrorEquals": ["States.ALL"],
                        "Next": abort_multipart_upload.state_id,
                        "ResultPath": "$.Errors.DispatchUploadTasks",
                    }
                ],
                "ItemProcessor": {
                    "ProcessorConfig": {"Mode": "DISTRIBUTED", "ExecutionType": "STANDARD"},
                    "StartAt": "Upload File Part",
                    "States": {
                        "Upload File Part": {
                            "Type": "Task",
                            "Resource": f"arn:{self.partition}:states:::lambda:invoke",
                            "OutputPath": "$.Payload",
                            "Parameters": {
                                "Payload.$": "$",
                                "FunctionName": uploader.function_arn,
                            },
                            "Retry": [
                                {
                                    "ErrorEquals": [
                                        "Lambda.ServiceException",
                                        "Lambda.AWSLambdaException",
                                        "Lambda.SdkClientException",
                                        "Lambda.TooManyRequestsException",
                                    ],
                                    "IntervalSeconds": 2,
                                    "MaxAttempts": 3,
                                    "BackoffRate": 2,
                                },
                                {"ErrorEquals": [sfn.Errors.ALL], "MaxAttempts": 3},
                            ],
                            "End": True,
                        }
                    },
                },
            },
        )

        complete_multipart_upload = sfn.CustomState(
            self,
            "Complete Multipart Upload",
            state_json={
                "Type": "Task",
                "Resource": f"arn:{self.partition}:states:::aws-sdk:s3:completeMultipartUpload",
                "Parameters": {
                    "Bucket.$": "$.Bucket",
                    "Key.$": "$.Key",
                    "UploadId.$": "$.MultipartUpload.UploadId",
                    "MultipartUpload": {"Parts.$": "$.UploadedParts"},
                },
                "Catch": [
                    {
                        "ErrorEquals": ["S3.S3Exception"],
                        "Next": abort_multipart_upload.state_id,
                        "ResultPath": "$.Errors.CompleteMultipartUpload",
                    }
                ],
            },
        )

        state_machine = sfn.StateMachine(
            self,
            "StateMachine",
            definition=partition_tasks.next(
                sfn.Choice(self, "Verify The Number Of Tasks")
                .when(
                    sfn.Condition.or_(
                        sfn.Condition.number_greater_than("$.TasksLength", 0),
                        sfn.Condition.number_less_than_equals("$.TasksLength", self.max_num_tasks),
                    ),
                    initiate_multipart_upload.next(dispatch_tasks).next(complete_multipart_upload).next(upload_success),
                )
                .otherwise(upload_failure)
            ),
        )

        state_machine.role.attach_inline_policy(
            policy=iam.Policy(
                self,
                "DistributedMap",
                policy_name="AllowedDistributedMap",
                statements=[
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["states:StartExecution"],
                        resources=[state_machine.state_machine_arn],
                    ),
                    iam.PolicyStatement(
                        effect=iam.Effect.ALLOW,
                        actions=["states:DescribeExecution", "states:StopExecution"],
                        resources=[f"{state_machine.state_machine_arn}/*"],
                    ),
                ],
            )
        )

        uploader.grant_invoke(state_machine)
        bucket.grant_write(state_machine)
