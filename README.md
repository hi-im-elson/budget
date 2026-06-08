# Budget

## Where do I find transaction data?
### American Express
1. Go to [website]
2. Scroll to recent activity
3. Click `View All Recent Activity`
4. Hover over `Your Statement` and click `Export Statement Data`
5. Select `Download > CSV > Include all transaction details`

### RBC



### Wealthsimple
1. Login to [website]
2. Click on profile icon
3. Select `Settings > Accounts`
4. Select cash account
5. Select monthly statements
6. Select `Download CSV` for cash account

## Restoring from backup

To restore a backup into the running Postgres container:

    cat backups/budget_YYYYMMDD_HHMMSS.sql | docker compose exec -T postgres psql -U budget -d budget

To trigger a backup immediately without waiting 24 hours:

    docker compose exec postgres_backup sh -c "pg_dump -h postgres -U \$POSTGRES_USER \$POSTGRES_DB > /backups/manual_\$(date +%Y%m%d_%H%M%S).sql"
