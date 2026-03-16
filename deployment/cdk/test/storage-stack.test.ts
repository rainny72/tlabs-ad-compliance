import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { StorageStack } from '../lib/storage-stack';

/**
 * Feature: amplify-serverless-migration, Property 2: S3 퍼블릭 액세스 차단 불변성
 *
 * For any CDK 스택 환경 설정(dev, prod 등)에서, 생성되는 S3 버킷은
 * 반드시 blockPublicAcls=true, blockPublicPolicy=true,
 * ignorePublicAcls=true, restrictPublicBuckets=true가 모두 설정되어야 한다.
 *
 * Validates: Requirements 3.1
 */
describe('Property 2: S3 퍼블릭 액세스 차단 불변성', () => {
  const environments = ['dev', 'prod'];

  environments.forEach((envName) => {
    describe(`환경: ${envName}`, () => {
      let template: Template;

      beforeAll(() => {
        const app = new cdk.App();
        const stack = new StorageStack(app, `TestStorageStack-${envName}`, { envName });
        template = Template.fromStack(stack);
      });

      test('S3 버킷의 PublicAccessBlockConfiguration이 모두 true여야 한다', () => {
        template.hasResourceProperties('AWS::S3::Bucket', {
          PublicAccessBlockConfiguration: {
            BlockPublicAcls: true,
            BlockPublicPolicy: true,
            IgnorePublicAcls: true,
            RestrictPublicBuckets: true,
          },
        });
      });
    });
  });
});

/**
 * Feature: async-analysis - Jobs 테이블 인프라 검증
 *
 * Jobs 테이블의 PK, 과금 모드, TTL, GSI 설정을 검증한다.
 *
 * Validates: Requirements 5.1, 5.2, 5.4
 */
describe('Jobs 테이블 인프라 검증', () => {
  let template: Template;

  beforeAll(() => {
    const app = new cdk.App();
    const stack = new StorageStack(app, 'TestStorageStack-jobs', { envName: 'dev' });
    template = Template.fromStack(stack);
  });

  test('Jobs 테이블의 PK는 job_id (String)이어야 한다 (요구사항 5.1)', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'ad-compliance-dev-jobs',
      KeySchema: Match.arrayWith([
        { AttributeName: 'job_id', KeyType: 'HASH' },
      ]),
      AttributeDefinitions: Match.arrayWith([
        { AttributeName: 'job_id', AttributeType: 'S' },
      ]),
    });
  });

  test('Jobs 테이블은 PAY_PER_REQUEST 과금 모드여야 한다 (요구사항 5.2)', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'ad-compliance-dev-jobs',
      BillingMode: 'PAY_PER_REQUEST',
    });
  });

  test('Jobs 테이블에 TTL 속성 ttl이 활성화되어야 한다', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'ad-compliance-dev-jobs',
      TimeToLiveSpecification: {
        AttributeName: 'ttl',
        Enabled: true,
      },
    });
  });

  test('Jobs 테이블에 user-jobs-index GSI가 있어야 한다 (PK=user_id, SK=created_at) (요구사항 5.4)', () => {
    template.hasResourceProperties('AWS::DynamoDB::Table', {
      TableName: 'ad-compliance-dev-jobs',
      GlobalSecondaryIndexes: Match.arrayWith([
        Match.objectLike({
          IndexName: 'user-jobs-index',
          KeySchema: Match.arrayWith([
            { AttributeName: 'user_id', KeyType: 'HASH' },
            { AttributeName: 'created_at', KeyType: 'RANGE' },
          ]),
        }),
      ]),
    });
  });
});
