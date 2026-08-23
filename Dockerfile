# see.io site contract: serve plain HTTP on :8080 (the platform terminates TLS).
FROM busybox:stable
COPY . /www
EXPOSE 8080
CMD ["httpd", "-f", "-p", "8080", "-h", "/www"]
