# Evidence 01: Landing-volume file inventory and samples

Volume: `/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/` · captured 2026-11-20 after job `febar_generate`.

Layout: `<system>/<YYYY-MM-DD>/<file>` + `_MANIFEST.json` (control totals: record_count, amount_total, file_created_ts), written last. A folder with a manifest is never rewritten.

## Inventory per system

| System | Folders | Files (incl. manifests) | MB | First folder | Last folder |
|---|---|---|---|---|---|
| `iss_auth` | 363 | 726 | 1320.0 | 2025-11-20 | 2026-11-17 |
| `mrd_events` | 310 | 620 | 338.3 | 2026-01-12 | 2026-11-17 |
| `atl_daily` | 363 | 726 | 842.8 | 2025-11-20 | 2026-11-17 |
| `merchant_master` | 363 | 726 | 6.2 | 2025-11-20 | 2026-11-17 |
| `card_portfolio` | 28 | 56 | 3.8 | 2025-11-20 | 2026-09-18 |
| `acquirer_ref` | 14 | 28 | 0.2 | 2025-11-20 | 2026-11-01 |
| `ref` | 1 | 3 | 0.0 | 2025-11-20 | 2025-11-20 |
| **Total** | 1442 | 2885 | 2511.3 | | |

Notes: `mrd_events` starts at wave 1 (2026-01-12); `card_portfolio` has folders only on days with changes (full load, wave slips, migrations, stale re-sends); `acquirer_ref` = monthly snapshots + 2026-09-23.

## `databricks fs ls` (top level and one folder per system, with sizes in bytes)
```
$ databricks fs ls dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing
_generator_truth
acquirer_ref
atl_daily
card_portfolio
iss_auth
merchant_master
mrd_events
ref

$ databricks fs ls -l dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/iss_auth/2026-09-30
FILE 3457724 ISSAUTH_20260930_202610010030.csv
FILE 204 _MANIFEST.json

$ databricks fs ls -l dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/mrd_events/2026-09-30
FILE 1717344 MRD_AUTH_EVENTS_20260930_202610010030.jsonl
FILE 214 _MANIFEST.json

$ databricks fs ls -l dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/atl_daily/2026-08-05
FILE 2048961 ATL_DAILY_20260805_202608060600.txt
FILE 207 _MANIFEST.json

$ databricks fs ls -l dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/atl_daily/2026-10-14
FILE 1981413 ATL_DAILY_20261014_202610160600.txt
FILE 207 _MANIFEST.json

$ databricks fs ls -l dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/card_portfolio/2026-09-18
FILE 1580 CARD_PORTFOLIO_DELTA_20260918.csv
FILE 201 _MANIFEST.json

$ databricks fs ls dbfs:/Volumes/classic_stable_zjnu75_catalog/network_migration/landing/iss_auth | tail -3   # held-back dates absent
2026-11-15
2026-11-16
2026-11-17
```

## Rerun safety

The second run with the same seed wrote **0** folders for every system: `iss_auth`: 0, `mrd_events`: 0, `atl_daily`: 0, `merchant_master`: 0, `card_portfolio`: 0, `acquirer_ref`: 0. All existing folders were skipped.

## Samples (first rows of each file, as text)

