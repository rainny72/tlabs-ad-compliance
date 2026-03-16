#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { AuthStack } from '../lib/auth-stack';
import { StorageStack } from '../lib/storage-stack';
import { ApiStack } from '../lib/api-stack';
import { FrontendStack } from '../lib/frontend-stack';

const app = new cdk.App();

// Resolve environment from CDK context: -c env=dev|prod
const envName = app.node.tryGetContext('env') || 'dev';
const envConfig = app.node.tryGetContext(envName);

if (!envConfig) {
  throw new Error(
    `Environment "${envName}" not found in cdk.json context. Use -c env=dev or -c env=prod`,
  );
}

const awsEnv: cdk.Environment = {
  account: envConfig.account,
  region: envConfig.region,
};

const stackPrefix = `AdCompliance-${envName}`;

const authStack = new AuthStack(app, `${stackPrefix}-Auth`, {
  env: awsEnv,
  envName,
});

const storageStack = new StorageStack(app, `${stackPrefix}-Storage`, {
  env: awsEnv,
  envName,
});

const apiStack = new ApiStack(app, `${stackPrefix}-Api`, {
  env: awsEnv,
  envName,
  envConfig,
  userPool: authStack.userPool,
  userPoolClient: authStack.userPoolClient,
  videoBucket: storageStack.videoBucket,
  reportsTable: storageStack.reportsTable,
  settingsTable: storageStack.settingsTable,
  jobsTable: storageStack.jobsTable,
});

new FrontendStack(app, `${stackPrefix}-Frontend`, {
  env: awsEnv,
  envName,
  api: apiStack.api,
  userPool: authStack.userPool,
  userPoolClient: authStack.userPoolClient,
});

app.synth();
