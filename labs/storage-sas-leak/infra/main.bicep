// Lab 1: The SAS token in the build log. DELIBERATELY VULNERABLE storage for the learner to find and fix,
// in the learner's own resource group. Synthetic data only (planted by seed/plant.py); expires with the lab.
// Vulnerable on purpose: anonymous blob access allowed, shared-key (and so SAS) access allowed, a public
// build-artifacts container. The learner's fix and IaC are what the checkpoints verify.
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

// checkov:skip=CKV_AZURE_190:Deliberately vulnerable lab resource: anonymous blob access is the scenario.
// checkov:skip=CKV_AZURE_59:Lab endpoints are probed from the internet (owner decision 3, option b); synthetic data only.
// checkov:skip=CKV_AZURE_206:Single short-lived lab account; LRS keeps learner cost near zero.
// checkov:skip=CKV_AZURE_33:Queue logging not relevant: the lab uses blobs only.
// checkov:skip=CKV2_AZURE_1:Customer-managed keys out of scope for this lab.
// checkov:skip=CKV2_AZURE_33:Private endpoints out of scope; the learner fixes public exposure differently.
// checkov:skip=CKV2_AZURE_38:Soft delete would keep deleted planted data after cleanup; not wanted here.
// checkov:skip=CKV2_AZURE_40:Shared-key access is the vulnerability the learner must disable.
// checkov:skip=CKV2_AZURE_41:SAS expiration policy would defeat the planted long-lived SAS scenario.
resource account 'Microsoft.Storage/storageAccounts@2024-01-01' = {
  name: names.storageAccount
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: true // VULNERABLE (scenario)
    allowSharedKeyAccess: true // VULNERABLE (scenario): account-key SAS tokens work
    allowCrossTenantReplication: false
    defaultToOAuthAuthentication: false
    publicNetworkAccess: 'Enabled'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2024-01-01' = {
  parent: account
  name: 'default'
}

// Anyone can read blobs in here: where the CI pipeline "accidentally" published its logs.
resource buildArtifacts 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobService
  name: 'build-artifacts'
  properties: {
    publicAccess: 'Blob' // VULNERABLE (scenario)
  }
}

// Private, but the leaked SAS grants read/list on it.
resource customerExports 'Microsoft.Storage/storageAccounts/blobServices/containers@2024-01-01' = {
  parent: blobService
  name: 'customer-exports'
  properties: {
    publicAccess: 'None'
  }
}

output storageAccountName string = account.name
output blobEndpoint string = account.properties.primaryEndpoints.blob
