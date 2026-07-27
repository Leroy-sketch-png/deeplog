# Diagnosed Analyst Review Packet

This packet maps raw anomaly scores into deterministic operational causal categories for SOC triage. Two independent review queues are provided for Track A.

---

## Track A — Queue 1: Top 20 by Total Score
Structural workflow violations or extreme timing deviations within a single backend operation lifecycle.

### A1-1. `a222a216-ebee-40c5-b8db-be5fdaea4544`
**Window:** 2026-07-13T03:01:39.664055+00:00 — 2026-07-13T03:01:45.426707+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Critical Deployment/Migration Shift
**Cause:** Unseen sequence path combined with massive latency, likely indicating a failed backend deployment involving `MICROSOFT.NETWORK/VIRTUALNETWORKS/SUBNETS/SERVICEASSOCIATIONLINKS/WRITE`.
**Scores:** Total `4.0` | Eff. Signals `2` | Pattern Instances `10` | Struct `1.0` | Rarity `1.0` | Duration `1.0` | Length `1.0` | Context `0.0`

### A1-2. `0b8882fb-0603-4d9f-9a5b-caced38a7142`
**Window:** 2026-07-13T00:00:21.340779+00:00 — 2026-07-13T00:00:39.727434+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Critical Deployment/Migration Shift
**Cause:** Unseen sequence path combined with massive latency, likely indicating a failed backend deployment involving `MICROSOFT.SQL/SERVERS/DATABASES/WRITE`.
**Scores:** Total `4.0` | Eff. Signals `2` | Pattern Instances `343` | Struct `1.0` | Rarity `1.0` | Duration `1.0` | Length `1.0` | Context `0.0`

### A1-3. `1fd1afbf-3afb-46b6-8dd7-35381c72cc9b`
**Window:** 2026-07-11T08:46:38.004925+00:00 — 2026-07-11T10:06:42.644776+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Lateral Boundary Crossing
**Cause:** CorrelationId unexpectedly traversed distinct resource groups or providers during `MICROSOFT.NETWORK/VIRTUALNETWORKS/TAGGEDTRAFFICCONSUMERS/VALIDATE/ACTION`.
**Scores:** Total `3.076` | Eff. Signals `2` | Pattern Instances `21` | Struct `0.0` | Rarity `0.995` | Duration `0.484` | Length `0.597` | Context `1.0`

### A1-4. `a220e4a2-e728-4885-b3c3-3ed1a85b19eb`
**Window:** 2026-07-11T16:48:44.048513+00:00 — 2026-07-11T16:57:00.658383+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Lateral Boundary Crossing
**Cause:** CorrelationId unexpectedly traversed distinct resource groups or providers during `MICROSOFT.NETWORK/VIRTUALNETWORKS/TAGGEDTRAFFICCONSUMERS/VALIDATE/ACTION`.
**Scores:** Total `2.914` | Eff. Signals `3` | Pattern Instances `2` | Struct `0.0` | Rarity `0.995` | Duration `0.097` | Length `0.822` | Context `1.0`

### A1-5. `04acc6d0-eaf0-4032-9298-ffe8e28b6a61`
**Window:** 2026-07-12T04:56:53.215819+00:00 — 2026-07-12T04:57:08.645601+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.SQL/SERVERS/DATABASES/BACKUPSHORTTERMRETENTIONPOLICIES/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.743` | Eff. Signals `1` | Pattern Instances `1` | Struct `1.0` | Rarity `1.0` | Duration `0.253` | Length `0.49` | Context `0.0`

### A1-6. `033d6d1a-bf1d-4176-937f-42ea33754eee`
**Window:** 2026-07-11T14:41:54.020717+00:00 — 2026-07-11T14:42:04.192789+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.COMPUTE/VIRTUALMACHINESCALESETS/DELETE/ACTION`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.712` | Eff. Signals `1` | Pattern Instances `1` | Struct `1.0` | Rarity `1.0` | Duration `0.467` | Length `0.244` | Context `0.0`

### A1-7. `fdf4aae1-3162-43d8-a079-21d783996b67`
**Window:** 2026-07-13T06:40:17.052068+00:00 — 2026-07-13T06:40:33.043789+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.KUSTO/CLUSTERS/DATABASES/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.522` | Eff. Signals `1` | Pattern Instances `1` | Struct `1.0` | Rarity `1.0` | Duration `0.278` | Length `0.245` | Context `0.0`

### A1-8. `b6f484c8-a19e-45df-b76c-e785761f1cba`
**Window:** 2026-07-12T23:44:09.635025+00:00 — 2026-07-12T23:54:09.992659+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Stalled Operation
**Cause:** Abnormal volume of events within the same CorrelationId cycle.
**Scores:** Total `2.492` | Eff. Signals `2` | Pattern Instances `1` | Struct `0.0` | Rarity `1.0` | Duration `0.492` | Length `1.0` | Context `0.0`

