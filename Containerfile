FROM alpine:3.24
RUN apk add --no-cache python3 py3-pip nginx
WORKDIR /app
# copy only install inputs so fleet.yaml/macs.csv/output can't bake into a layer
COPY pyproject.toml README.md LICENSE snompl.py pbx_export.py /app/
RUN pip3 install --no-cache-dir --break-system-packages .

RUN cat > /etc/nginx/nginx.conf <<'EOF'
worker_processes auto;
daemon off;
pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events {}
http {
    server_tokens off;
    types { text/xml xml; }
    access_log /dev/stdout;
    server {
        listen 80;
        root /srv;
        autoindex off;
    }
}
EOF

CMD sh -c "snompl generate -c /app/fleet.yaml -o /srv/snom && nginx"
EXPOSE 80
