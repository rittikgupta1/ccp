---
title: "Rain Day EOB Mitigation Playbook - Bangalore"
date: 2026-05-05
author: ritikguptasnabbit
team: ops
type: playbook
trust: draft
expires: 2026-08-03
---

# Rain Day EOB Mitigation Playbook - Bangalore

## Rain Day EOB Mitigation Playbook — Bangalore

**Trigger:** Weather forecast predicts >20mm rainfall in any Bangalore cluster.

### Pre-Rain (2 hours before)

1. Check OpenWeatherMap forecast for cluster-level rainfall
2. If >20mm predicted:
   - Activate 5 additional OT runners in affected clusters
   - Add 15% buffer to all OSRM travel time estimates
   - Notify city ops lead via Slack: #bangalore-ops
3. Pre-position runners in high-demand hoods (Bellandur, Sarjapur, Varthur)

### During Rain

1. Monitor EOB dashboard every 30 minutes
2. If EOB > 15 mins in any cluster:
   - Redistribute runners from non-rain clusters
   - Pause new job acceptance if runner coverage < 50%
3. Track runner shelter breaks — allow up to 5 min, flag > 10 min

### Post-Rain

1. Run EOB attribution analysis (weather vs attendance vs behavior)
2. Update this playbook with any new learnings
3. File incident report if SLA breach > 15%

### Key Contacts

| Role | Name | Slack |
|------|------|-------|
| City Ops Lead | Ravi | @ravi-ops |
| Data On-Call | Ritik | @ritik |
| Runner Ops | Arjun | @arjun-ops |