### A1-9. `dba4d656-db45-45be-99e0-a0210d5778d9`
**Window:** 2026-07-11T09:25:17.067742+00:00 — 2026-07-11T09:55:28.670949+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Lateral Boundary Crossing
**Cause:** CorrelationId unexpectedly traversed distinct resource groups or providers during `MICROSOFT.NETWORK/VIRTUALNETWORKS/TAGGEDTRAFFICCONSUMERS/VALIDATE/ACTION`.
**Scores:** Total `2.488` | Eff. Signals `2` | Pattern Instances `75` | Struct `0.0` | Rarity `0.995` | Duration `0.122` | Length `0.371` | Context `1.0`

### A1-10. `8b379118-d277-4ad4-bd77-6c134c189c9d`
**Window:** 2026-07-13T05:22:46.062687+00:00 — 2026-07-13T05:23:03.170535+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.SQL/SERVERS/DATABASES/DELETE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.448` | Eff. Signals `1` | Pattern Instances `2` | Struct `1.0` | Rarity `1.0` | Duration `0.081` | Length `0.367` | Context `0.0`

### A1-11. `5b11ad2b-2be5-4b65-8db6-4cd75e607e37`
**Window:** 2026-07-11T07:37:48.947717+00:00 — 2026-07-11T07:47:50.548085+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Latency / Retry Loop
**Cause:** Standard workflow path, but extreme timing delay indicative of a backend retry loop terminating at `MICROSOFT.SQL/SERVERS/DATABASES/WRITE`.
**Scores:** Total `2.431` | Eff. Signals `2` | Pattern Instances `3210` | Struct `0.0` | Rarity `0.925` | Duration `1.0` | Length `0.506` | Context `0.0`

### A1-12. `d5ffae81-ada6-4a45-a33b-9857cbfa4e16`
**Window:** 2026-07-11T16:40:28.549408+00:00 — 2026-07-11T16:50:29.530612+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Stalled Operation
**Cause:** Abnormal volume of events within the same CorrelationId cycle.
**Scores:** Total `2.43` | Eff. Signals `2` | Pattern Instances `1` | Struct `0.0` | Rarity `1.0` | Duration `0.492` | Length `0.938` | Context `0.0`

### A1-13. `67fcd844-27e0-4a12-81d8-ca862a42ab6b`
**Window:** 2026-07-13T02:19:54.590565+00:00 — 2026-07-13T02:20:02.613701+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.NETWORK/LOADBALANCERS/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.386` | Eff. Signals `1` | Pattern Instances `3` | Struct `1.0` | Rarity `1.0` | Duration `0.141` | Length `0.245` | Context `0.0`

### A1-14. `9f0a87ea-3796-4440-abe4-fa7c875780f6`
**Window:** 2026-07-13T02:18:48.497521+00:00 — 2026-07-13T02:18:56.821068+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.NETWORK/LOADBALANCERS/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.386` | Eff. Signals `1` | Pattern Instances `3` | Struct `1.0` | Rarity `1.0` | Duration `0.141` | Length `0.245` | Context `0.0`

### A1-15. `2298053a-e275-4424-8070-34506e041c95`
**Window:** 2026-07-13T02:17:14.500570+00:00 — 2026-07-13T02:17:21.228028+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.NETWORK/LOADBALANCERS/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.386` | Eff. Signals `1` | Pattern Instances `3` | Struct `1.0` | Rarity `1.0` | Duration `0.141` | Length `0.245` | Context `0.0`

### A1-16. `34f03ea3-b00f-475e-b3e0-c229ee5085ef`
**Window:** 2026-07-13T02:15:59.763028+00:00 — 2026-07-13T02:16:06.286632+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.NETWORK/LOADBALANCERS/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.386` | Eff. Signals `1` | Pattern Instances `5` | Struct `1.0` | Rarity `1.0` | Duration `0.141` | Length `0.245` | Context `0.0`

### A1-17. `669b68c8-b3b6-4cd7-a249-9b03c3cedde2`
**Window:** 2026-07-13T02:13:40.137261+00:00 — 2026-07-13T02:13:44.244537+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.NETWORK/LOADBALANCERS/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.386` | Eff. Signals `1` | Pattern Instances `3` | Struct `1.0` | Rarity `1.0` | Duration `0.141` | Length `0.245` | Context `0.0`

