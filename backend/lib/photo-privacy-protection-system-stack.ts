import * as cdk from 'aws-cdk-lib/core';
import * as ssm from "aws-cdk-lib/aws-ssm";
import { Construct } from 'constructs';
import { AppConfig } from "./config/app-config";
import { AppNetwork } from "./network/network";
import { MosaicProcessing } from "./service/mosaic-processing";

export class PhotoPrivacyProtectionSystemStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const appConfig = new AppConfig(this, "AppConfig");
    const appNetwork = new AppNetwork(this, "AppNetwork", { appConfig });
    const mosaicProcessing = new MosaicProcessing(this, "MosaicProcessing", { appConfig });

    /*
     * Parameter Store
     */
    // dynamodb
    new ssm.StringParameter(this, 'ExperiencePhotoProcessingTableName', {
      parameterName: '/photo-protection/dynamodb/ExperiencePhotoProcessingTableName',
      stringValue: mosaicProcessing.experiencePhotoProcessingTable.tableName,
    });
    // s3
    new ssm.StringParameter(this, 'ExperiencePhotoBucketName', {
      parameterName: '/photo-protection/s3/ExperiencePhotoBucketName',
      stringValue: mosaicProcessing.experiencePhotoBucket.bucketName,
    });
    // sqs queue
    new ssm.StringParameter(this, 'PhotoReviewQueueURL', {
      parameterName: '/photo-protection/sqs/PhotoReviewQueueURL',
      stringValue: mosaicProcessing.photoReviewQueue.queueUrl,
    });

    /*
     * Outputs
     */
    new cdk.CfnOutput(this, "ApiUrl", {
      value: mosaicProcessing.experiencePhotoApi.url,
    });
  }
}
