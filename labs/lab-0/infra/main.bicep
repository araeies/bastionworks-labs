// Lab 0 — Secure your playground. Subscription-scope guardrails for a DEDICATED learning subscription:
// a low budget with early alerts, allowed regions, small VM sizes only, and a deny-list of expensive
// resource types. bw adds the bastionworks:playground=true tag afterwards with a merge (never replace).
targetScope = 'subscription'

@description('Lab id (set by bw).')
param labId string

@description('Learner seed code (set by bw).')
param seed string

@description('Seed-derived names (set by bw from lab.json kit.names).')
param names object

@description('Expiry date tag value (set by bw; guardrails are meant to stay, so unused here).')
#disable-next-line no-unused-params
param expires string

@description('Monthly budget in USD. Keep it low: alerts are your early warning. Budgets alert; they never stop spending.')
@minValue(1)
@maxValue(100)
param budgetAmountUsd int = 10

@description('First day of the current month; budgets cannot start in the past.')
param budgetStartDate string = '${utcNow('yyyy-MM')}-01'

@description('Regions labs may use.')
param allowedLocations array = [
  'uksouth'
  'ukwest'
  'westeurope'
  'northeurope'
  'southafricanorth'
  'eastus'
]

@description('Small, cheap VM sizes only.')
param allowedVmSkus array = [
  'Standard_B1s'
  'Standard_B1ms'
  'Standard_B2s'
  'Standard_B2ats_v2'
  'Standard_B2als_v2'
]

@description('Resource types that are expensive by default and never needed in Bastionworks labs.')
param deniedResourceTypes array = [
  'Microsoft.Network/ddosProtectionPlans'
  'Microsoft.Network/azureFirewalls'
  'Microsoft.Network/bastionHosts'
  'Microsoft.Network/virtualNetworkGateways'
  'Microsoft.Network/expressRouteCircuits'
  'Microsoft.Network/applicationGateways'
  'Microsoft.Network/frontDoors'
  'Microsoft.Sql/managedInstances'
  'Microsoft.Web/hostingEnvironments'
  'Microsoft.ApiManagement/service'
  'Microsoft.Databricks/workspaces'
  'Microsoft.Synapse/workspaces'
  'Microsoft.Kusto/clusters'
  'Microsoft.HDInsight/clusters'
  'Microsoft.AVS/privateClouds'
]

// Built-in policy definitions (IDs verified against github.com/Azure/azure-policy, 2026-10-14).
var allowedLocationsPolicy = 'e56962a6-4747-49cd-b67b-bf8b01975c4c' // Allowed locations
var allowedVmSkusPolicy = 'cccc23c7-8427-4f53-ad12-b6a63eb452b3' // Allowed virtual machine size SKUs
var deniedTypesPolicy = '6c112d4e-5bc7-47ae-a041-ea2d9dccd749' // Not allowed resource types
var metadata = {
  bastionworksLab: labId
  bastionworksSeed: seed
  assignedBy: 'Bastionworks Lab 0 (bw deploy)'
}

resource allowedLocations_ 'Microsoft.Authorization/policyAssignments@2024-04-01' = {
  name: 'bw-allowed-locations'
  properties: {
    displayName: 'Bastionworks: allowed locations (${names.playgroundId})'
    description: 'Lab 0 guardrail: resources may only be created in the regions Bastionworks labs use.'
    policyDefinitionId: tenantResourceId('Microsoft.Authorization/policyDefinitions', allowedLocationsPolicy)
    parameters: {
      listOfAllowedLocations: { value: allowedLocations }
    }
    metadata: metadata
  }
}

resource allowedVmSkus_ 'Microsoft.Authorization/policyAssignments@2024-04-01' = {
  name: 'bw-allowed-vm-sizes'
  properties: {
    displayName: 'Bastionworks: allowed VM sizes (${names.playgroundId})'
    description: 'Lab 0 guardrail: only small, low-cost VM sizes may be created in this playground subscription.'
    policyDefinitionId: tenantResourceId('Microsoft.Authorization/policyDefinitions', allowedVmSkusPolicy)
    parameters: {
      listOfAllowedSKUs: { value: allowedVmSkus }
    }
    metadata: metadata
  }
}

resource deniedTypes_ 'Microsoft.Authorization/policyAssignments@2024-04-01' = {
  name: 'bw-denied-resource-types'
  properties: {
    displayName: 'Bastionworks: denied expensive resource types (${names.playgroundId})'
    description: 'Lab 0 guardrail: blocks resource types that are expensive by default and never needed in Bastionworks labs.'
    policyDefinitionId: tenantResourceId('Microsoft.Authorization/policyDefinitions', deniedTypesPolicy)
    parameters: {
      listOfResourceTypesNotAllowed: { value: deniedResourceTypes }
    }
    metadata: metadata
  }
}

resource budget 'Microsoft.Consumption/budgets@2024-08-01' = {
  name: 'bw-${labId}-budget-${names.playgroundId}'
  properties: {
    category: 'Cost'
    amount: budgetAmountUsd
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: budgetStartDate
    }
    // contactRoles avoids collecting an email address: Azure notifies the subscription's Owners/Contributors.
    notifications: {
      actual25: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 25
        thresholdType: 'Actual'
        contactRoles: ['Owner', 'Contributor']
      }
      actual50: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 50
        thresholdType: 'Actual'
        contactRoles: ['Owner', 'Contributor']
      }
      actual90: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 90
        thresholdType: 'Actual'
        contactRoles: ['Owner', 'Contributor']
      }
      forecast100: {
        enabled: true
        operator: 'GreaterThanOrEqualTo'
        threshold: 100
        thresholdType: 'Forecasted'
        contactRoles: ['Owner', 'Contributor']
      }
    }
  }
}

output budgetName string = budget.name
