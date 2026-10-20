// Lab 2: The app that trusts everyone. DELIBERATELY VULNERABLE web apps for the learner to find and fix, in the
// learner's own resource group: a customer portal and an orders API on one Free (F1) Linux plan. Synthetic data only.
// Vulnerable on purpose: plain HTTP allowed, wildcard CORS, FTP and basic-auth publishing on, a debug page switched
// on, and an API with no authentication. The app code (../app) adds missing security headers and broken
// object-level authorisation. The learner's fixes and IaC are what the checkpoints verify.
targetScope = 'resourceGroup'

@description('Lab id (set by bw).')
param labId string

@description('Learner seed code (set by bw).')
param seed string

@description('Seed-derived names (set by bw from lab.json kit.names).')
param names object

@description('Expiry date tag value (set by bw).')
param expires string

param location string = resourceGroup().location

var tags = {
  'bastionworks:lab': labId
  'bastionworks:seed': seed
  'bastionworks:expires': expires
}

// Node.js LTS on App Service Linux. The kit test confirms the stack is offered in the learner's region.
var nodeStack = 'NODE|22-lts'
var apiHost = '${names.api}.azurewebsites.net'

resource plan 'Microsoft.Web/serverfarms@2024-04-01' = {
  // checkov:skip=CKV_AZURE_225:Free (F1) plan, so the lab costs nothing; zone redundancy needs Premium.
  name: names.plan
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: 'F1' // Free: 60 CPU minutes a day, plenty for a lab, and no charge
    tier: 'Free'
  }
  properties: {
    reserved: true // Linux
  }
}

// Both apps carry the same deliberately weak settings, written out in full so they're easy to compare with your fix.
resource portal 'Microsoft.Web/sites@2024-04-01' = {
  // checkov:skip=CKV_AZURE_222:Lab endpoints are probed from the internet (owner decision 3, option b); synthetic data only.
  // checkov:skip=CKV_AZURE_16:The app calls no Azure resources, so a managed identity would have nothing to do.
  // checkov:skip=CKV_AZURE_71:The app calls no Azure resources, so a managed identity would have nothing to do.
  // checkov:skip=CKV_AZURE_17:Client certificates are out of scope; the API's fix is Entra sign-in.
  // checkov:skip=CKV_AZURE_212:Free (F1) plan: one instance, so the lab costs nothing.
  // checkov:skip=CKV_AZURE_213:Free (F1) plan: health checks need a paid tier.
  // checkov:skip=CKV_AZURE_14:Deliberately vulnerable lab resource: plain HTTP is the scenario.
  // checkov:skip=CKV_AZURE_70:Deliberately vulnerable lab resource: plain HTTP is the scenario.
  // checkov:skip=CKV_AZURE_153:Deliberately vulnerable lab resource: plain HTTP is the scenario.
  // checkov:skip=CKV_AZURE_78:Deliberately vulnerable lab resource: FTP is the scenario.
  name: names.portal
  location: location
  tags: tags
  kind: 'app,linux'
  properties: {
    serverFarmId: plan.id
    httpsOnly: false // VULNERABLE (scenario): answers over plain HTTP
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: nodeStack
      appCommandLine: 'node server.js'
      alwaysOn: false // not available on Free
      http20Enabled: true
      minTlsVersion: '1.2' // App Service retires TLS 1.0 and 1.1 on 31 May 2027; the lab doesn't plant old TLS
      scmMinTlsVersion: '1.2'
      remoteDebuggingEnabled: false
      ftpsState: 'AllAllowed' // VULNERABLE (scenario): plain FTP allowed
      cors: {
        allowedOrigins: ['*'] // VULNERABLE (scenario): any website may read responses
      }
      appSettings: [
        { name: 'BW_ROLE', value: 'portal' }
        { name: 'BW_LAB', value: labId }
        { name: 'BW_SEED', value: seed }
        { name: 'BW_DEBUG', value: 'on' } // VULNERABLE (scenario): the debug page is live
        { name: 'BW_ORDERS_API_URL', value: 'https://${apiHost}' }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'false' } // built-ins only: nothing to build
      ]
    }
  }
}

resource api 'Microsoft.Web/sites@2024-04-01' = {
  // checkov:skip=CKV_AZURE_222:Lab endpoints are probed from the internet (owner decision 3, option b); synthetic data only.
  // checkov:skip=CKV_AZURE_16:The app calls no Azure resources, so a managed identity would have nothing to do.
  // checkov:skip=CKV_AZURE_71:The app calls no Azure resources, so a managed identity would have nothing to do.
  // checkov:skip=CKV_AZURE_17:Client certificates are out of scope; the API's fix is Entra sign-in.
  // checkov:skip=CKV_AZURE_212:Free (F1) plan: one instance, so the lab costs nothing.
  // checkov:skip=CKV_AZURE_213:Free (F1) plan: health checks need a paid tier.
  // checkov:skip=CKV_AZURE_14:Deliberately vulnerable lab resource: plain HTTP is the scenario.
  // checkov:skip=CKV_AZURE_70:Deliberately vulnerable lab resource: plain HTTP is the scenario.
  // checkov:skip=CKV_AZURE_153:Deliberately vulnerable lab resource: plain HTTP is the scenario.
  // checkov:skip=CKV_AZURE_78:Deliberately vulnerable lab resource: FTP is the scenario.
  name: names.api
  location: location
  tags: tags
  kind: 'app,linux'
  properties: {
    serverFarmId: plan.id
    httpsOnly: false // VULNERABLE (scenario)
    clientAffinityEnabled: false
    siteConfig: {
      linuxFxVersion: nodeStack
      appCommandLine: 'node server.js'
      alwaysOn: false // not available on Free
      http20Enabled: true
      minTlsVersion: '1.2' // App Service retires TLS 1.0 and 1.1 on 31 May 2027; the lab doesn't plant old TLS
      scmMinTlsVersion: '1.2'
      remoteDebuggingEnabled: false
      ftpsState: 'AllAllowed' // VULNERABLE (scenario): plain FTP allowed
      cors: {
        allowedOrigins: ['*'] // VULNERABLE (scenario): any website may read responses
      }
      appSettings: [
        { name: 'BW_ROLE', value: 'api' }
        { name: 'BW_LAB', value: labId }
        { name: 'BW_SEED', value: seed }
        { name: 'SCM_DO_BUILD_DURING_DEPLOYMENT', value: 'false' }
      ]
    }
  }
  // VULNERABLE (scenario): no built-in authentication (no authsettingsV2), so anyone can call the API.
}

// VULNERABLE (scenario): username-and-password publishing (FTP, and Web Deploy or Git over SCM) on both apps.
resource portalFtp 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  parent: portal
  name: 'ftp'
  properties: { allow: true }
}

resource portalScm 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  parent: portal
  name: 'scm'
  properties: { allow: true }
}

resource apiFtp 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  parent: api
  name: 'ftp'
  properties: { allow: true }
}

resource apiScm 'Microsoft.Web/sites/basicPublishingCredentialsPolicies@2024-04-01' = {
  parent: api
  name: 'scm'
  properties: { allow: true }
}

output portalUrl string = 'http://${portal.properties.defaultHostName}'
output apiUrl string = 'http://${api.properties.defaultHostName}'
