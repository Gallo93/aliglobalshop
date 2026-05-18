FROM n8nio/n8n:latest

USER root
RUN apk add --no-cache python3 py3-pip su-exec

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 5678
ENTRYPOINT ["/entrypoint.sh"]
CMD ["n8n", "start"]
