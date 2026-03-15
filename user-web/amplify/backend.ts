import { defineBackend } from '@aws-amplify/backend';
import { auth } from './auth/resource';
import { data } from './data/resource';
import { storage } from './storage/resource';
import { CustomResources } from './custom/resource';
import * as ssm from 'aws-cdk-lib/aws-ssm';

const backend = defineBackend({
  auth,
  data,
  storage
});

// GraphQLのURL取得
const appsyncEndpointUrl = backend.data.resources.cfnResources.cfnGraphqlApi.attrGraphQlUrl;

// CustomResourceスタック作成
const customResourceStack = backend.createStack('CustomResources');
const customResources = new CustomResources(
  customResourceStack,
  'CustomResources',
  {
      appsyncEndpointUrl
  }
);

// Lambda関数名
new ssm.StringParameter(customResourceStack, 'AppsyncQueryProxyFunctionName', {
  parameterName: '/photo-protection/lambda/AppsyncQueryProxyFunctionName',
  stringValue: customResources.appsyncQueryProxyFunctionName,
});

// S3 バケット名
new ssm.StringParameter(customResourceStack, 'PhotoProtectionBucketName', {
  parameterName: '/photo-protection/s3/PhotoProtectionBucketName',
  stringValue: backend.storage.resources.bucket.bucketName,
});

