using 'main.bicep'

// Sample values for CI compilation and PSRule expansion only. bw supplies the real ones at deploy time.
param labId = 'app-trusts-everyone'
param seed = 'K7Q2MX4P'
param names = { plan: 'bw-plan-example1', portal: 'bw-portal-example001', api: 'bw-api-example0001' }
param expires = '2026-12-31'
