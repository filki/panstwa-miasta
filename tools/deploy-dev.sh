#!/bin/sh
# Deploy dev branch to dev server
set -e
git push origin dev
ssh hcloud "cd /srv/panstwa-miasta-dev && git pull && systemctl restart panstwa-miasta-dev"
echo "Dev deployed: http://46.62.225.116:8001/"