### A1-18. `18a39400-ae9b-4528-a9f5-db4f84770a6f`
**Window:** 2026-07-13T02:12:17.097689+00:00 — 2026-07-13T02:12:24.304441+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.NETWORK/LOADBALANCERS/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.386` | Eff. Signals `1` | Pattern Instances `3` | Struct `1.0` | Rarity `1.0` | Duration `0.141` | Length `0.245` | Context `0.0`

### A1-19. `60c85589-a940-4387-b6a2-b08614771488`
**Window:** 2026-07-13T02:12:08.144438+00:00 — 2026-07-13T02:12:09.316333+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.NETWORK/LOADBALANCERS/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.386` | Eff. Signals `1` | Pattern Instances `11` | Struct `1.0` | Rarity `1.0` | Duration `0.141` | Length `0.245` | Context `0.0`

### A1-20. `90ec13a5-dbae-423d-8f4b-4549385843da`
**Window:** 2026-07-13T02:09:48.005506+00:00 — 2026-07-13T02:10:00.041461+00:00
**Uncertainty:** LOW_CONFIDENCE
**Category:** New Microservice Routine
**Cause:** Strictly unseen workflow path to `MICROSOFT.NETWORK/LOADBALANCERS/WRITE`, likely an unmodeled script or manual intervention.
**Scores:** Total `2.386` | Eff. Signals `1` | Pattern Instances `5` | Struct `1.0` | Rarity `1.0` | Duration `0.141` | Length `0.245` | Context `0.0`

---

## Track A — Queue 2: Top 20 by Context Inconsistency
CorrelationIds that traversed distinct resource groups or subscriptions — a distinct cross-boundary anomaly axis, evaluated independently of sequence structure.

### A2-1. `836b3380-2b0b-47aa-af11-fdc28dc48bd1`
**Window:** 2026-07-11T07:41:15.761123+00:00 — 2026-07-11T07:50:55.741504+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Lateral Boundary Crossing
**Cause:** CorrelationId unexpectedly traversed distinct resource groups or providers during `MICROSOFT.NETWORK/VIRTUALNETWORKS/TAGGEDTRAFFICCONSUMERS/VALIDATE/ACTION`.
**Scores:** Total `2.285` | Eff. Signals `2` | Pattern Instances `92` | Struct `0.0` | Rarity `0.995` | Duration `0.097` | Length `0.193` | Context `1.0`

---

## Track B — Caller 30-Minute Session Drift
Identity-centric behavioral drift: net-new access patterns or volume spikes over a 30-minute window.

### B-1. `ec712e27-21a7-46d9-b3b1-94e125392689`
**Window:** 2026-07-13T03:01:39.664055+00:00 — 2026-07-13T03:29:51.188501+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Possible Credential/Token Compromise
**Cause:** Identity used a brand new IP to execute unseen operations (`MICROSOFT.NETWORK/VIRTUALNETWORKS/SUBNETS/SERVICEASSOCIATIONLINKS/WRITE`) at an unusually high volume.
**Scores:** Total `7.0` | Eff. Signals `4` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `1.0` | New RG `1.0` | Act Spike `1.0` | Hour Dev `0.0`

### B-2. `ec712e27-21a7-46d9-b3b1-94e125392689`
**Window:** 2026-07-13T03:54:07.383824+00:00 — 2026-07-13T03:54:15.572723+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Possible Credential/Token Compromise
**Cause:** Identity used a brand new IP to execute unseen operations (`MICROSOFT.NETWORK/VIRTUALNETWORKS/SUBNETS/SERVICEASSOCIATIONLINKS/WRITE`) at an unusually high volume.
**Scores:** Total `7.0` | Eff. Signals `4` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `1.0` | New RG `1.0` | Act Spike `1.0` | Hour Dev `0.0`

### B-3. `f944677e-d2b8-440e-a288-7ecf1d016305`
**Window:** 2026-07-11T14:41:54.020717+00:00 — 2026-07-11T14:42:04.192789+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Possible Credential/Token Compromise
**Cause:** Identity used a brand new IP to execute unseen operations (`MICROSOFT.COMPUTE/VIRTUALMACHINESCALESETS/DELETE/ACTION`) at an unusually high volume.
**Scores:** Total `6.6` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `1.0` | New RG `1.0` | Act Spike `0.6` | Hour Dev `0.0`

### B-4. `3ddc0bea-151f-4a8b-9b9e-6feceed02576`
**Window:** 2026-07-13T06:40:17.052068+00:00 — 2026-07-13T06:40:33.043789+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Possible Credential/Token Compromise
**Cause:** Identity used a brand new IP to execute unseen operations (`MICROSOFT.KUSTO/CLUSTERS/DATABASES/WRITE`) at an unusually high volume.
**Scores:** Total `6.6` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `1.0` | New RG `1.0` | Act Spike `0.6` | Hour Dev `0.0`

