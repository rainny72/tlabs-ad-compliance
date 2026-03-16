import * as cdk from 'aws-cdk-lib';
import * as amplify from 'aws-cdk-lib/aws-amplify';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as cognito from 'aws-cdk-lib/aws-cognito';
import { Construct } from 'constructs';

export interface FrontendStackProps extends cdk.StackProps {
  envName: string;
  api: apigateway.IRestApi;
  userPool: cognito.IUserPool;
  userPoolClient: cognito.IUserPoolClient;
}

export class FrontendStack extends cdk.Stack {
  public readonly amplifyApp: amplify.CfnApp;

  constructor(scope: Construct, id: string, props: FrontendStackProps) {
    super(scope, id, props);

    // API Gateway URL 구성
    const apiUrl = `https://${props.api.restApiId}.execute-api.${this.region}.amazonaws.com/${props.envName}`;

    // Amplify Hosting 앱 생성 (L1 CfnApp)
    this.amplifyApp = new amplify.CfnApp(this, 'AmplifyApp', {
      name: `ad-compliance-${props.envName}`,
      description: `Ad Compliance Analyzer Frontend (${props.envName})`,
      platform: 'WEB',
      buildSpec: [
        'version: 1',
        'frontend:',
        '  phases:',
        '    preBuild:',
        '      commands:',
        '        - npm ci',
        '    build:',
        '      commands:',
        '        - npm run build',
        '  artifacts:',
        '    baseDirectory: dist',
        '    files:',
        "      - '**/*'",
        '  cache:',
        '    paths:',
        "      - node_modules/**/*",
      ].join('\n'),
      environmentVariables: [
        { name: 'VITE_API_URL', value: apiUrl },
        { name: 'VITE_USER_POOL_ID', value: props.userPool.userPoolId },
        { name: 'VITE_USER_POOL_CLIENT_ID', value: props.userPoolClient.userPoolClientId },
        { name: 'VITE_AWS_REGION', value: this.region },
      ],
      // SPA 라우팅: 모든 경로를 index.html로 리다이렉트
      customRules: [
        {
          source: '</^[^.]+$|\\.(?!(css|gif|ico|jpg|js|png|txt|svg|woff|woff2|ttf|map|json)$)([^.]+$)/>',
          target: '/index.html',
          status: '200',
        },
      ],
    });

    // main 브랜치 설정
    const mainBranch = new amplify.CfnBranch(this, 'MainBranch', {
      appId: this.amplifyApp.attrAppId,
      branchName: 'main',
      stage: 'PRODUCTION',
      enableAutoBuild: true,
    });

    // CloudFormation Outputs
    new cdk.CfnOutput(this, 'AmplifyAppId', {
      value: this.amplifyApp.attrAppId,
      description: 'Amplify App ID',
    });

    new cdk.CfnOutput(this, 'AmplifyDefaultDomain', {
      value: this.amplifyApp.attrDefaultDomain,
      description: 'Amplify Default Domain',
    });

    new cdk.CfnOutput(this, 'AmplifyAppUrl', {
      value: `https://main.${this.amplifyApp.attrDefaultDomain}`,
      description: 'Amplify App URL (main branch)',
    });
  }
}
