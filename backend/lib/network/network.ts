import { Construct } from "constructs";
import { AppConfig } from "../config/app-config";
import { Stack } from "aws-cdk-lib";
import * as ec2 from "aws-cdk-lib/aws-ec2";

interface AppNetworkProps {
  appConfig: AppConfig;
}

export class AppNetwork extends Construct {
  vpc: ec2.Vpc;
  privateSubnets: ec2.ISubnet[];

  constructor(scope: Construct, id: string, props: AppNetworkProps) {
    super(scope, id);
    const appConfig = props.appConfig;
    const region = Stack.of(this).region;

    /*
     * VPC
     */
    // VPC
    this.vpc = new ec2.Vpc(this, "Vpc", {
      ipAddresses: ec2.IpAddresses.cidr(appConfig.vpcCidr),
      subnetConfiguration: [
        {
          cidrMask: 20,
          name: `${appConfig.appName}-private`,
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
      ],
      vpcName: `${appConfig.appName}-vpc`,
    });

    // Subnet
    this.privateSubnets = this.vpc.selectSubnets({
      subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
    }).subnets;


    /*
     * VPC Endpoint (Gateway)
     */
    // S3
    this.vpc.addGatewayEndpoint("S3Endpoint", {
      service: ec2.GatewayVpcEndpointAwsService.S3,
      subnets: [{ subnetType: ec2.SubnetType.PRIVATE_ISOLATED }],
    });

    // DynamoDB
    this.vpc.addGatewayEndpoint("DynamoEndpoint", {
      service: ec2.GatewayVpcEndpointAwsService.DYNAMODB,
      subnets: [{ subnetType: ec2.SubnetType.PRIVATE_ISOLATED }],
    });


    /*
     * VPC Endpoint (Interface)
     */
    // CloudWatch Logs
    this.vpc.addInterfaceEndpoint("CloudWatchLogsEndpoint", {
      service: ec2.InterfaceVpcEndpointAwsService.CLOUDWATCH_LOGS,
      subnets: {
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
      },
    });

    // SQS
    this.vpc.addInterfaceEndpoint("SqsEndpoint", {
      service: ec2.InterfaceVpcEndpointAwsService.SQS,
      subnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
    });
    
    // SES Email
    this.vpc.addInterfaceEndpoint("SesEmailEndpoint", {
      service: new ec2.InterfaceVpcEndpointService(
        `com.amazonaws.${region}.email`,
        443
      ),
      subnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
      privateDnsEnabled: true,
    });

    // STS
    this.vpc.addInterfaceEndpoint("StsEndpoint", {
      service: ec2.InterfaceVpcEndpointAwsService.STS,
      subnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
    });

    // SSM Parameter Store
    this.vpc.addInterfaceEndpoint("SsmEndpoint", {
      service: ec2.InterfaceVpcEndpointAwsService.SSM,
      subnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
    });

    // Lambda
    this.vpc.addInterfaceEndpoint("LambdaEndpoint", {
      service: ec2.InterfaceVpcEndpointAwsService.LAMBDA,
      subnets: { subnetType: ec2.SubnetType.PRIVATE_ISOLATED },
    });
  }
}
