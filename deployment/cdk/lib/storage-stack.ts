import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

export interface StorageStackProps extends cdk.StackProps {
  envName: string;
}

export class StorageStack extends cdk.Stack {
  public readonly videoBucket: s3.Bucket;
  public readonly reportsTable: dynamodb.Table;
  public readonly settingsTable: dynamodb.Table;
  public readonly jobsTable: dynamodb.Table;

  constructor(scope: Construct, id: string, props: StorageStackProps) {
    super(scope, id, props);

    // S3 Video Bucket - 모든 퍼블릭 액세스 차단, SSE-S3 암호화
    this.videoBucket = new s3.Bucket(this, 'VideoBucket', {
      bucketName: `ad-compliance-${props.envName}-videos-${this.account}`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      enforceSSL: true,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      lifecycleRules: [
        {
          id: 'expire-uploads-30d',
          prefix: 'uploads/',
          expiration: cdk.Duration.days(30),
        },
      ],
      cors: [
        {
          allowedOrigins: ['*'],
          allowedMethods: [s3.HttpMethods.PUT],
          allowedHeaders: ['*'],
          maxAge: 3600,
        },
      ],
    });

    // Bedrock 서비스가 S3에서 비디오를 직접 읽을 수 있도록 허용
    this.videoBucket.addToResourcePolicy(new iam.PolicyStatement({
      sid: 'AllowBedrockReadAccess',
      effect: iam.Effect.ALLOW,
      principals: [new iam.ServicePrincipal('bedrock.amazonaws.com')],
      actions: ['s3:GetObject'],
      resources: [`${this.videoBucket.bucketArn}/uploads/*`],
      conditions: {
        StringEquals: {
          'aws:SourceAccount': this.account,
        },
      },
    }));

    // DynamoDB ComplianceReports 테이블 - On-Demand 용량
    this.reportsTable = new dynamodb.Table(this, 'ReportsTable', {
      tableName: `ad-compliance-${props.envName}-reports`,
      partitionKey: {
        name: 'user_id',
        type: dynamodb.AttributeType.STRING,
      },
      sortKey: {
        name: 'analyzed_at',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
      pointInTimeRecoverySpecification: {
        pointInTimeRecoveryEnabled: true,
      },
    });

    // CloudFormation Outputs
    new cdk.CfnOutput(this, 'VideoBucketName', {
      value: this.videoBucket.bucketName,
      description: 'S3 Video Bucket Name',
    });

    new cdk.CfnOutput(this, 'ReportsTableName', {
      value: this.reportsTable.tableName,
      description: 'DynamoDB Reports Table Name',
    });

    // DynamoDB UserSettings 테이블 - backend 선택, API Key 저장
    this.settingsTable = new dynamodb.Table(this, 'SettingsTable', {
      tableName: `ad-compliance-${props.envName}-settings`,
      partitionKey: {
        name: 'user_id',
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    new cdk.CfnOutput(this, 'SettingsTableName', {
      value: this.settingsTable.tableName,
      description: 'DynamoDB Settings Table Name',
    });

    // DynamoDB Jobs 테이블 - 비동기 분석 작업 상태 관리
    this.jobsTable = new dynamodb.Table(this, 'JobsTable', {
      tableName: `ad-compliance-${props.envName}-jobs`,
      partitionKey: { name: 'job_id', type: dynamodb.AttributeType.STRING },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
      timeToLiveAttribute: 'ttl',
    });

    // GSI: user_id + created_at (사용자별 작업 목록 조회)
    this.jobsTable.addGlobalSecondaryIndex({
      indexName: 'user-jobs-index',
      partitionKey: { name: 'user_id', type: dynamodb.AttributeType.STRING },
      sortKey: { name: 'created_at', type: dynamodb.AttributeType.STRING },
    });

    new cdk.CfnOutput(this, 'JobsTableName', {
      value: this.jobsTable.tableName,
      description: 'DynamoDB Jobs Table Name',
    });
  }
}
