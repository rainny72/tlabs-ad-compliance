import * as cdk from 'aws-cdk-lib';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { Construct } from 'constructs';
import * as path from 'path';

export interface ApiStackProps extends cdk.StackProps {
  envName: string;
  envConfig: Record<string, unknown>;
  userPool: cognito.IUserPool;
  userPoolClient: cognito.IUserPoolClient;
  videoBucket: s3.IBucket;
  reportsTable: dynamodb.ITable;
  settingsTable: dynamodb.ITable;
  jobsTable: dynamodb.ITable;
}

export class ApiStack extends cdk.Stack {
  public readonly api: apigateway.RestApi;

  constructor(scope: Construct, id: string, props: ApiStackProps) {
    super(scope, id, props);

    const lambdaDir = path.join(__dirname, '..', '..', 'lambda');

    // Shared Lambda Layer (core/, shared/, prompts/)
    const sharedLayer = new lambda.LayerVersion(this, 'SharedLayer', {
      code: lambda.Code.fromAsset(path.join(lambdaDir, 'shared_layer')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      description: 'Shared layer with core, shared, and prompts modules',
    });

    // FFmpeg Layer (static binary for video preprocessing)
    const ffmpegLayer = new lambda.LayerVersion(this, 'FfmpegLayer', {
      code: lambda.Code.fromAsset(path.join(lambdaDir, 'ffmpeg_layer')),
      compatibleRuntimes: [lambda.Runtime.PYTHON_3_12],
      description: 'FFmpeg static binary for video stream cleanup',
    });

    // --- Upload Lambda ---
    const uploadFn = new lambda.Function(this, 'UploadFunction', {
      functionName: `ad-compliance-${props.envName}-upload`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      code: lambda.Code.fromAsset(path.join(lambdaDir, 'upload')),
      layers: [sharedLayer],
      environment: {
        VIDEO_BUCKET: props.videoBucket.bucketName,
      },
    });

    // Upload Lambda IAM: S3 PutObject only
    uploadFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['s3:PutObject'],
      resources: [`${props.videoBucket.bucketArn}/*`],
    }));

    // --- Dispatcher Lambda (30s) ---
    const dispatcherFn = new lambda.Function(this, 'DispatcherFunction', {
      functionName: `ad-compliance-${props.envName}-dispatcher`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'dispatcher.handler',
      code: lambda.Code.fromAsset(path.join(lambdaDir, 'analyze')),
      layers: [sharedLayer],
      timeout: cdk.Duration.seconds(30),
      environment: {
        VIDEO_BUCKET: props.videoBucket.bucketName,
        JOBS_TABLE: props.jobsTable.tableName,
      },
    });

    // Dispatcher Lambda IAM: Jobs 테이블 쓰기 권한
    dispatcherFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['dynamodb:PutItem', 'dynamodb:GetItem', 'dynamodb:UpdateItem'],
      resources: [props.jobsTable.tableArn],
    }));

    // --- Worker Lambda (900s, 1024MB) ---
    const workerFn = new lambda.Function(this, 'WorkerFunction', {
      functionName: `ad-compliance-${props.envName}-worker`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'worker.handler',
      code: lambda.Code.fromAsset(path.join(lambdaDir, 'analyze')),
      layers: [sharedLayer, ffmpegLayer],
      memorySize: 1024,
      timeout: cdk.Duration.seconds(900),
      environment: {
        JOBS_TABLE: props.jobsTable.tableName,
        VIDEO_BUCKET: props.videoBucket.bucketName,
        REPORTS_TABLE: props.reportsTable.tableName,
        SETTINGS_TABLE: props.settingsTable.tableName,
        BEDROCK_REGION: 'ap-northeast-2',
        ACCOUNT_ID: this.account,
      },
    });

    // Worker Lambda IAM: Jobs 테이블 읽기/쓰기 권한
    workerFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['dynamodb:GetItem', 'dynamodb:PutItem', 'dynamodb:UpdateItem', 'dynamodb:Query'],
      resources: [props.jobsTable.tableArn],
    }));

    // Worker Lambda IAM: S3 읽기 권한
    workerFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['s3:GetObject'],
      resources: [`${props.videoBucket.bucketArn}/*`],
    }));

    // Worker Lambda IAM: Bedrock InvokeModel 권한
    // foundation-model ARN은 account ID가 없는 형식 (arn:aws:bedrock:REGION::foundation-model/*)
    workerFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['bedrock:InvokeModel'],
      resources: [
        cdk.Arn.format({
          service: 'bedrock',
          resource: 'inference-profile',
          resourceName: '*',
          account: '',
        }, this),
        cdk.Arn.format({
          service: 'bedrock',
          resource: 'foundation-model',
          resourceName: '*',
          account: '',
        }, this),
      ],
    }));

    // Worker Lambda IAM: Reports 테이블 쓰기 권한
    workerFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['dynamodb:PutItem'],
      resources: [props.reportsTable.tableArn],
    }));

    // Worker Lambda IAM: Settings 테이블 읽기 권한
    workerFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['dynamodb:GetItem'],
      resources: [props.settingsTable.tableArn],
    }));

    // Dispatcher Lambda IAM: Worker Lambda 비동기 호출 권한
    dispatcherFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['lambda:InvokeFunction'],
      resources: [workerFn.functionArn],
    }));

    // Dispatcher 환경 변수에 Worker 함수 이름 참조 업데이트
    dispatcherFn.addEnvironment('WORKER_FUNCTION_NAME', workerFn.functionName);

    // --- Reports Lambda ---
    const reportsFn = new lambda.Function(this, 'ReportsFunction', {
      functionName: `ad-compliance-${props.envName}-reports`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      code: lambda.Code.fromAsset(path.join(lambdaDir, 'reports')),
      layers: [sharedLayer],
      environment: {
        REPORTS_TABLE: props.reportsTable.tableName,
      },
    });

    // Reports Lambda IAM: DynamoDB Query, GetItem
    reportsFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['dynamodb:Query', 'dynamodb:GetItem'],
      resources: [props.reportsTable.tableArn],
    }));

    // --- Settings Lambda ---
    const settingsFn = new lambda.Function(this, 'SettingsFunction', {
      functionName: `ad-compliance-${props.envName}-settings`,
      runtime: lambda.Runtime.PYTHON_3_12,
      handler: 'handler.handler',
      code: lambda.Code.fromAsset(path.join(lambdaDir, 'settings')),
      environment: {
        SETTINGS_TABLE: props.settingsTable.tableName,
      },
    });

    settingsFn.addToRolePolicy(new iam.PolicyStatement({
      actions: ['dynamodb:GetItem', 'dynamodb:PutItem'],
      resources: [props.settingsTable.tableArn],
    }));

    // --- API Gateway REST API ---
    this.api = new apigateway.RestApi(this, 'Api', {
      restApiName: `ad-compliance-${props.envName}-api`,
      description: 'Ad Compliance Analyzer REST API',
      deployOptions: {
        stageName: props.envName,
        throttlingRateLimit: (props.envConfig.apiThrottleRate as number) || 10,
        throttlingBurstLimit: (props.envConfig.apiThrottleBurst as number) || 20,
      },
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS,
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'Authorization',
          'X-Amz-Date',
          'X-Api-Key',
          'X-Amz-Security-Token',
        ],
      },
    });

    // Gateway Responses - Lambda 에러 시에도 CORS 헤더 포함
    this.api.addGatewayResponse('Default4XX', {
      type: apigateway.ResponseType.DEFAULT_4XX,
      responseHeaders: {
        'Access-Control-Allow-Origin': "'*'",
        'Access-Control-Allow-Headers': "'Content-Type,Authorization'",
      },
    });

    this.api.addGatewayResponse('Default5XX', {
      type: apigateway.ResponseType.DEFAULT_5XX,
      responseHeaders: {
        'Access-Control-Allow-Origin': "'*'",
        'Access-Control-Allow-Headers': "'Content-Type,Authorization'",
      },
    });

    // Cognito Authorizer
    const authorizer = new apigateway.CognitoUserPoolsAuthorizer(this, 'CognitoAuthorizer', {
      cognitoUserPools: [props.userPool],
      authorizerName: `ad-compliance-${props.envName}-authorizer`,
    });

    const authMethodOptions: apigateway.MethodOptions = {
      authorizer,
      authorizationType: apigateway.AuthorizationType.COGNITO,
    };

    // POST /upload-url
    const uploadUrlResource = this.api.root.addResource('upload-url');
    uploadUrlResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(uploadFn),
      authMethodOptions,
    );

    // POST /analyze
    const analyzeResource = this.api.root.addResource('analyze');
    analyzeResource.addMethod(
      'POST',
      new apigateway.LambdaIntegration(dispatcherFn),
      authMethodOptions,
    );

    // GET /analyze/{jobId}
    const analyzeJobResource = analyzeResource.addResource('{jobId}');
    analyzeJobResource.addMethod(
      'GET',
      new apigateway.LambdaIntegration(dispatcherFn),
      authMethodOptions,
    );

    // GET /reports
    const reportsResource = this.api.root.addResource('reports');
    reportsResource.addMethod(
      'GET',
      new apigateway.LambdaIntegration(reportsFn),
      authMethodOptions,
    );

    // GET /reports/{id}
    const reportByIdResource = reportsResource.addResource('{id}');
    reportByIdResource.addMethod(
      'GET',
      new apigateway.LambdaIntegration(reportsFn),
      authMethodOptions,
    );

    // GET /settings, PUT /settings
    const settingsResource = this.api.root.addResource('settings');
    settingsResource.addMethod(
      'GET',
      new apigateway.LambdaIntegration(settingsFn),
      authMethodOptions,
    );
    settingsResource.addMethod(
      'PUT',
      new apigateway.LambdaIntegration(settingsFn),
      authMethodOptions,
    );

    // CloudFormation Outputs
    new cdk.CfnOutput(this, 'ApiUrl', {
      value: this.api.url,
      description: 'API Gateway URL',
    });

    new cdk.CfnOutput(this, 'ApiId', {
      value: this.api.restApiId,
      description: 'API Gateway REST API ID',
    });
  }
}
