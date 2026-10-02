#!/bin/sh
# Installs WordPress + WooCommerce and mints two API keys for LOCAL DEV:
#   /keys/connector.env  read-only key  -> what the connector uses
#   /keys/seed.env       read/write key -> only used by scripts/seed.py to create fake data
set -eu
cd /var/www/html

until wp db check --skip-ssl >/dev/null 2>&1; do sleep 2; done
if ! wp core is-installed 2>/dev/null; then
  wp core install --url=http://localhost:8081 --title="Demo Shop" \
    --admin_user=admin --admin_password=admin-local-only --admin_email=admin@example.com --skip-email
fi
wp plugin install woocommerce --activate
wp option update woocommerce_currency INR
wp rewrite structure '/%postname%/' --hard

mint() { # $1=permissions $2=description $3=output file
  wp eval "
    global \$wpdb;
    \$ck = 'ck_' . wc_rand_hash(); \$cs = 'cs_' . wc_rand_hash();
    \$wpdb->insert(\$wpdb->prefix . 'woocommerce_api_keys', [
      'user_id' => 1, 'description' => '$2', 'permissions' => '$1',
      'consumer_key' => wc_api_hash(\$ck), 'consumer_secret' => \$cs,
      'truncated_key' => substr(\$ck, -7),
    ]);
    echo \"\$ck \$cs\";" > /tmp/pair
  set -- "$1" "$2" "$3" "$(cut -d' ' -f1 /tmp/pair)" "$(cut -d' ' -f2 /tmp/pair)"
  printf 'WOO_CONSUMER_KEY=%s\nWOO_CONSUMER_SECRET=%s\n' "$4" "$5" > "$3"
}
mint read "connector (read-only)" /keys/connector.env
mint read_write "seed script (local only)" /keys/seed.env
echo "Done. Keys are in ./.local/ (git-ignored). Store: http://localhost:8081"
