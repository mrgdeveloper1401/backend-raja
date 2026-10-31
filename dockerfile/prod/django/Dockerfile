FROM py_raja

WORKDIR /app

COPY . .

RUN chmod +x /app/scripts/*

ENTRYPOINT ["/bin/bash", "/app/scripts/start.sh"]