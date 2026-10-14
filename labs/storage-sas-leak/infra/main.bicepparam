using 'main.bicep'

// Sample values for CI compilation and PSRule expansion only. bw supplies the real ones at deploy time.
param labId = 'storage-sas-leak'
param seed = 'K7Q2MX4P'
param names = { storageAccount: 'bwsasexample01' }
param expires = '2026-12-31'
