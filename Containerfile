FROM alpine:3.24
RUN apk add --no-cache python3 py3-pip nginx
WORKDIR /app
COPY . /app
RUN pip3 install --no-cache-dir --break-system-packages .

# Full custom nginx: serve one dir, list nothing, no version banner.
# Replaces Alpine's default include stack entirely — nothing we don't control.
RUN cat > /etc/nginx/nginx.conf <<'EOF'
worker_processes auto;
daemon off;
pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events {}
http {
    server_tokens off;
    types { text/xml xml; }
    default_type application/octet-stream;
    access_log /dev/stdout;
    server {
        listen 80;
        root /srv;
        autoindex off;
    }
}
EOF

# fleet.yaml mounted at runtime (no secrets in image layers); generate then serve.
# Phones fetch http://<server>/snom/snom-<mac>.xml  ->  /srv/snom/snom-<mac>.xml
CMD sh -c "snompl generate -c /app/fleet.yaml -o /srv/snom && nginx"
EXPOSE 80
