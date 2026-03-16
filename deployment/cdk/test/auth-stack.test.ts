import * as cdk from 'aws-cdk-lib';
import { Template, Match } from 'aws-cdk-lib/assertions';
import { AuthStack } from '../lib/auth-stack';

/**
 * Feature: amplify-serverless-migration, Property 1: Cognito 보안 설정 불변성
 *
 * For any CDK 스택 환경 설정(dev, prod 등)에서, 생성되는 Cognito User Pool은
 * 반드시 selfSignUpEnabled=false이고 AllowAdminCreateUserOnly=true여야 한다.
 *
 * Validates: Requirements 2.1, 2.2
 */
describe('Property 1: Cognito 보안 설정 불변성', () => {
  const environments = ['dev', 'prod'];

  environments.forEach((envName) => {
    describe(`환경: ${envName}`, () => {
      let template: Template;

      beforeAll(() => {
        const app = new cdk.App();
        const stack = new AuthStack(app, `TestAuthStack-${envName}`, { envName });
        template = Template.fromStack(stack);
      });

      test('AdminCreateUserConfig.AllowAdminCreateUserOnly가 true여야 한다', () => {
        template.hasResourceProperties('AWS::Cognito::UserPool', {
          AdminCreateUserConfig: {
            AllowAdminCreateUserOnly: true,
          },
        });
      });

      test('비밀번호 정책: 최소 8자, 대소문자, 숫자, 특수문자 필수', () => {
        template.hasResourceProperties('AWS::Cognito::UserPool', {
          Policies: {
            PasswordPolicy: Match.objectLike({
              MinimumLength: 8,
              RequireUppercase: true,
              RequireLowercase: true,
              RequireNumbers: true,
              RequireSymbols: true,
            }),
          },
        });
      });
    });
  });
});
