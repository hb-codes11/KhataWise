# KhaataWise · Cloud self-healing

- **Application:** https://khatawise-n849.vercel.app/
- **Web recovery center:** https://khatawise-n849.vercel.app/healer/
- **Cloud runs and evidence:** https://github.com/hb-codes11/KhataWise/actions/workflows/self-heal.yml

## Use it entirely from the web

1. Open the recovery center and choose **Run recovery demo**. The server processes
   a sample expense with a formatted amount and missing category. It logs each
   failure, applies a bounded transformation, retries, and verifies the result.
   This isolated demo changes neither production code nor financial records.
2. Choose **Run cloud check on GitHub** for a full application check. Sign into
   GitHub as a repository collaborator, choose **Run workflow**, keep `main`, and
   confirm. Watch the job and download its `cloud-recovery-report` artifact.
3. Cloud checks also run on source changes and approximately every 15 minutes.
   GitHub can delay scheduled runs. Your laptop and localhost server are unnecessary.

## Actual source recovery

The deliberately broken expense branch has been removed, and expense creation has
an authenticated POST regression test. The GitHub Actions runner checks out `main`,
runs the application tests, and examines their failure logs. If the exact recognized
expense fault returns, it removes that fault block, reruns all app tests, rolls back
failed patches, and commits/pushes only the verified expense source change using its
short-lived repository token. The existing Vercel Git integration deploys source
commits. Unknown faults are reported for review rather than called healed.

Every run also recreates the broken expense source in a temporary Git repository,
checks real repair and rollback, and probes the production URL. The isolated fixture
never introduces a fault into production. A green run means these bounded checks
passed, not that every possible production fault can be repaired automatically.

The public web page cannot issue shell commands or push repository changes.
Starting cloud jobs requires GitHub collaborator access. The workflow limits repair
to the recognized source block and has a ten-minute execution limit.

## Validation

```
python3 manage.py test khaatawise --noinput
python3 -m unittest test_recovery test_vercel_bridge -v
AI_PROVIDER=mock python3 test_healing.py
python3 cloud_healer.py
```

## Optional local diagnostics

`python3 run_all.py` still supervises the local Django app (8000) and legacy healer
(8080). Its optional Vercel runtime-log bridge uses `vercel login` and stays on the
local machine. This local stream is separate from the cloud workflow, which reads
its regression-test logs and checks public production health. The hosted workflow
does not currently ingest Vercel's private runtime logs.

Vercel currently stores SQLite in temporary storage. A hosted database is needed
for durable production financial records; that hosting setting is unchanged.
