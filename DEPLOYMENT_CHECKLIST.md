# Deployment Checklist (Public Launch)

## P0 Required
- Set `APP_ENV=production`
- Set `SESSION_SECRET_KEY` (strong random value)
- Set `TRUSTED_HOSTS` to your domain(s)
- Set `ENABLE_HTTPS_REDIRECT=true`
- Set `REQUESTS_PER_MINUTE` appropriately
- Configure mail sender: `BREVO_API_KEY` + `SENDER_EMAIL` (verified)
- Configure admin creds: `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`
- Rotate all previously exposed credentials

## Infrastructure
- Deploy with Docker (`Dockerfile` included)
- Use HTTPS termination at proxy/platform
- Add uptime checks against `/healthz` and `/readyz`
- Configure error log shipping / monitoring (Sentry optional)
- Migrate SQLite data using `POSTGRES_MIGRATION.md`
- Set `DATABASE_URL` in production runtime

## Data & Compliance
- Publish Privacy and Terms pages (routes included)
- Define data retention policy for resumes/interview/coding submissions
- Add regular DB backup and restore drills
- Use managed Postgres for production scale

## Quality
- Run CI (workflow included)
- Add staged environment and smoke tests before production promotion

## Security hardening to complete externally
- WAF / bot mitigation
- CAPTCHA provider wiring if needed
- Domain and DNS security (CAA, SPF, DKIM, DMARC)
