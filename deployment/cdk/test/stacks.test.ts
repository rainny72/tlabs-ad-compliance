import * as cdk from 'aws-cdk-lib';
import { Template } from 'aws-cdk-lib/assertions';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as dynamodb from 'aws-cdk-lib/aws-dynamodb';
import { AuthStack } from '../lib/auth-stack';
import { StorageStack } from '../lib/storage-stack';
import { ApiStack } from '../lib/api-stack';
import { FrontendStack } from '../lib/frontend-stack';

describe('CDK Stack Synthesis', () => {
  let app: cdk.App;

  beforeEach(() => {
    app = new cdk.App();
  });

  test('AuthStack synthesizes without errors', () => {
    const stack = new AuthStack(app, 'TestAuthStack', {
      envName: 'dev',
    });

    // Verify synth succeeds and produces a valid template
    const template = Template.fromStack(stack);
    expect(template.toJSON()).toBeDefined();
  });

  test('StorageStack synthesizes without errors', () => {
    const stack = new StorageStack(app, 'TestStorageStack', {
      envName: 'dev',
    });

    const template = Template.fromStack(stack);
    expect(template.toJSON()).toBeDefined();
  });

  test('ApiStack synthesizes without errors', () => {
    // ApiStack requires cross-stack references; provide mock props
    const stack = new ApiStack(app, 'TestApiStack', {
      envName: 'dev',
      envConfig: { lambdaMemory: 1024, apiThrottleRate: 10, apiThrottleBurst: 20 },
      userPool: { userPoolId: 'mock-pool-id', userPoolArn: 'arn:aws:cognito-idp:us-east-1:123456789012:userpool/mock', stack: {} as any, env: {} as any, node: {} as any } as unknown as cognito.IUserPool,
      userPoolClient: { userPoolClientId: 'mock-client-id' } as unknown as cognito.IUserPoolClient,
      videoBucket: { bucketName: 'mock-bucket', bucketArn: 'arn:aws:s3:::mock-bucket' } as unknown as s3.IBucket,
      reportsTable: { tableName: 'mock-table', tableArn: 'arn:aws:dynamodb:us-east-1:123456789012:table/mock' } as unknown as dynamodb.ITable,
      settingsTable: { tableName: 'mock-settings-table', tableArn: 'arn:aws:dynamodb:us-east-1:123456789012:table/mock-settings' } as unknown as dynamodb.ITable,
      jobsTable: { tableName: 'mock-jobs-table', tableArn: 'arn:aws:dynamodb:us-east-1:123456789012:table/mock-jobs' } as unknown as dynamodb.ITable,
    });

    const template = Template.fromStack(stack);
    expect(template.toJSON()).toBeDefined();
  });

  test('FrontendStack synthesizes without errors', () => {
    const stack = new FrontendStack(app, 'TestFrontendStack', {
      envName: 'dev',
      api: { restApiId: 'mock-api-id' } as unknown as apigateway.IRestApi,
      userPool: { userPoolId: 'mock-pool-id' } as unknown as cognito.IUserPool,
      userPoolClient: { userPoolClientId: 'mock-client-id' } as unknown as cognito.IUserPoolClient,
    });

    const template = Template.fromStack(stack);
    expect(template.toJSON()).toBeDefined();
  });
});
