FROM n8nio/n8n:latest

USER root
RUN if command -v apk >/dev/null 2>&1; then \
      apk add --no-cache python3 py3-pip su-exec; \
    else \
      apt-get update && apt-get install -y --no-install-recommends python3 python3-pip gosu && rm -rf /var/lib/apt/lists/*; \
    fi

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5678
ENTRYPOINT ["/entrypoint.sh"]
CMD ["n8n", "start"]
