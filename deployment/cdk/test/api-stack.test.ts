import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { AuthStack } from '../lib/auth-stack';
import { StorageStack } from '../lib/storage-stack';
import { ApiStack } from '../lib/api-stack';

/**
 * API 스택 CDK assertions 테스트
 *
 * Cognito Authorizer 적용, Lambda 메모리/타임아웃 설정,
 * API Gateway 스로틀링 설정, API 엔드포인트 존재 여부를 검증한다.
 *
 * Validates: Requirements 5.2, 5.5, 4.4, 4.5
 */
describe('API 스택 CDK assertions', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();

    const authStack = new AuthStack(app, 'TestAuthStack', { envName: 'dev' });
    const storageStack = new StorageStack(app, 'TestStorageStack', { envName: 'dev' });

    const apiStack = new ApiStack(app, 'TestApiStack', {
      envName: 'dev',
      envConfig: { lambdaMemory: 1024, apiThrottleRate: 10, apiThrottleBurst: 20 },
      userPool: authStack.userPool,
      userPoolClient: authStack.userPoolClient,
      videoBucket: storageStack.videoBucket,
      reportsTable: storageStack.reportsTable,
      settingsTable: storageStack.settingsTable,
      jobsTable: storageStack.jobsTable,
    });

    template = Template.fromStack(apiStack);
  });

  describe('Cognito Authorizer 적용 검증 (요구사항 5.2)', () => {
    test('Cognito User Pools Authorizer가 생성되어야 한다', () => {
      template.hasResourceProperties('AWS::ApiGateway::Authorizer', {
        Type: 'COGNITO_USER_POOLS',
        Name: Match.stringLikeRegexp('ad-compliance-dev-authorizer'),
      });
    });

    test('API 메서드에 COGNITO_USER_POOLS 인증이 적용되어야 한다', () => {
      const methods = template.findResources('AWS::ApiGateway::Method', {
        Properties: {
          HttpMethod: Match.anyValue(),
          AuthorizationType: 'COGNITO_USER_POOLS',
        },
      });
      // POST /upload-url, POST /analyze, GET /reports, GET /reports/{id} = 4개
      expect(Object.keys(methods).length).toBeGreaterThanOrEqual(4);
    });
  });

  describe('Lambda 메모리/타임아웃 설정 검증 (요구사항 4.4, 4.5)', () => {
    test('Dispatcher Lambda는 30초 타임아웃을 가져야 한다', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'ad-compliance-dev-dispatcher',
        Timeout: 30,
      });
    });
  });

  describe('스로틀링 설정 검증 (요구사항 5.5)', () => {
    test('API Gateway Stage에 스로틀링이 설정되어야 한다 (rate=10, burst=20)', () => {
      template.hasResourceProperties('AWS::ApiGateway::Stage', {
        MethodSettings: Match.arrayWith([
          Match.objectLike({
            ThrottlingRateLimit: 10,
            ThrottlingBurstLimit: 20,
          }),
        ]),
      });
    });
  });

  describe('API 엔드포인트 존재 검증 (요구사항 5.1)', () => {
    test('POST /upload-url 엔드포인트가 존재해야 한다', () => {
      // upload-url 리소스 확인
      template.hasResourceProperties('AWS::ApiGateway::Resource', {
        PathPart: 'upload-url',
      });
      // POST 메서드 확인
      template.hasResourceProperties('AWS::ApiGateway::Method', {
        HttpMethod: 'POST',
        AuthorizationType: 'COGNITO_USER_POOLS',
      });
    });

    test('POST /analyze 엔드포인트가 존재해야 한다', () => {
      template.hasResourceProperties('AWS::ApiGateway::Resource', {
        PathPart: 'analyze',
      });
    });

    test('GET /reports 엔드포인트가 존재해야 한다', () => {
      template.hasResourceProperties('AWS::ApiGateway::Resource', {
        PathPart: 'reports',
      });
    });

    test('GET /reports/{id} 엔드포인트가 존재해야 한다', () => {
      template.hasResourceProperties('AWS::ApiGateway::Resource', {
        PathPart: '{id}',
      });
    });
    test('GET /reports/{id} 엔드포인트가 존재해야 한다', () => {
      template.hasResourceProperties('AWS::ApiGateway::Resource', {
        PathPart: '{id}',
      });
    });

    test('GET /analyze/{jobId} 엔드포인트가 존재해야 한다', () => {
      template.hasResourceProperties('AWS::ApiGateway::Resource', {
        PathPart: '{jobId}',
      });
      // GET 메서드에 Cognito 인증 적용 확인
      const methods = template.findResources('AWS::ApiGateway::Method', {
        Properties: {
          HttpMethod: 'GET',
          AuthorizationType: 'COGNITO_USER_POOLS',
        },
      });
      expect(Object.keys(methods).length).toBeGreaterThanOrEqual(1);
    });
  });

  /**
   * Feature: async-analysis - Worker Lambda 설정 검증
   *
   * Validates: Requirements 6.2, 6.4, 6.6
   */
  describe('Worker Lambda 설정 검증 (요구사항 6.2, 6.6)', () => {
    test('Worker Lambda는 900초 타임아웃을 가져야 한다', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'ad-compliance-dev-worker',
        Timeout: 900,
      });
    });

    test('Worker Lambda는 1024MB 메모리를 가져야 한다', () => {
      template.hasResourceProperties('AWS::Lambda::Function', {
        FunctionName: 'ad-compliance-dev-worker',
        MemorySize: 1024,
      });
    });

    test('Worker Lambda는 sharedLayer와 ffmpegLayer 2개의 레이어를 가져야 한다', () => {
      const functions = template.findResources('AWS::Lambda::Function', {
        Properties: {
          FunctionName: 'ad-compliance-dev-worker',
        },
      });
      const workerKey = Object.keys(functions)[0];
      const layers = functions[workerKey].Properties.Layers;
      expect(layers).toHaveLength(2);
    });
  });

  /**
   * Feature: async-analysis - IAM 권한 검증
   *
   * Validates: Requirements 6.3, 6.4
   */
  describe('IAM 권한 검증 (요구사항 6.3, 6.4)', () => {
    test('Dispatcher는 lambda:InvokeFunction 권한을 가져야 한다', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: 'lambda:InvokeFunction',
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });

    test('Worker는 Jobs 테이블에 대한 dynamodb:GetItem, PutItem, UpdateItem, Query 권한을 가져야 한다', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: Match.arrayWith([
                'dynamodb:GetItem',
                'dynamodb:PutItem',
                'dynamodb:UpdateItem',
                'dynamodb:Query',
              ]),
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });

    test('Worker는 s3:GetObject 권한을 가져야 한다', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: 's3:GetObject',
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });

    test('Worker는 bedrock:InvokeModel 권한을 가져야 한다', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: 'bedrock:InvokeModel',
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });

    test('Worker는 Reports 테이블에 대한 dynamodb:PutItem 권한을 가져야 한다', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: 'dynamodb:PutItem',
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });

    test('Worker는 Settings 테이블에 대한 dynamodb:GetItem 권한을 가져야 한다', () => {
      template.hasResourceProperties('AWS::IAM::Policy', {
        PolicyDocument: {
          Statement: Match.arrayWith([
            Match.objectLike({
              Action: 'dynamodb:GetItem',
              Effect: 'Allow',
            }),
          ]),
        },
      });
    });
  });
});
