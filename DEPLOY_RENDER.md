# Deploy PlacementGap to Render

This Blueprint builds the React app into the FastAPI image and serves both from one HTTPS origin. It also provisions a private Render Postgres database and persistent disk for authentication, run records, caches, and reports. Keeping the UI and API on one origin keeps OAuth callbacks and session cookies aligned.

## Completely Free Deployment

This Blueprint runs on Render's **Free Web Service** tier ($0/month) and connects to your free **Neon.tech** PostgreSQL database with `pgvector`. No paid persistent disks or paid Render databases are required.

The initial configuration uses fixture-backed job data and disables paid LLM calls, so the app can start without an AI provider key. OAuth and email OTP require the provider and SMTP values described below.

## Create the Render Blueprint

1. Push the project to GitHub (`origin main`).
2. In Render, choose **New + → Blueprint** (or **New + → Web Service**) and connect the `PlacementGap` repository.
3. Review the resources from `render.yaml` — the estimated monthly cost will be **$0.00 / month (Free)**.
4. Set the `DATABASE_URL` environment variable to your free Neon PostgreSQL connection string.
5. Enter your SMTP and OAuth credentials in Render's secret fields if desired.
6. Click **Apply** to deploy! Render will build the container from `Dockerfile` and serve both frontend and backend on your assigned Render HTTPS URL.

## Finish OAuth setup

After the first deploy, copy the app's public Render URL, for example `https://placementgap-app.onrender.com`. Add these callback URLs to the matching provider applications, replacing the example host with the exact URL Render assigned:

- Google: `https://placementgap-app.onrender.com/auth/google/callback`
- Microsoft: `https://placementgap-app.onrender.com/auth/microsoft/callback`
- GitHub: `https://placementgap-app.onrender.com/auth/github/callback`

For Google, add the app URL as an authorized JavaScript origin and the callback as an authorized redirect URI. For Microsoft, register the callback as a **Web** redirect URI. For GitHub, use it as the Authorization callback URL. Save the matching client IDs and secrets in the Render service environment, then redeploy.

## Configure email OTP

Set `SMTP_HOST`, `SMTP_USERNAME`, `SMTP_PASSWORD`, and `SMTP_FROM` in the Render service environment. The Blueprint defaults to port `587` with STARTTLS (`SMTP_USE_SSL=false`). For implicit TLS, use port `465` and set `SMTP_USE_SSL=true`. Redeploy after changing environment values.

## Verify the deployed app

- Open the service's public HTTPS URL. The landing page, sign-in, and dashboard are served by the same service.
- Open `/health`; it should return the PlacementGap health response.
- Create an account and confirm the email OTP arrives.
- Test each configured OAuth provider and ensure it returns to the same Render host.
- Start an analysis, approve its plan, and download the generated report.

The default Blueprint runs with fixture-backed job data and no LLM calls. Change those flags only after configuring and validating the corresponding live providers.