### B-5. `0dfc69b3-63ca-4ac5-a08f-697ae4be2771`
**Window:** 2026-07-13T00:00:21.340779+00:00 — 2026-07-13T00:10:46.609244+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Automation / Batch Script Change
**Cause:** Massive volume spike of unseen operations (`MICROSOFT.SQL/SERVERS/DATABASES/WRITE`) from a known IP, indicating a cron job or automation change.
**Scores:** Total `5.44` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `1.0` | Act Spike `1.0` | Hour Dev `0.44`

### B-6. `e7778229-8a2f-49d3-bcc3-a89f9e377ffa`
**Window:** 2026-07-13T02:34:46.431031+00:00 — 2026-07-13T02:55:51.680691+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.689` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.768` | Hour Dev `0.921`

### B-7. `3154fdeb-3386-4e53-892d-af6182a6a7eb`
**Window:** 2026-07-13T02:31:42.385486+00:00 — 2026-07-13T02:58:34.190283+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.455` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.501` | Hour Dev `0.954`

### B-8. `a1972da0-b698-4a62-b333-a679954ecf5c`
**Window:** 2026-07-13T02:33:15.921255+00:00 — 2026-07-13T02:59:24.990291+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Unclassified Behavioral Drift
**Cause:** Session deviates from standard historical actor baseline.
**Scores:** Total `3.231` | Eff. Signals `2` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.459` | Hour Dev `0.771`

### B-9. `e7778229-8a2f-49d3-bcc3-a89f9e377ffa`
**Window:** 2026-07-13T02:21:22.949481+00:00 — 2026-07-13T02:21:30.242445+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.227` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.288` | Hour Dev `0.939`

### B-10. `d1fd911f-132c-4765-83ea-892def9625e6`
**Window:** 2026-07-13T03:01:08.059038+00:00 — 2026-07-13T03:29:06.997796+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.209` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.389` | Hour Dev `0.821`

### B-11. `fa2f2f17-abc9-4752-8afc-2057125a66f8`
**Window:** 2026-07-13T02:32:45.860638+00:00 — 2026-07-13T02:59:15.252006+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.166` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.28` | Hour Dev `0.886`

### B-12. `de188c5d-cc07-4edb-b97f-55b3233bc0be`
**Window:** 2026-07-13T02:30:03.191064+00:00 — 2026-07-13T02:59:59.704329+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Unclassified Behavioral Drift
**Cause:** Session deviates from standard historical actor baseline.
**Scores:** Total `3.159` | Eff. Signals `2` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.372` | Hour Dev `0.787`

### B-13. `bb36369a-b619-41fa-ab89-7cfd11aa3bdd`
**Window:** 2026-07-13T02:05:24.816500+00:00 — 2026-07-13T02:17:37.245808+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.158` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.182` | Hour Dev `0.976`

### B-14. `de188c5d-cc07-4edb-b97f-55b3233bc0be`
**Window:** 2026-07-13T02:18:48.497521+00:00 — 2026-07-13T02:29:59.068090+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.123` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.32` | Hour Dev `0.803`

### B-15. `d1fd911f-132c-4765-83ea-892def9625e6`
**Window:** 2026-07-13T02:36:16.659366+00:00 — 2026-07-13T02:57:40.327482+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.118` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.263` | Hour Dev `0.855`

### B-16. `3154fdeb-3386-4e53-892d-af6182a6a7eb`
**Window:** 2026-07-13T02:13:40.137261+00:00 — 2026-07-13T02:13:44.244537+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.095` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.116` | Hour Dev `0.979`

### B-17. `d1fd911f-132c-4765-83ea-892def9625e6`
**Window:** 2026-07-13T02:23:31.912946+00:00 — 2026-07-13T02:23:40.470423+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.028` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.156` | Hour Dev `0.873`

### B-18. `cdf534dc-0dae-4754-8b5d-79245150f30d`
**Window:** 2026-07-13T02:09:48.005506+00:00 — 2026-07-13T02:10:00.041461+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `3.025` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.138` | Hour Dev `0.887`

### B-19. `bb36369a-b619-41fa-ab89-7cfd11aa3bdd`
**Window:** 2026-07-13T02:32:13.657122+00:00 — 2026-07-13T02:59:06.277815+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `2.994` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.007` | Hour Dev `0.987`

### B-20. `0e294f7c-e6d7-4c67-ad72-fba229227d42`
**Window:** 2026-07-13T02:25:22.883695+00:00 — 2026-07-13T02:25:27.407788+00:00
**Uncertainty:** HIGH_CONFIDENCE
**Category:** Off-Hours Deviation
**Cause:** Identity executed unseen operations during an historically inactive hour.
**Scores:** Total `2.99` | Eff. Signals `3` | Dominant Signal `New Operations` | New Ops `1.0` | New IP `0.0` | New RG `0.0` | Act Spike `0.113` | Hour Dev `0.877`