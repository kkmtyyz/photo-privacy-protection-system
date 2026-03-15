import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import * as url from 'node:url';
import { Runtime } from 'aws-cdk-lib/aws-lambda';
import * as lambda from 'aws-cdk-lib/aws-lambda-nodejs';

interface CustomResourcesProps {
  appsyncEndpointUrl: string;
}

export class CustomResources extends Construct {
  appsyncQueryProxyFunctionName: string;

  constructor(scope: Construct, id: string, props: CustomResourcesProps) {
    super(scope, id);

    // Lambda Function
    const appsyncQueryProxyFunction = new lambda.NodejsFunction(this, 'AppSyncQueryProxyFunction', {
      entry: url.fileURLToPath(new URL('appsync_query_proxy.ts', import.meta.url)),
      environment: {
        APPSYNC_ENDPOINT_URL: props.appsyncEndpointUrl,
      },
      runtime: Runtime.NODEJS_22_X,
      memorySize: 1024,
      timeout: cdk.Duration.seconds(60),
    });
    this.appsyncQueryProxyFunctionName = appsyncQueryProxyFunction.functionName;

    appsyncQueryProxyFunction.addToRolePolicy(
      new cdk.aws_iam.PolicyStatement({
        actions: ["appsync:GraphQL"],
        resources: ["*"]
      })
    );
  }
}