#### `iss_auth/2026-09-30/ISSAUTH_20260930_202610010030.csv`
```
AUTH_ID,AUTH_TS_LOCAL,AUTH_TZ,CARD_REF,CARD_ACCEPTOR_ID,ACQ_INST_ID,MCC,POS_ENTRY_MODE,TRAN_AMT,CURR_CD,TERM_CNTRY,NETWORK_ID,WALLET_IND,RECUR_IND,AUTH_DECISION,ISS_RESP_CD
A20260930000000,2026-09-30 08:53:22,America/Los_Angeles,CR04250090,MR066709757,910001,5814,05,7.57,840,USA,MRD,N,N,A,00
A20260930000001,2026-09-30 18:06:49,America/Chicago,CR06854274,MR101157407,901233,5814,07,2.81,840,USA,ATL,W,N,A,00
A20260930000002,2026-09-30 17:02:38,America/New_York,CR59893579,MR007063849,900959,7011,81,129.81,840,USA,ATL,C,N,A,00
A20260930000003,2026-09-30 17:55:26,America/Los_Angeles,CR10252033,MR020676610,907124,5812,07,24.43,840,USA,MRD,N,N,A,00
A20260930000004,2026-09-30 15:57:35,America/Chicago,CR25424774,MR264645162,900274,5651,81,33.81,840,USA,MRD,N,N,A,00
```
#### `iss_auth/2026-09-30/_MANIFEST.json`
```
{"system": "iss_auth", "business_date": "2026-09-30", "file_created_ts": "2026-10-01T00:30:00", "files": [{"name": "ISSAUTH_20260930_202610010030.csv", "record_count": 29361, "amount_total": 2293032.35}]}
```
#### `mrd_events/2026-09-30/MRD_AUTH_EVENTS_20260930_202610010030.jsonl`
```
{"netTxnId":"MRDcd878ba4ebd64127","issuerAuthRef":"A20260930000000","eventTimeUtc":"2026-09-30T15:53:23.266Z","merchantNetworkId":"MRD82186559","acquirerCode":"ACQ-073","amountMinor":757,"currency":"USD","responseCode":"M000","processingPath":"DIRECT","crossBorder":false,"stipFlag":false}
{"netTxnId":"MRD1e73ea44fe7ec2ce","issuerAuthRef":"A20260930000003","eventTimeUtc":"2026-10-01T00:55:27.587Z","merchantNetworkId":"M-73431760","acquirerCode":"ACQ-052","amountMinor":2443,"currency":"USD","responseCode":"M000","processingPath":"DIRECT","crossBorder":false,"stipFlag":false}
{"netTxnId":"MRD64264cfef4657b8c","issuerAuthRef":"A20260930000004","eventTimeUtc":"2026-09-30T20:57:35.750Z","merchantNetworkId":"MRD99737944","acquirerCode":"ACQ-002","amountMinor":3381,"currency":"USD","responseCode":"M000","processingPath":"DIRECT","crossBorder":false,"stipFlag":false}
{"netTxnId":"MRDa39eb98622ba2157","issuerAuthRef":"A20260930000026","eventTimeUtc":"2026-09-30T18:16:54.405Z","merchantNetworkId":"M-45187872","acquirerCode":"ACQ-047","amountMinor":4799,"currency":"USD","responseCode":"M000","processingPath":"DIRECT","crossBorder":false,"stipFlag":false}
{"netTxnId":"MRDd73847c6febfcb5b","issuerAuthRef":"A20260930000027","eventTimeUtc":"2026-09-30T17:56:18.797Z","merchantNetworkId":"M-29050138","acquirerCode":"ACQ-001","amountMinor":8185,"currency":"USD","responseCode":"M000","processingPath":"DIRECT","crossBorder":false,"stipFlag":false}
{"netTxnId":"MRD87dba33e4db4f26c","issuerAuthRef":"A20260930000029","eventTimeUtc":"2026-09-30T04:10:01.963Z","merchantNetworkId":"MRD39291989","acquirerCode":"ACQ-049","amountMinor":10025,"currency":"USD","responseCode":"M000","processingPath":"DIRECT","tokenRequestorId":"TR-40022","crossBorder":false,"stipFlag":false}
```
#### `mrd_events/2026-09-30/_MANIFEST.json`
```
{"system": "mrd_events", "business_date": "2026-09-30", "file_created_ts": "2026-10-01T00:30:00", "files": [{"name": "MRD_AUTH_EVENTS_20260930_202610010030.jsonl", "record_count": 5789, "amount_total": 435697.84}]}
```
#### `atl_daily/2026-09-30/ATL_DAILY_20260930_202610010600.txt`
```
txn_ref|auth_reference|txn_date|txn_time|mer_id|acq_bin|amt|resp_cd|rsn_cd|xb_flag|pos_cd
ATL873828635954|A20260930000001|09/30/2026|180649|816413965|901233|2.81|000|  |N|07
ATL575126881865|A20260930000002|09/30/2026|170238|813389799|900959|129.81|000|  |N|81
ATL258079109733|A20260930000005|09/30/2026|201321|388110027|900685|42.86|000|  |N|05
ATL016633275299|A20260930000006|09/30/2026|125124|632206789|900274|148.24|000|  |N|05
ATL850224459423|A20260930000007|09/30/2026|090409|185798617|900274|48.57|000|  |N|07
```
#### `atl_daily/2026-09-30/_MANIFEST.json`
```
{"system": "atl_daily", "business_date": "2026-09-30", "file_created_ts": "2026-10-01T06:00:00", "files": [{"name": "ATL_DAILY_20260930_202610010600.txt", "record_count": 23011, "amount_total": 1817309.9}]}
```
#### `merchant_master/2025-11-20/MERCHANT_MASTER_FULL_20251120.csv`
```
MRCH_NUM,DBA_NAME,MCC,CITY,STATE,CNTRY,ACQ_INST_ID,MRD_MID,ATL_MID,STATUS,EFF_DT
MR000000101,Highline Market #0000,5411,Upton Vale,CA,USA,900137,MRD00000007,000000003,A,2019-01-25
MR000031777,Ironwood Goods Co #0124,5999,Ashford Glen,TX,USA,904795,MRD00418899,061943455,A,2019-03-24
MR000039696,Clearwater Row Kitchen #0155,5812,Juniper Flats,TX,USA,907809,MRD00523622,077429318,A,2024-01-28
MR000047615,Thistledown Quick Eats #0186,5814,Westhollow,CA,USA,900137,MRD00628345,000000092915181,A,2020-02-04
MR000063453,Driftwood Outfitters #0248,5651,Brookhaven Point,NY,USA,900822,MRD00837791,123886907,A,2023-07-20
```
#### `merchant_master/2025-11-20/_MANIFEST.json`
```
{"system": "merchant_master", "business_date": "2025-11-20", "file_created_ts": "2025-11-21T04:00:00", "files": [{"name": "MERCHANT_MASTER_FULL_20251120.csv", "record_count": 40000, "amount_total": null}]}
```
#### `merchant_master/2026-09-30/MERCHANT_MASTER_DELTA_20260930.csv`
```
MRCH_NUM,DBA_NAME,MCC,CITY,STATE,CNTRY,ACQ_INST_ID,MRD_MID,ATL_MID,STATUS,EFF_DT
MR035611844,Saltmarsh Outfitters #9758   ,5651,Granite Bay,WA,USA,901096,MRD70939338,639925914,A,2026-09-30
MR046833067,Stonebridge Fuel Stop #3820,5541,Juniper Flats,CA,USA,903425,MRD19331829,583393785,A,2026-09-30
MR050745053,Birchstone Inn & Suites #9161,7011,Kestrel Park,NM,USA,900137,MRD71064991,233410107,A,2026-09-30
MR051837875,Juniper Department Store #3466,5311,Northvale,VA,USA,900137,MRD85516765,370459201,A,2026-09-30
MR016392431,Hollowtree Kitchen #4332,5812,Granite Bay,WA,USA,900137,MRD16776617,055736413,A,2026-09-30
```
#### `merchant_master/2026-09-30/_MANIFEST.json`
```
{"system": "merchant_master", "business_date": "2026-09-30", "file_created_ts": "2026-10-01T04:00:00", "files": [{"name": "MERCHANT_MASTER_DELTA_20260930.csv", "record_count": 50, "amount_total": null}]}
```
#### `card_portfolio/2026-09-08/CARD_PORTFOLIO_DELTA_20260908.csv`
```
CARD_REF,PRODUCT_CD,SEGMENT,HOME_ST,WAVE_ID,PLANNED_MIG_DT,ACTUAL_MIG_DT,ISSUER_SEG,STATUS,UPDATE_TS
CR64874140,CSH,INTL_TRAVELER,OH,6,2026-09-08,2026-09-08,OWN,ACTIVE,2026-09-08 03:35:55
CR40592130,RWD,WALLET_HEAVY,NY,6,2026-09-08,2026-09-08,OWN,ACTIVE,2026-09-08 03:21:05
CR08609836,CSH,ECOM_HEAVY,NY,6,2026-09-08,2026-09-08,OWN,ACTIVE,2026-09-08 03:19:39
CR90781075,TRV,WALLET_HEAVY,OR,6,2026-09-08,2026-09-08,OWN,ACTIVE,2026-09-08 03:09:30
CR64260884,RWD,RECURRING_HEAVY,PA,6,2026-09-08,2026-09-08,OWN,ACTIVE,2026-09-08 03:24:51
```
#### `card_portfolio/2026-09-08/_MANIFEST.json`
```
{"system": "card_portfolio", "business_date": "2026-09-08", "file_created_ts": "2026-09-09T04:00:00", "files": [{"name": "CARD_PORTFOLIO_DELTA_20260908.csv", "record_count": 1442, "amount_total": null}]}
```
#### `acquirer_ref/2026-09-23/ACQUIRER_REF_20260923.jsonl`
```
{"acquirerId":"ACQ-001","acquirerName":"Northgate Merchant Services","bin":"900137","region":"NE","mrdCertified":true,"certifiedDate":"2025-06-02","lastConfigChange":"2025-05-01"}
{"acquirerId":"ACQ-002","acquirerName":"Clearpath Merchant Services","bin":"900274","region":"MW","mrdCertified":true,"certifiedDate":"2025-07-09","lastConfigChange":"2025-06-23"}
{"acquirerId":"ACQ-017","acquirerName":"Ridgeline Merchant Services","bin":"902329","region":"MW","mrdCertified":true,"certifiedDate":"2025-09-22","lastConfigChange":"2026-09-22","configNote":"Meridian profile update: e-commerce token cryptogram settings"}
```
#### `acquirer_ref/2026-09-23/_MANIFEST.json`
```
{"system": "acquirer_ref", "business_date": "2026-09-23", "file_created_ts": "2026-09-24T04:00:00", "files": [{"name": "ACQUIRER_REF_20260923.jsonl", "record_count": 80, "amount_total": null}]}
```
#### `ref/2025-11-20/RECOVERY_ASSUMPTIONS_v1.csv`
```
segment,unrecovered_rate,version,effective_dt,source
DOMESTIC,0.4,v1,2026-01-01,Finance estimate (synthetic)
ECOM_HEAVY,0.55,v1,2026-01-01,Finance estimate (synthetic)
RECURRING_HEAVY,0.35,v1,2026-01-01,Finance estimate (synthetic)
WALLET_HEAVY,0.45,v1,2026-01-01,Finance estimate (synthetic)
INTL_TRAVELER,0.6,v1,2026-01-01,Finance estimate (synthetic)
```
#### `ref/2025-11-20/RESPONSE_CODE_MAP_v1.csv`
```
network_cd,native_cd,description,std_category,is_acceptance_failure
ISS,00,Approved,APPROVED,N
ISS,05,Do not honor,ISSUER_LEGIT_DNH,N
ISS,51,Insufficient funds,ISSUER_LEGIT_NSF,N
ISS,54,Expired card,ISSUER_LEGIT_EXPIRED,N
ISS,14,Invalid card number,ISSUER_LEGIT_INVALID,N
```
#### `ref/2025-11-20/_MANIFEST.json`
```
{"system": "ref", "business_date": "2025-11-20", "file_created_ts": "2025-11-20T00:00:00", "files": [{"name": "RESPONSE_CODE_MAP_v1.csv", "record_count": 134}, {"name": "RECOVERY_ASSUMPTIONS_v1.csv", "record_count": 6}]}
```

