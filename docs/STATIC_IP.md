# Zach — give Cloud Run a static outbound IP (reduces anti-bot blocks)

**Why:** JobStreet (Cloudflare 403) and LinkedIn (429) rate-limit the random
*shared* Google Cloud egress IP that Cloud Run currently uses. Giving the
service a **static, dedicated outbound IP** makes it look like a stable
datacenter caller instead of a rotating/shared spam IP. This is on Google
Cloud (RULES-clean, no third-party). It does **not** turn it into a residential
IP, so it may not fully bypass aggressive walls — but it's the correct, real
lever and often reduces 403/429.

**Project:** `hireflow-506207` · **Region:** `us-central1` · **Today:** 2026-08-24

---

## How it works (30-second mental model)
Cloud Run has no outbound IP of its own. Outbound traffic goes through a VPC
connector → Cloud NAT. Cloud NAT can be pinned to a **static external IP** you
reserve. So: reserve a static IP → create a serverless VPC connector → create
Cloud NAT with that static IP → attach the connector to Cloud Run → all
outbound calls (JobStreet/LinkedIn) now come from your static IP.

---

## Steps (PowerShell/cmd, authenticated as owner)

### 1. Reserve a static external IP
```bash
gcloud compute addresses create hireflow-egress-ip --region us-central1
# capture the reserved address
gcloud compute addresses describe hireflow-egress-ip --region us-central1 --format='value(address)'
```

### 2. Enable + create a Serverless VPC connector
```bash
gcloud services enable vpcaccess.googleapis.com
gcloud compute networks vpc-access-connectors create hireflow-connector \
  --region us-central1 \
  --network default \
  --range 10.8.0.0/28 \
  --min-instances 2 --max-instances 10 \
  --machine-type e2-micro
```

### 3. Enable Cloud NAT pinned to the static IP
```bash
gcloud services enable compute.googleapis.com
# Router first
gcloud compute routers create hireflow-router --region us-central1 --network default
# NAT using the static IP
gcloud compute routers nats create hireflow-nat \
  --router hireflow-router --region us-central1 \
  --nat-external-ip-pool hireflow-egress-ip \
  --nat-all-subnet-ip-ranges --auto-allocate-nat-cidrs
```

### 4. Attach the connector to the Cloud Run service (redeploy)
Add `--vpc-connector hireflow-connector` to the deploy. Because egress must go
through the connector, **set `--no-cpu-throttling`** so the connector path works
and requests aren't throttled (Cloud Run requires this for VPC egress on
long-running requests):

```bash
gcloud run deploy hireflow-backend --region us-central1 --source . \
  --allow-unauthenticated \
  --memory 3Gi --cpu 2 --timeout 3600 \
  --vpc-connector hireflow-connector \
  --no-cpu-throttling \
  --set-env-vars GCP_PROJECT_ID=hireflow-506207,GEMINI_USE_VERTEX=true,VERTEX_LOCATION=global,GEMINI_MODEL=gemini-3.5-flash,RESUME_PARSE_MODE=hybrid,QUERY_EXPANSION=true,JOB_RECENCY_DAYS=14,DIVERSITY_MAX_SAME_COMPANY=2,SEMANTIC_SEARCH=1,HIREFLOW_PLAYWRIGHT=1,JOBSTREET_ENABLED=true,EMBEDDING_MODEL=gemini-embedding-001
```

### 5. Verify the egress IP changed
After deploy, from a terminal that can call the service, confirm the outbound IP
is your static one. Simplest: temporarily hit a public "what's my IP" endpoint
through the service, or check Cloud NAT logs. A quick check:

```bash
# The service should now egress via the static IP; verify in NAT logs:
gcloud compute routers nats logs set-config hireflow-nat \
  --router hireflow-router --region us-central1 --enable --filter=NAT
# then view logs:
gcloud logging read 'resource.type="nat_gateway" AND jsonPayload.remote_ip="<your-static-ip>"'
```

---

## Cost
- 1 static IPv4 (~$0.005/hr ≈ ~$3.6/mo — negligible).
- Serverless VPC connector (per-instance hourly; e2-micro ×2 is small).
- Cloud NAT (data processing, small).
- `--no-cpu-throttling` (CPU always on — costs more but needed for VPC egress
  on long requests). Turn it off after the demo to save.

---

## If it still gets blocked
- **JobStreet/Cloudflare** may still challenge a datacenter IP even if static.
  That's the hard wall (needs residential/proxy — third-party, RULES risk).
- **LinkedIn 429** is a rate-limit, not an IP-reputation issue — the static IP
  alone may not fix it; our in-app throttle + 1×/run already reduced it.

**Bottom line:** this gives a stable, dedicated GCP egress IP — the correct
"change the IP" lever on Google Cloud. It's best-effort (may not fully bypass
Cloudflare), but it's the real, RULES-clean step. Skip it if cost/time is a
concern — the core search still works without it.

*Written from live GCP docs, 2026-08-24. Re-verify flags if gcloud drift.*