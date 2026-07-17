#!/usr/bin/env bash
set -Eeuo pipefail

DOMAIN="${1:?domain is required}"
REPOSITORY="${2:?repository URL is required}"
EMAIL="${3:?certificate email is required}"
BRANCH="${CAREERPILOT_BRANCH:-main}"
APP_DIR="/opt/careerpilot"
ENV_SOURCE="/tmp/careerpilot.env.oracle"

test -f "$ENV_SOURCE" || { echo "Missing $ENV_SOURCE" >&2; exit 1; }

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git nginx certbot
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
fi
sudo systemctl enable --now docker nginx

if [ ! -d "$APP_DIR/.git" ]; then
  sudo git clone --branch "$BRANCH" --single-branch "$REPOSITORY" "$APP_DIR"
  sudo chown -R "$USER":"$USER" "$APP_DIR"
else
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" pull --ff-only origin "$BRANCH"
fi

install -m 600 "$ENV_SOURCE" "$APP_DIR/deploy/oracle/.env.oracle"
cd "$APP_DIR"

sed "s/__DOMAIN__/${DOMAIN}/g" deploy/oracle/nginx/careerpilot.conf.template | sudo tee /etc/nginx/sites-available/careerpilot.conf >/dev/null
sudo ln -sfn /etc/nginx/sites-available/careerpilot.conf /etc/nginx/sites-enabled/careerpilot.conf
sudo rm -f /etc/nginx/sites-enabled/default
sudo mkdir -p /var/www/certbot
sudo nginx -t
sudo systemctl reload nginx

sudo docker compose --env-file deploy/oracle/.env.oracle -f deploy/oracle/docker-compose.yml up -d --build
for attempt in $(seq 1 60); do
  if curl -fsS http://127.0.0.1:3000/ >/dev/null; then break; fi
  sleep 2
done
curl -fsS http://127.0.0.1:3000/ >/dev/null

sudo docker compose --env-file deploy/oracle/.env.oracle -f deploy/oracle/docker-compose.yml exec -T backend sh -c \
  'INIT_USER_PASSWORD="$BOOTSTRAP_ADMIN_PASSWORD" python scripts/init_user.py --username "$BOOTSTRAP_ADMIN_USERNAME" --email admin@local.invalid --admin --legacy-owner'

sudo certbot certonly --webroot -w /var/www/certbot -d "$DOMAIN" --email "$EMAIL" --agree-tos --non-interactive --keep-until-expiring
sudo tee /etc/nginx/sites-available/careerpilot.conf >/dev/null <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;
    location /.well-known/acme-challenge/ { root /var/www/certbot; }
    location / { return 301 https://\$host\$request_uri; }
}
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name $DOMAIN;
    client_max_body_size 20m;
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
NGINX
sudo nginx -t
sudo systemctl reload nginx
curl -fsS "https://$DOMAIN/api/health"
echo "CareerPilot deployed at https://$DOMAIN"
