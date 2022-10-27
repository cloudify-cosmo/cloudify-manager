FROM minio/minio

ENV MINIO_ROOT_USER=admin
ENV MINIO_ROOT_PASSWORD=admin123

CMD ["minio", "server", "/data", "--console-address", ":9090"]
