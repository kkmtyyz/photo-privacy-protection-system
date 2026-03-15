import * as cdk from 'aws-cdk-lib/core';
import { Construct } from "constructs";
import { AppConfig } from "../config/app-config";
import * as apigateway from "aws-cdk-lib/aws-apigateway";
import * as integrations from "aws-cdk-lib/aws-apigatewayv2-integrations";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as s3n from "aws-cdk-lib/aws-s3-notifications";
import * as sqs from "aws-cdk-lib/aws-sqs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as lambdaPython from "@aws-cdk/aws-lambda-python-alpha";


interface MosaicProcessingProps {
  appConfig: AppConfig;
}

export class MosaicProcessing extends Construct {
  experiencePhotoProcessingTable: dynamodb.Table;
  experiencePhotoBucket: s3.Bucket;
  photoReviewQueue: sqs.Queue;
  experiencePhotoApi: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: MosaicProcessingProps) {
    super(scope, id);
    const appConfig = props.appConfig;

    /*
     * DynamoDB
     */
    // 写真処理情報テーブル
    this.experiencePhotoProcessingTable = new dynamodb.Table(this, "ExperiencePhotoProcessingTable", {
      partitionKey: {
        name: "photoId",
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
    // GSI
    // 運用に用いる。特定ステータスのアイテムを撮影日時でソートして取得するため
    this.experiencePhotoProcessingTable.addGlobalSecondaryIndex({
      indexName: "status-takenAt-index",
      partitionKey: {
        name: "status",
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: "takenAt",
        type: dynamodb.AttributeType.STRING,
      },
      projectionType: dynamodb.ProjectionType.ALL,
    });


    /*
     * S3
     */
    // 写真保存バケット
    this.experiencePhotoBucket = new s3.Bucket(this, "ExperiencePhotoBucket", {
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      encryption: s3.BucketEncryption.S3_MANAGED,
      enforceSSL: true,
      versioned: false,
      autoDeleteObjects: true,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      cors: [
        {
          allowedMethods: [s3.HttpMethods.PUT],
          allowedOrigins: ["*"],
          allowedHeaders: ["*"],
        },
      ],
    });


    /*
     * SQS
     */
    // 写真レビューDLQ
    const photoReviewDlq = new sqs.Queue(this, "PhotoReviewQueueDlq", {
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // 写真レビューキュー
    this.photoReviewQueue = new sqs.Queue(this, "PhotoReviewQueue", {
      visibilityTimeout: cdk.Duration.minutes(30), // 30分レビューされなかったら他のレビュワーに回す
      deadLetterQueue: {
        queue: photoReviewDlq,
        maxReceiveCount: 5,
      },
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });


    /*
     * Lambda Layer
     */
    // cdk synthでrequirements.txtのパッケージをダウンロードするためdockerの起動が必要
    const layer = new lambdaPython.PythonLayerVersion(this, "LambdaLayer", {
      entry: "resources/lambda/layer",
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_13],
    });


    /*
     * Lambda Function
     */
    // 写真アップロード関数
    const photoRegisterFunction = new lambda.Function(this, "PhotoRegisterFunction", {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset("resources/lambda/photo-register-function"),
      timeout: cdk.Duration.seconds(30),
      memorySize: 256,
      environment: {
        EXPERIENCE_PHOTO_PROCESSING_TABLE_NAME: this.experiencePhotoProcessingTable.tableName,
        EXPERIENCE_PHOTO_BUCKET_NAME: this.experiencePhotoBucket.bucketName,
        PRESIGNED_URL_EXPIRES_SECONDS: "300", // S3署名付きURLの期限
      },
    });

    this.experiencePhotoProcessingTable.grantReadWriteData(photoRegisterFunction);
    this.experiencePhotoBucket.grantPut(photoRegisterFunction);
    // S3署名付きurl生成用権限
    photoRegisterFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ["s3:PutObject"],
        resources: [`${this.experiencePhotoBucket.bucketArn}/original/*`],
      })
    );

    // 自動モザイク処理関数
    const autoMosaicFunction = new lambda.Function(this, "autoMosaicFunction", {
      runtime: lambda.Runtime.PYTHON_3_13,
      handler: "lambda_function.lambda_handler",
      code: lambda.Code.fromAsset("resources/lambda/auto-mosaic-function"),
      timeout: cdk.Duration.minutes(3),
      memorySize: 1024,
      layers: [layer],
      recursiveLoop: lambda.RecursiveLoop.TERMINATE, // トリガー元S3の異なるパスに書き戻すが、念のため無限ループ防止
      environment: {
        EXPERIENCE_PHOTO_PROCESSING_TABLE_NAME: this.experiencePhotoProcessingTable.tableName,
        PHOTO_REVIEW_QUEUE_URL: this.photoReviewQueue.queueUrl,
      },
    });

    this.experiencePhotoBucket.grantReadWrite(autoMosaicFunction);
    this.experiencePhotoProcessingTable.grantReadWriteData(autoMosaicFunction);
    this.photoReviewQueue.grantSendMessages(autoMosaicFunction);
    // Rekognition実行用権限
    autoMosaicFunction.addToRolePolicy(
      new iam.PolicyStatement({
        actions: [
          "rekognition:DetectFaces",
          "rekognition:DetectLabels",
        ],
        resources: ["*"],
      })
    );

    // S3イベント通知から自動モザイク処理Lambda関数をトリガー
    // original/ 以下のアップロードのみ処理
    this.experiencePhotoBucket.addEventNotification(
      s3.EventType.OBJECT_CREATED,
      new s3n.LambdaDestination(autoMosaicFunction),
      { prefix: "original/" }
    );


    /*
     * API Gateway
     * 検証なので今回はmTLS無し
     */
    this.experiencePhotoApi = new apigateway.RestApi(this, "ExperiencePhotoApi", {
      deployOptions: {
        stageName: "prod",
      },
    });
    
    // 体験フォト用リソース /experience-photos
    const experiencePhotosResource =
      this.experiencePhotoApi.root.addResource("experience-photos");
    
    // 体験フォト登録用メソッド POST /experience-photos
    experiencePhotosResource.addMethod(
      "POST",
      new apigateway.LambdaIntegration(photoRegisterFunction)
    );
  }
}
