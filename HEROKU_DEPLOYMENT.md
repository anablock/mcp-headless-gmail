# Deploying Gmail Auto-Response System to Heroku

This guide walks through deploying the Gmail Auto-Response system to Heroku for production use.

## Prerequisites

1. [Heroku account](https://signup.heroku.com/) (free tier is available)
2. [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli) installed locally
3. Git repository with your Gmail Auto-Response code

## Setup Steps

### 1. Login to Heroku CLI

```bash
heroku login
```

### 2. Create a new Heroku app

```bash
# Navigate to your project directory
cd /path/to/mcp-headless-gmail

# Create a new Heroku app
heroku create anablock-gmail-autoresponse

# Alternatively, let Heroku generate a random name
# heroku create
```

### 3. Provision a PostgreSQL database

```bash
heroku addons:create heroku-postgresql:hobby-dev
```

### 4. Set environment variables

Set all required environment variables securely in Heroku:

```bash
heroku config:set GOOGLE_CLIENT_ID="your-client-id"
heroku config:set GOOGLE_CLIENT_SECRET="your-client-secret"
heroku config:set GOOGLE_REFRESH_TOKEN="your-refresh-token"
heroku config:set HEROKU=true
```

### 5. Deploy your application

```bash
# Commit any changes if needed
git add .
git commit -m "Prepared for Heroku deployment"

# Deploy to Heroku
git push heroku main
# Or if you're on a different branch
# git push heroku yourbranch:main
```

### 6. Verify deployment

```bash
# Open your application in a browser
heroku open

# Check logs for any errors
heroku logs --tail
```

## Scaling and Monitoring

### Scaling your application

```bash
# Scale to more dynos if needed (costs apply)
heroku ps:scale web=2

# Scale back down
heroku ps:scale web=1
```

### Monitoring

```bash
# View application metrics
heroku metrics

# Set up Heroku application monitoring
heroku addons:create papertrail:choklad
```

## Setting up Auto-Response Scheduling

To run the auto-response check periodically, add the Heroku Scheduler addon:

```bash
heroku addons:create scheduler:standard

# Then configure a job to run regularly:
heroku addons:open scheduler
```

In the scheduler dashboard, add a new job with the following command:
```
python -c "from auto_response import main; main()"
```

Set it to run:
- Every 10 minutes for frequent checking
- Hourly for normal usage
- Daily for low-volume inboxes

## Handling Heroku Application Sleep (Free Tier)

If using the free tier, Heroku applications "sleep" after 30 minutes of inactivity. To keep your application awake:

1. Use a service like [UptimeRobot](https://uptimerobot.com/) to ping your application
2. Or upgrade to a Hobby dyno ($7/month) which doesn't sleep

## Troubleshooting

- **Application crashes**: Check logs with `heroku logs --tail`
- **Database issues**: Run `heroku pg:info` to check database status
- **Email sending failures**: Verify your Google tokens are valid and not expired
